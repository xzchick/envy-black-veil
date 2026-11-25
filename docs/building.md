# Building the ENVY BLACK VEIL ISO

The OS is built on **AlmaLinux 10 (x86_64)**, the same way AlmaLinux builds its own live media: `livemedia-creator --no-virt` inside an AlmaLinux 10 host or VM. It can't be built on macOS or Windows; those can only write a finished ISO to a USB stick.

## Host requirements

A clean AlmaLinux 10 machine or VM (x86_64, ~25 GB free disk, 8 GB+ RAM), as root:

```sh
sudo dnf install -y epel-release
sudo dnf install -y lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart \
    librsvg2-tools grub2-tools-extra dejavu-sans-fonts
```

## Build

```sh
git clone https://github.com/xzchick/envy-black-veil.git
cd envy-black-veil
sudo ./build/build-iso.sh
```

That script:

1. **validates** [`kickstart/envy-black-veil.ks`](../kickstart/envy-black-veil.ks) with `ksvalidator`,
2. reads the current **AlmaLinux 10 minor release** from AlmaLinux's BaseOS repository (as AlmaLinux's own build does),
3. **builds the ENVY identity RPMs** (`envy-black-veil-theme`, `envy-black-veil-release`) from [`packaging/envy-black-veil.spec`](../packaging/envy-black-veil.spec), rendering the SVG art to PNG on the way, and publishes them as a local repo at `/srv/envy-black-veil/repo`,
4. sets SELinux to permissive **on the build host** for the build (AlmaLinux's live-media build does the same on EL10; the image itself ships SELinux enforcing),
5. runs **`livemedia-creator --no-virt --make-iso`** against the kickstart. This takes 20–50 minutes.

The result lands in `output/`:

```
output/envy-black-veil-0.1.0-x86_64.iso
output/envy-black-veil-0.1.0-x86_64.iso.sha256
```

Override `VERSION`, `RELEASEVER`, `OUTDIR`, `ISO_NAME` or `VOLID` as environment variables.

## How CI builds and tests it

Every change to the OS (kickstart, packaging, theme, build or CI scripts) runs the [**ISO** workflow](../.github/workflows/iso.yml) on a GitHub-hosted Ubuntu runner with KVM:

1. [`ci/build-in-vm.sh`](../ci/build-in-vm.sh) boots AlmaLinux's official 10 cloud image (checked against AlmaLinux's published SHA-256) in QEMU, logs in with a one-time SSH key, and runs `build/build-iso.sh` inside it.
2. [`ci/boot-test.py`](../ci/boot-test.py) boots the finished ISO twice:
   - **the real path** — UEFI firmware → the ISO's own boot loader → the live desktop, with a screenshot every few seconds;
   - **with a serial console** — the same kernel and initrd, so it can log in as the live user and check, from the inside, that the Plasma desktop is running, SELinux is enforcing, the firewall is on and opens nothing, no TCP port listens beyond loopback, SSH is off, and the ENVY identity is in place (boot splash, login theme, colours, wallpaper, installer, `envy-tools`, the ENVY app runtime).
3. The screenshots, the results and the ISO itself are kept as workflow artifacts (the ISO for 14 days).

## Just the theme packages

To build only the identity RPMs (for testing on an existing AlmaLinux 10 + KDE box):

```sh
mkdir -p .build/SOURCES
tar --transform "s,^,envy-black-veil-0.1.0/," -czf .build/SOURCES/envy-black-veil-0.1.0.tar.gz theme tools LICENSE
rpmbuild --define "_topdir $PWD/.build" -ba packaging/envy-black-veil.spec
```

## Validate without building

Anywhere with the linters installed:

```sh
make validate     # ksvalidator + shellcheck + desktop-file-validate + xmllint
```

CI runs this, plus a test build of the identity RPMs, on every push.

## What goes in the image

- **AlmaLinux 10** base, **KDE Plasma 6** desktop (from EPEL), SDDM, Plymouth, GRUB2 — AlmaLinux's own signed boot chain, unchanged.
- The **ENVY theme** applied to boot, login and desktop: boot splash, login screen, colour scheme, wallpaper, Konsole profile.
- The **ENVY tool runtime**: Python 3, PyQt6, `cryptography`, `git`, `pip` — so any ENVY app installs cleanly afterward.
- The **Anaconda** live installer — AlmaLinux's own, labelled *Install ENVY BLACK VEIL*. (Calamares isn't packaged for AlmaLinux 10, so BLACK VEIL uses what AlmaLinux uses.)
- Privacy defaults: SELinux enforcing, the firewall on with nothing open, and SSH, printing (CUPS) and mDNS discovery (Avahi) installed but off.
- AlmaLinux's own release package stays in place, so `dnf`, the repositories and updates work exactly as on AlmaLinux 10; BLACK VEIL marks itself with `/etc/envy-black-veil-release`.
- **No ENVY applications.** They're added on the installed system with `envy-tools`.
