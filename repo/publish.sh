#!/usr/bin/env bash
# publish.sh SITE: build ENVY BLACK VEIL's packages, sign them with the project's key,
# and lay out the package repository GitHub Pages serves at
# https://xzchick.github.io/envy-black-veil/ :
#
#   SITE/el10/                          the packages, and the repository's metadata
#                                       (its repomd.xml signed too: repomd.xml.asc)
#   SITE/envy-black-veil.repo           the repository file, for adding it by hand
#   SITE/RPM-GPG-KEY-envy-black-veil    the public key
#   SITE/index.html                     what the site shows in a browser
#
# Runs on AlmaLinux 10 (the package-repo workflow's container) with rpm-build,
# rpm-sign, createrepo_c, gnupg2 and what packaging/envy-black-veil.spec needs to
# build. The private key comes from $RPM_SIGNING_KEY, an armored OpenPGP secret key
# (the RPM_SIGNING_KEY secret in CI). It must be the key in RPM-GPG-KEY-envy-black-veil.
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
SITE="${1:?usage: publish.sh SITE}"
URL="https://xzchick.github.io/envy-black-veil"
KEY="$HERE/repo/RPM-GPG-KEY-envy-black-veil"

say() { printf "\033[38;5;51m==>\033[0m %s\n" "$*"; }
die() { printf "\033[38;5;205mpublish.sh:\033[0m %s\n" "$*" >&2; exit 1; }
[ -n "${RPM_SIGNING_KEY:-}" ] || die "RPM_SIGNING_KEY isn't set (the armored private signing key)."

work=$(mktemp -d)
GNUPGHOME=$(mktemp -d)
export GNUPGHOME
trap 'rm -rf "$work" "$GNUPGHOME"' EXIT

# --- The packages ----------------------------------------------------------------
version=$(awk '/^Version:/ {print $2}' "$HERE/packaging/envy-black-veil.spec")
say "Building the ENVY BLACK VEIL packages ($version)"
mkdir -p "$work"/{SOURCES,SPECS,RPMS,BUILD,BUILDROOT,SRPMS}
sources=(theme tools privacy live LICENSE)
[ -d "$HERE/repo" ] && sources+=(repo)
tar --transform "s,^,envy-black-veil-${version}/," -czf "$work/SOURCES/envy-black-veil-${version}.tar.gz" \
    -C "$HERE" "${sources[@]}"
rpmbuild --quiet --define "_topdir $work" -bb "$HERE/packaging/envy-black-veil.spec"

# --- Signed with the project's key -------------------------------------------------
gpg --batch --quiet --import <<< "$RPM_SIGNING_KEY"
fpr=$(gpg --batch --with-colons --list-secret-keys | awk -F: '/^fpr/ {print $10; exit}')
want=$(gpg --batch --with-colons --show-keys "$KEY" | awk -F: '/^fpr/ {print $10; exit}')
[ -n "$fpr" ] && [ "$fpr" = "$want" ] \
    || die "the signing key (${fpr:-none}) isn't the one in repo/RPM-GPG-KEY-envy-black-veil ($want)."

rm -rf "$SITE"
mkdir -p "$SITE/el10"
find "$work/RPMS" -name '*.rpm' -exec cp {} "$SITE/el10/" \;
say "Signing $(find "$SITE/el10" -name '*.rpm' | wc -l) packages with $fpr"
rpmsign --addsign --define "_gpg_name $fpr" --define "_gpg_path $GNUPGHOME" "$SITE"/el10/*.rpm > /dev/null

# Check them the way a BLACK VEIL system will: rpm, with nothing but the public key.
db=$(mktemp -d)
rpm --dbpath "$db" --import "$KEY"
for f in "$SITE"/el10/*.rpm; do
    out=$(rpm --dbpath "$db" -K "$f")
    echo "   $out"
    case "$out" in *": digests signatures OK") ;; *) die "${f##*/} isn't signed as it should be." ;; esac
done
rm -rf "$db"

# --- The repository ------------------------------------------------------------------
say "Writing the repository"
createrepo_c --quiet "$SITE/el10"
gpg --batch --yes --armor --detach-sign --local-user "$fpr" "$SITE/el10/repodata/repomd.xml"
cp "$KEY" "$SITE/"
# Added by hand (BLACK VEIL 0.1.0 came out before the repository), dnf gets the key from
# the site; BLACK VEIL's own copy of this file reads it from /etc/pki/rpm-gpg.
sed "s#^gpgkey=.*#gpgkey=$URL/RPM-GPG-KEY-envy-black-veil#" "$HERE/repo/envy-black-veil.repo" \
    > "$SITE/envy-black-veil.repo"

# The page: the template with the packages, the key's fingerprint and the date.
for f in "$SITE"/el10/*.rpm; do printf '      <li><code>%s</code></li>\n' "${f##*/}"; done > "$work/packages.html"
fingerprint=$(printf '%s' "$fpr" | sed 's/.\{4\}/& /g; s/ $//')
sed -e "/@PACKAGES@/{r $work/packages.html" -e 'd;}' \
    -e "s/@FINGERPRINT@/$fingerprint/g" \
    -e "s/@UPDATED@/$(date -u '+%Y-%m-%d %H:%M UTC')/g" \
    "$HERE/repo/index.html" > "$SITE/index.html"

say "Done: $SITE"
find "$SITE" -type f | sort | sed 's/^/   /'
