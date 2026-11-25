#!/usr/bin/env bash
# build-iso.sh — build the ENVY BLACK VEIL live ISO.
#
# Runs as root on an AlmaLinux 10 host, VM or privileged container, x86_64 or
# aarch64 (the way AlmaLinux builds its own live media). It:
#   1. builds the ENVY identity RPMs (theme, release + envy-tools),
#   2. publishes them as a local repo at /srv/envy-black-veil/repo, which the
#      kickstart installs from,
#   3. runs livemedia-creator --no-virt against kickstart/envy-black-veil.ks.
#
# The OS is built on Linux. On macOS (or any Linux with KVM), ci/build-in-vm.sh runs
# this script in a throwaway AlmaLinux 10 VM, which is how CI builds every change
# (see .github/workflows/iso.yml).
#
#   sudo dnf install -y epel-release
#   sudo dnf install -y lorax lorax-templates-almalinux anaconda rpm-build \
#        createrepo_c pykickstart librsvg2-tools grub2-tools-extra dejavu-sans-fonts dejavu-sans-mono-fonts
#   sudo ./build/build-iso.sh
#
# Env overrides: VERSION, ARCH, RELEASEVER, OUTDIR, ISO_NAME, VOLID.
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
ARCH="${ARCH:-$(uname -m)}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${OUTDIR:-$HERE/output}"
WORK="${WORK:-/var/tmp/envy-black-veil-rpmbuild}"
ISO_NAME="${ISO_NAME:-envy-black-veil-${VERSION}-${ARCH}.iso}"
# ISO 9660 volume IDs are at most 32 characters; the live boot finds its root by it.
VOLID="${VOLID:-ENVY-BLACK-VEIL-${VERSION//./-}-${ARCH}}"
REPO_DIR=/srv/envy-black-veil/repo          # must match the kickstart's envy-local repo
KS_SRC="$HERE/kickstart/envy-black-veil.ks"
KS="$KS_SRC"
BASEOS="https://repo.almalinux.org/almalinux/10/BaseOS/${ARCH}/os"

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mbuild-iso:\033[0m %s\n" "$*" >&2; exit 1; }

# --- Preflight ---------------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "the ISO is built on Linux; this host is $(uname -s)."
[ "$(id -u)" = "0" ] || die "run with sudo (livemedia-creator needs root)."
[ "$(uname -m)" = "$ARCH" ] || die "build $ARCH images on an $ARCH host (this one is $(uname -m))."
[ "${#VOLID}" -le 32 ] || die "volume ID '$VOLID' is longer than 32 characters."
for t in rpmbuild createrepo_c livemedia-creator ksvalidator rsvg-convert curl python3; do
    command -v "$t" >/dev/null || die "missing '$t'. Install: lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart librsvg2-tools grub2-tools-extra dejavu-sans-fonts dejavu-sans-mono-fonts (see the top of this script)."
done
# Read the host's identity in a subshell: /etc/os-release defines VERSION, ID and
# friends, which must not overwrite this script's own VERSION.
# shellcheck disable=SC1091
host_os=$( (. /etc/os-release 2>/dev/null && echo "${ID:-}:${VERSION_ID:-}:${PRETTY_NAME:-unknown}") || echo "::unknown")
case "$host_os" in
    almalinux:10*) ;;
    *) say "warning: this recipe is tested on AlmaLinux 10; this host is ${host_os##*:}." ;;
esac

# One kickstart serves every architecture; lines marked "x86_64-only" are dropped
# for the others (AlmaLinux's own aarch64 KDE recipe differs only by memtest86+).
if [ "$ARCH" != "x86_64" ]; then
    KS="/var/tmp/envy-black-veil-${ARCH}.ks"
    grep -v '# x86_64-only' "$KS_SRC" > "$KS"
fi
say "Validating the kickstart ($ARCH)"
ksvalidator "$KS" || die "kickstart failed validation."

# The AlmaLinux 10 minor release the image is built from (e.g. 10.3), read from
# almalinux-release in the BaseOS repository (this also proves the repos answer).
primary=$(curl -sf "$BASEOS/repodata/repomd.xml" | grep -oE 'repodata/[^"]*-primary\.xml\.gz' | head -n 1) || primary=
ALMA_RELEASE=$(curl -sf "$BASEOS/$primary" | gunzip | python3 -c \
    'import re,sys; print(re.search(r"<name>almalinux-release</name>.*?ver=\"([^\"]+)\"", sys.stdin.read(), re.S).group(1))') || ALMA_RELEASE=
[[ "$ALMA_RELEASE" =~ ^10\.[0-9]+$ ]] || die "couldn't read the AlmaLinux 10 release version from $BASEOS (got '$ALMA_RELEASE')."
# livemedia-creator only uses this for the boot-menu labels ("Start ENVY BLACK VEIL
# 0.1.0"); the kickstart's repositories don't depend on it.
RELEASEVER="${RELEASEVER:-$VERSION}"
say "Building ENVY BLACK VEIL $VERSION from AlmaLinux $ALMA_RELEASE ($ARCH)"

# --- 1. Build the ENVY identity RPMs ----------------------------------------
say "Building the ENVY identity RPMs (theme, release + envy-tools)"
rm -rf "$WORK"; mkdir -p "$WORK"/{SOURCES,SPECS,RPMS,BUILD,BUILDROOT,SRPMS}
tar --transform "s,^,envy-black-veil-${VERSION}/," \
    -czf "$WORK/SOURCES/envy-black-veil-${VERSION}.tar.gz" -C "$HERE" \
    theme tools privacy LICENSE
