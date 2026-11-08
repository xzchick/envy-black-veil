# Building the ENVY BLACK VEIL ISO

The OS is built on **Linux** (AlmaLinux 10 / RHEL 10 / Fedora). It cannot be built on macOS or Windows — those can only write a finished ISO to a USB stick.

## Host requirements

A clean AlmaLinux 10 (or compatible) box or VM, run as root:

```sh
sudo dnf install -y lorax rpm-build createrepo_c pykickstart librsvg2-tools
# KDE Plasma 6 and Calamares come from EPEL, enabled by the kickstart:
sudo dnf install -y epel-release
```

Give the build host ~20 GB free and a few CPU cores; `livemedia-creator` spins up a short-lived VM to compose the image.

## Build

```sh
git clone https://github.com/xzchick/envy-black-veil.git
cd envy-black-veil
sudo ./build/build-iso.sh
```

That script:

1. **validates** `kickstart/envy-black-veil.ks` with `ksvalidator`,
2. **builds the ENVY identity RPMs** (`envy-black-veil-theme`, `-release`, `calamares-branding-envy`) from [`packaging/envy-black-veil.spec`](../packaging/envy-black-veil.spec) — rendering the SVG art to PNG along the way,
3. puts them in a **local repo** the kickstart installs from,
4. runs **`livemedia-creator --make-iso`** against the kickstart.

The result lands in `output/`:

```
output/envy-black-veil-0.1.0-x86_64.iso
output/envy-black-veil-0.1.0-x86_64.iso.sha256
```

Override `VERSION`, `ARCH`, `RELEASEVER`, `OUTDIR` or `ISO_NAME` as environment variables.

## Just the theme packages

To build only the identity RPMs (for testing on an existing KDE box):

```sh
rpmbuild --define "_topdir $PWD/.build" -ba packaging/envy-black-veil.spec
```

## Validate without building

Anywhere with the linters installed:

```sh
make validate     # ksvalidator + shellcheck + desktop-file-validate + xmllint
```

CI runs this on every push.

## What goes in the image

- **AlmaLinux 10** base, **KDE Plasma 6** desktop (from EPEL), SDDM, Plymouth, GRUB2.
- The **ENVY theme** applied to boot, login and desktop.
- The **ENVY tool runtime**: Python 3, PyQt6, `cryptography`, `git`, `pip` — so any ENVY app installs cleanly afterward.
- The **Calamares** installer, ENVY-branded.
- **No ENVY applications.** They are added on the installed system with `envy-tools`.
