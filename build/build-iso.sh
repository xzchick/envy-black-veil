#!/usr/bin/env bash
# build-iso.sh — build the ENVY BLACK VEIL live ISO.
#
# Runs as root on an AlmaLinux 10 x86_64 host or VM (the way AlmaLinux builds its
# own live media). It:
#   1. builds the ENVY identity RPMs (theme, release + envy-tools),
#   2. publishes them as a local repo at /srv/envy-black-veil/repo, which the
#      kickstart installs from,
#   3. runs livemedia-creator --no-virt against kickstart/envy-black-veil.ks.
#
# It can't run on macOS or Windows: the OS is built on Linux. CI builds it in an
# AlmaLinux 10 VM on every change (see .github/workflows/iso.yml).
#
#   sudo dnf install -y epel-release
#   sudo dnf install -y lorax lorax-templates-almalinux anaconda rpm-build \
#        createrepo_c pykickstart librsvg2-tools
#   sudo ./build/build-iso.sh
#
# Env overrides: VERSION, ARCH, RELEASEVER, OUTDIR, ISO_NAME, VOLID.
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
ARCH="${ARCH:-x86_64}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${OUTDIR:-$HERE/output}"
WORK="${WORK:-/var/tmp/envy-black-veil-rpmbuild}"
ISO_NAME="${ISO_NAME:-envy-black-veil-${VERSION}-${ARCH}.iso}"
# ISO 9660 volume IDs are at most 32 characters; the live boot finds its root by it.
VOLID="${VOLID:-ENVY-BLACK-VEIL-${VERSION//./-}-${ARCH}}"
REPO_DIR=/srv/envy-black-veil/repo          # must match the kickstart's envy-local repo
KS="$HERE/kickstart/envy-black-veil.ks"
BASEOS="https://repo.almalinux.org/almalinux/10/BaseOS/${ARCH}/os"

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mbuild-iso:\033[0m %s\n" "$*" >&2; exit 1; }

# --- Preflight ---------------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "the ISO is built on Linux; this host is $(uname -s)."
[ "$(id -u)" = "0" ] || die "run with sudo (livemedia-creator needs root)."
[ "$(uname -m)" = "$ARCH" ] || die "build $ARCH images on an $ARCH host (this one is $(uname -m))."
[ "${#VOLID}" -le 32 ] || die "volume ID '$VOLID' is longer than 32 characters."
for t in rpmbuild createrepo_c livemedia-creator ksvalidator rsvg-convert curl python3; do
    command -v "$t" >/dev/null || die "missing '$t'. Install: lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart librsvg2-tools (see the top of this script)."
done
# Read the host's identity in a subshell: /etc/os-release defines VERSION, ID and
# friends, which must not overwrite this script's own VERSION.
# shellcheck disable=SC1091
host_os=$( (. /etc/os-release 2>/dev/null && echo "${ID:-}:${VERSION_ID:-}:${PRETTY_NAME:-unknown}") || echo "::unknown")
case "$host_os" in
    almalinux:10*) ;;
    *) say "warning: this recipe is tested on AlmaLinux 10; this host is ${host_os##*:}." ;;
esac

say "Validating the kickstart"
ksvalidator "$KS" || die "kickstart failed validation."

# The AlmaLinux 10 minor release the image is built from (e.g. 10.3), read from
# almalinux-release in the BaseOS repository, as AlmaLinux's own build does.
if [ -z "${RELEASEVER:-}" ]; then
    primary=$(curl -sf "$BASEOS/repodata/repomd.xml" | grep -oE 'repodata/[^"]*-primary\.xml\.gz' | head -n 1) || primary=
    RELEASEVER=$(curl -sf "$BASEOS/$primary" | gunzip | python3 -c \
        'import re,sys; print(re.search(r"<name>almalinux-release</name>.*?ver=\"([^\"]+)\"", sys.stdin.read(), re.S).group(1))') || RELEASEVER=
    [[ "$RELEASEVER" =~ ^10\.[0-9]+$ ]] || die "couldn't read the AlmaLinux 10 release version from $BASEOS (got '$RELEASEVER')."
fi
say "Building from AlmaLinux $RELEASEVER"

# --- 1. Build the ENVY identity RPMs ----------------------------------------
say "Building the ENVY identity RPMs (theme, release + envy-tools)"
rm -rf "$WORK"; mkdir -p "$WORK"/{SOURCES,SPECS,RPMS,BUILD,BUILDROOT,SRPMS}
tar --transform "s,^,envy-black-veil-${VERSION}/," \
    -czf "$WORK/SOURCES/envy-black-veil-${VERSION}.tar.gz" -C "$HERE" \
    theme tools LICENSE
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
    "$@"

ISO_PATH="$OUTDIR/result/$ISO_NAME"
[ -f "$ISO_PATH" ] || ISO_PATH="$(find "$OUTDIR/result" -name '*.iso' | head -1 || true)"
[ -n "$ISO_PATH" ] && [ -f "$ISO_PATH" ] || die "livemedia-creator did not produce an ISO (see $OUTDIR/logs)."
mv -f "$ISO_PATH" "$OUTDIR/$ISO_NAME"
( cd "$OUTDIR" && sha256sum "$ISO_NAME" > "${ISO_NAME}.sha256" )
echo "$VOLID" > "$OUTDIR/${ISO_NAME}.volid"

say "Done:"
printf "   %s\n   %s\n" "$OUTDIR/$ISO_NAME" "$OUTDIR/${ISO_NAME}.sha256"
say "Write it to a USB stick with:  sudo dd if=$OUTDIR/$ISO_NAME of=/dev/sdX bs=4M status=progress oflag=sync"