rpmbuild --define "_topdir $WORK" -ba "$HERE/packaging/envy-black-veil.spec"

say "Publishing the local package repo at $REPO_DIR"
rm -rf "$REPO_DIR"; mkdir -p "$REPO_DIR"
find "$WORK/RPMS" -name '*.rpm' -exec cp -v {} "$REPO_DIR/" \;
createrepo_c "$REPO_DIR"

# --- 2. Build the live ISO ---------------------------------------------------
# AlmaLinux 10's live-media build runs with SELinux permissive on the build host;
# the image itself still ships with SELinux enforcing (see the kickstart).
if command -v getenforce >/dev/null && [ "$(getenforce)" = "Enforcing" ]; then
    say "Setting SELinux to permissive on this build host for the duration of the build"
    setenforce 0
fi

# A smaller ISO: xz-compressed squashfs with 1 MiB blocks (mksquashfs's default is
# 128 KiB) plus the CPU's branch filter for programs, as Arch Linux's live ISO does.
# A filter this mksquashfs doesn't have is left out.
case "$ARCH" in x86_64) BCJ=x86 ;; aarch64) BCJ=arm64 ;; *) BCJ="" ;; esac
probe="$(mktemp -d)"
mkdir "$probe/empty"
if [ -n "$BCJ" ] && ! mksquashfs "$probe/empty" "$probe/test.img" -comp xz -Xbcj "$BCJ" -noappend -quiet >/dev/null 2>&1; then
    BCJ=""
fi
rm -rf "$probe"
compress=(--compression xz "--compress-arg=-b 1M")
[ -z "$BCJ" ] || compress+=("--compress-arg=-Xbcj $BCJ")

rm -rf "$OUTDIR/result"            # livemedia-creator refuses an existing result dir
mkdir -p "$OUTDIR/logs"
say "Building the live ISO with livemedia-creator (about 20–50 minutes)"
livemedia-creator \
    --ks "$KS" \
    --no-virt \
    --make-iso \
    --iso-only \
    --iso-name "$ISO_NAME" \
    --project "ENVY BLACK VEIL" \
    --releasever "$RELEASEVER" \
    --volid "$VOLID" \
    --resultdir "$OUTDIR/result" \
    --logfile "$OUTDIR/logs/livemedia.log" \
    --nomacboot \
    "${compress[@]}" \
    "$@"

ISO_PATH="$OUTDIR/result/$ISO_NAME"
[ -f "$ISO_PATH" ] || ISO_PATH="$(find "$OUTDIR/result" -name '*.iso' | head -1 || true)"
[ -n "$ISO_PATH" ] && [ -f "$ISO_PATH" ] || die "livemedia-creator did not produce an ISO (see $OUTDIR/logs)."
mv -f "$ISO_PATH" "$OUTDIR/$ISO_NAME"
( cd "$OUTDIR" && sha256sum "$ISO_NAME" > "${ISO_NAME}.sha256" )
echo "$VOLID" > "$OUTDIR/${ISO_NAME}.volid"

# --- 3. What's inside: package list and CycloneDX SBOM ------------------------
# Read from the finished image's own RPM database, so they describe exactly what ships.
say "Listing the image's packages (package list and CycloneDX SBOM)"
inspect="$(mktemp -d)"
mkdir -p "$inspect/iso" "$inspect/squash" "$inspect/ext"
root=""
if mount -o loop,ro "$OUTDIR/$ISO_NAME" "$inspect/iso" && mount -o loop,ro "$inspect/iso/LiveOS/squashfs.img" "$inspect/squash"; then
    root="$inspect/squash"
    # Older layouts wrap an ext4 image inside the squashfs.
    if [ -f "$root/LiveOS/rootfs.img" ] && mount -o loop,ro "$root/LiveOS/rootfs.img" "$inspect/ext"; then
        root="$inspect/ext"
    fi
fi
base="${ISO_NAME%.iso}"
if [ -n "$root" ] && rpm -qa --root "$root" --qf '%{NAME}-%{VERSION}-%{RELEASE}.%{ARCH}\n' | sort > "$OUTDIR/$base.packages.txt" \
   && rpm -qa --root "$root" --qf '%{NAME}\t%{EPOCHNUM}\t%{VERSION}\t%{RELEASE}\t%{ARCH}\t%{LICENSE}\t%{VENDOR}\n' \
        | python3 "$HERE/ci/sbom.py" --version "$VERSION" --arch "$ARCH" > "$OUTDIR/$base.cdx.json"; then
    say "$(wc -l < "$OUTDIR/$base.packages.txt") packages: $OUTDIR/$base.packages.txt, $OUTDIR/$base.cdx.json"
else
    printf "\033[38;5;205mbuild-iso:\033[0m warning: couldn't list the image's packages\n" >&2
    rm -f "$OUTDIR/$base.packages.txt" "$OUTDIR/$base.cdx.json"
fi
umount "$inspect/ext" 2>/dev/null || :
umount "$inspect/squash" 2>/dev/null || :
umount "$inspect/iso" 2>/dev/null || :
rm -rf "$inspect"

say "Done:"
printf "   %s\n   %s\n" "$OUTDIR/$ISO_NAME" "$OUTDIR/${ISO_NAME}.sha256"
say "Write it to a USB stick with:  sudo dd if=$OUTDIR/$ISO_NAME of=/dev/sdX bs=4M status=progress oflag=sync"
