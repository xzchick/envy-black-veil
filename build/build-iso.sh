#!/usr/bin/env bash
# build-iso.sh — build the ENVY BLACK VEIL live ISO.
#
# Runs on an AlmaLinux 10 / RHEL 10 / Fedora host (it uses lorax's
# livemedia-creator, rpmbuild and createrepo_c). It:
#   1. builds the ENVY identity RPMs (theme, release, calamares branding),
#   2. puts them in a local repo the kickstart installs from,
#   3. runs livemedia-creator against kickstart/envy-black-veil.ks.
#
# This CANNOT run on macOS or Windows — the OS is built on Linux. Everything in
# this repository is the real build system; only the final .iso is produced here.
#
#   sudo ./build/build-iso.sh
#
# Env overrides: VERSION, ARCH, RELEASEVER, OUTDIR, ISO_NAME.
set -euo pipefail

VERSION="${VERSION:-0.1.0}"
ARCH="${ARCH:-x86_64}"
RELEASEVER="${RELEASEVER:-10}"
HERE="$(cd "$(dirname "$0")/.." && pwd)"
OUTDIR="${OUTDIR:-$HERE/output}"
WORK="${WORK:-$HERE/.build}"
ISO_NAME="${ISO_NAME:-envy-black-veil-${VERSION}-${ARCH}.iso}"
REPO_DIR="$WORK/envy-repo"
KS="$HERE/kickstart/envy-black-veil.ks"

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mbuild-iso:\033[0m %s\n" "$*" >&2; exit 1; }

# --- Preflight ---------------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || die "the ISO is built on Linux; this host is $(uname -s)."
[ "$(id -u)" = "0" ] || die "run with sudo (livemedia-creator needs root)."
for t in rpmbuild createrepo_c livemedia-creator ksvalidator rsvg-convert; do
    command -v "$t" >/dev/null || die "missing '$t'. Install: lorax rpm-build createrepo_c pykickstart librsvg2-tools."
done

say "Validating the kickstart"
ksvalidator "$KS" || die "kickstart failed validation."

# --- 1. Build the ENVY identity RPMs ----------------------------------------
say "Building the ENVY identity RPMs (theme, release, calamares branding)"
rm -rf "$WORK"; mkdir -p "$WORK"/{SOURCES,SPECS,RPMS,BUILD,BUILDROOT,SRPMS} "$REPO_DIR"
TARBALL="$WORK/SOURCES/envy-black-veil-${VERSION}.tar.gz"
tar --transform "s,^,envy-black-veil-${VERSION}/," \
    -czf "$TARBALL" -C "$HERE" \
    theme tools release installer LICENSE
rpmbuild --define "_topdir $WORK" -ba "$HERE/packaging/envy-black-veil.spec"
find "$WORK/RPMS" -name '*.rpm' -exec cp -v {} "$REPO_DIR/" \;

say "Publishing the local package repo"
createrepo_c "$REPO_DIR"

# --- 2. Build the live ISO ---------------------------------------------------
# The ENVY repo is handed to the installer as an extra source; the kickstart's
# file:///run/install/repo/envy-repo line resolves it inside the build root.
mkdir -p "$OUTDIR"
say "Building the live ISO with livemedia-creator (this takes a while)"
livemedia-creator \
    --make-iso \
    --ks "$KS" \
    --iso-name "$ISO_NAME" \
    --project "ENVY BLACK VEIL" \
    --releasever "$RELEASEVER" \
    --resultdir "$OUTDIR/result" \
    --extra-boot-args "quiet rhgb" \
    --repo "$REPO_DIR" \
    --nomacboot \
    "$@"

ISO_PATH="$(find "$OUTDIR/result" -name '*.iso' | head -1 || true)"
[ -n "$ISO_PATH" ] || die "livemedia-creator did not produce an ISO (see $OUTDIR/result)."
cp -f "$ISO_PATH" "$OUTDIR/$ISO_NAME"
( cd "$OUTDIR" && sha256sum "$ISO_NAME" > "${ISO_NAME}.sha256" )

say "Done:"
printf "   %s\n   %s\n" "$OUTDIR/$ISO_NAME" "$OUTDIR/${ISO_NAME}.sha256"
say "Write it to a USB with:  sudo dd if=$OUTDIR/$ISO_NAME of=/dev/sdX bs=4M status=progress oflag=sync"
