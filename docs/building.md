# Building the ENVY BLACK VEIL ISO

The OS is built the way AlmaLinux builds its own live media: `livemedia-creator --no-virt` on an **AlmaLinux 10** machine or VM, for that machine's architecture (**x86_64** or **aarch64**).

## One command, from macOS or any Linux

[`ci/build-in-vm.sh`](../ci/build-in-vm.sh) does the whole build in a throwaway AlmaLinux 10 VM — it's exactly what CI runs. It downloads AlmaLinux's official cloud image (checked against AlmaLinux's published SHA-256), boots it with QEMU and hardware acceleration, builds inside it, and copies the ISO back to `output/`. Nothing else on your computer changes.

```sh
# macOS: brew install qemu          Debian/Ubuntu: sudo apt install qemu-system qemu-utils cloud-image-utils
git clone https://github.com/xzchick/envy-black-veil.git
cd envy-black-veil
./ci/build-in-vm.sh                 # -> output/envy-black-veil-0.1.0-<your arch>.iso
```

- An **Apple Silicon Mac** builds the **aarch64** ISO (Apple's Hypervisor framework; on an M4 Max the build takes about 10 minutes); an Intel Mac or x86 Linux PC builds **x86_64** (KVM on Linux).
- On **Windows**, run it inside WSL2 (Windows 11 offers KVM there).
- `VM_CPUS`, `VM_MEM` (MiB), `VM_DISK`, `VM_SSH_PORT`, `VMDIR` and `OUT` tune the VM and where files go.

## Host requirements (building directly)

A clean AlmaLinux 10 machine or VM (x86_64 or aarch64, ~25 GB free disk, 8 GB+ RAM), as root:

```sh
sudo dnf install -y epel-release
sudo dnf install -y lorax lorax-templates-almalinux anaconda rpm-build createrepo_c pykickstart \
    librsvg2-tools grub2-tools-extra dejavu-sans-fonts dejavu-sans-mono-fonts
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
5. runs **`livemedia-creator --no-virt --make-iso`** against the kickstart, with an xz-compressed root in 1 MiB blocks (about 6% smaller than the default). This takes 10–50 minutes, depending on the machine and the mirrors.

The result lands in `output/`:

```
output/envy-black-veil-0.1.0-<arch>.iso
output/envy-black-veil-0.1.0-<arch>.iso.sha256
```

Override `VERSION`, `ARCH`, `RELEASEVER`, `OUTDIR`, `ISO_NAME` or `VOLID` as environment variables.

## How CI builds and tests it

Every change to the OS (kickstart, packaging, theme, build or CI scripts) runs the [**ISO** workflow](../.github/workflows/iso.yml), for both architectures:

- **x86_64**, on a GitHub-hosted Ubuntu runner with KVM: [`ci/build-in-vm.sh`](../ci/build-in-vm.sh) builds the ISO in an AlmaLinux 10 VM, then [`ci/boot-test.py`](../ci/boot-test.py) boots and checks it:
  - **the real path** — UEFI firmware → the ISO's own boot loader → the live desktop, with a screenshot every few seconds;
  - **Secure Boot** — the same path with Secure Boot on and Microsoft's keys enrolled (as on most PCs and Hyper-V), booting through GRUB's own command line with a serial console added, then checking from the inside that Secure Boot and kernel lockdown are on;
  - **the live system with a serial console** — logging in as the live user to check that the Plasma desktop runs, SELinux is enforcing, the firewall is on and opens nothing, nothing listens on the network, nothing phones home (no connectivity check, no firmware or DNF pings on a timer, Firefox without telemetry), and the ENVY identity is in place;
  - **an unattended install** with the same installer and payload as the desktop's *Install ENVY BLACK VEIL* icon: UEFI, LUKS2 full-disk encryption, one admin user;
  - **the installed disk** on fresh firmware, as if moved to another PC: typing the disk passphrase into the ENVY splash, reaching the ENVY login screen, checking the installed system from the inside, and signing in for a desktop screenshot — then once more with **Secure Boot** on.
  - **a USB stick**: the ISO written to a virtual 8 GB stick and booted on UEFI firmware through the stick's own boot menu, with *keep changes on this USB stick*. The first boot turns the stick's free space into a persistence partition. After a clean shutdown, the stick's partition table is still sound, and a second boot finds what the first one changed (a file in the live user's home and one in `/etc`).
- **aarch64**, on GitHub's ARM runner: built in a privileged AlmaLinux 10 container, then booted and checked the same way. GitHub's ARM runners have no hardware virtualization, so these VMs are emulated and the install test runs locally instead (`ci/boot-test.py --install` on an Apple Silicon Mac uses Apple's Hypervisor framework).

The screenshots, the results and the ISOs are kept as workflow artifacts (the ISOs for 14 days). `ci/boot-test.py` runs on Linux and macOS alike: `python3 ci/boot-test.py --install --iso output/envy-black-veil-0.1.0-<arch>.iso --out test/`.

## Just the theme packages

To build only the identity RPMs (for testing on an existing AlmaLinux 10 + KDE box):

```sh
mkdir -p .build/SOURCES
tar --transform "s,^,envy-black-veil-0.1.0/," -czf .build/SOURCES/envy-black-veil-0.1.0.tar.gz theme tools privacy LICENSE
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
- Privacy defaults: SELinux enforcing, the firewall on with nothing open, and SSH, printing (CUPS) and mDNS discovery (Avahi) installed but off. No connectivity check, no firmware-metadata or DNF "countme" pings on a timer, and Firefox without telemetry, studies or sponsored content ([`privacy/`](../privacy)). Cockpit, Samba and KDE's VNC/RDP desktop sharing aren't installed.
- A leaner set than the stock KDE spin, so the ISO is a single download under 2 GiB: no KDE wallpaper collection, Akonadi/MariaDB, legacy printer-driver database or `/usr/share/doc`.
- **Keep changes on a USB stick**: the live boot menu's *keep changes* entry, and a small dracut module ([`live/`](../live), package `envy-black-veil-live`) that turns a stick's free space into storage on first use. [`build/lorax-templates.py`](../build/lorax-templates.py) adds the entry to lorax's boot menus, and gives the aarch64 ISO the same USB layout as x86_64 (a GPT with its EFI system partition).
- The **Hardware Report** ([`tools/envy-hardware-report`](../tools/envy-hardware-report)): this computer's hardware, drivers and firmware problems, as a file to share without anything that identifies you.
- AlmaLinux's own release package stays in place, so `dnf`, the repositories and updates work exactly as on AlmaLinux 10; BLACK VEIL marks itself with `/etc/envy-black-veil-release`.
- **No ENVY applications.** They're added on the installed system with `envy-tools`.
