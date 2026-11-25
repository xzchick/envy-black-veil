# Try ENVY BLACK VEIL on your computer — Windows, macOS or Linux

Two ways, from safest to most real:

1. **In a virtual machine** — BLACK VEIL runs in a window on your current system. Nothing on your computer changes. Best for a first look, and you can even install it onto the VM's virtual disk.
2. **From a USB stick** — boot your actual computer into the live desktop. Nothing is written to your disks unless you run the installer. See [install-to-external-drive.md](install-to-external-drive.md).

## 1. Get the right ISO

| Your computer | ISO to use |
| --- | --- |
| Windows PC, Linux PC, Intel Mac | `envy-black-veil-0.1.0-x86_64.iso` |
| Apple Silicon Mac (M1–M4), ARM Windows / Linux devices | `envy-black-veil-0.1.0-aarch64.iso` |

Download yours, and `SHA256SUMS.txt`, from the **[latest release](https://github.com/xzchick/envy-black-veil/releases/latest)**. Every release ISO passed all of CI's checks before it was published. (Builds of every later change are kept for 14 days as artifacts of the [ISO workflow](https://github.com/xzchick/envy-black-veil/actions/workflows/iso.yml); they need a free GitHub account.)

Check it before you use it:

```sh
sha256sum -c SHA256SUMS.txt --ignore-missing            # Linux
shasum -a 256 -c SHA256SUMS.txt --ignore-missing        # macOS
```

```powershell
# Windows PowerShell: the two lines must show the same checksum
(Get-FileHash .\envy-black-veil-0.1.0-x86_64.iso -Algorithm SHA256).Hash.ToLower()
Select-String envy-black-veil-0.1.0-x86_64.iso .\SHA256SUMS.txt
```

To check that the checksums themselves were made by this repository's release workflow, also download `SHA256SUMS.txt.sigstore.json` and run [cosign](https://docs.sigstore.dev/cosign/system_config/installation/):

```sh
cosign verify-blob --bundle SHA256SUMS.txt.sigstore.json \
  --certificate-identity-regexp '^https://github.com/xzchick/envy-black-veil/' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS.txt
```

Whatever you use, give the VM **UEFI firmware**, **4 GB of RAM or more** (6 GB is comfortable), **2+ CPUs**, and a **40 GB** disk if you want to install. The live session logs in by itself as `liveuser`; the desktop's **Install ENVY BLACK VEIL** icon installs it.

## 2. One command: macOS, Linux and Windows

### Windows (Hyper-V)

[`try-black-veil.ps1`](../try-black-veil.ps1) sets up a Hyper-V VM the way BLACK VEIL needs it — Generation 2 (UEFI), Secure Boot with the **Microsoft UEFI Certificate Authority** template, 6 GB of RAM, 4 CPUs, a 40 GB disk and the Default Switch — boots the ISO and opens the VM's window. It needs Windows 10/11 **Pro, Enterprise or Education** with Hyper-V turned on (*Settings → System → Optional features → More Windows features → Hyper-V*), run from an **administrator** PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\try-black-veil.ps1 .\envy-black-veil-0.1.0-x86_64.iso
powershell -ExecutionPolicy Bypass -File .\try-black-veil.ps1            # later: boot what you installed
powershell -ExecutionPolicy Bypass -File .\try-black-veil.ps1 -Remove    # delete the VM and its disk
```

On Windows Home, use VirtualBox or VMware Workstation (section 3).

### macOS and Linux

[`try-black-veil.sh`](../try-black-veil.sh) starts the right VM for you with QEMU — UEFI firmware, a 40 GB virtual disk to install onto, and full hardware acceleration (Apple's Hypervisor framework on macOS, KVM on Linux):

```sh
# macOS (Apple Silicon): brew install qemu
./try-black-veil.sh envy-black-veil-0.1.0-aarch64.iso

# Linux (x86_64): sudo apt install qemu-system ovmf   (Fedora: sudo dnf install qemu-kvm edk2-ovmf)
./try-black-veil.sh envy-black-veil-0.1.0-x86_64.iso

# Later: boot what you installed (no ISO)
./try-black-veil.sh
```

## 3. Your platform's own VM apps

> On every change CI boots, installs and re-boots BLACK VEIL in QEMU/KVM with UEFI firmware, with and without Secure Boot (Microsoft's keys, as Hyper-V and most PCs have them), and the aarch64 ISO is installed and booted the same way on an Apple Silicon Mac. On Windows, CI creates the Hyper-V VM with `try-black-veil.ps1` and checks every setting (GitHub's machines can't start it). The other apps below are each one's standard way to run an AlmaLinux 10 KDE live ISO; they aren't machine-tested.

### macOS

- **UTM** (free, [mac.getutm.app](https://mac.getutm.app)) — *Create a New Virtual Machine* → **Virtualize** → **Linux** → choose the **aarch64** ISO (Apple Silicon) → 6 GB RAM, 4 cores → 40 GB disk → Save → ▶. On an Intel Mac choose the x86_64 ISO. After installing, remove the ISO from the VM's CD drive.
- **Parallels Desktop** / **VMware Fusion** — new VM from an image file, choose the aarch64 ISO on Apple Silicon (x86_64 on Intel), OS type "Other Linux" / "Red Hat 64-bit", UEFI.

### Windows

- **Hyper-V** (Windows Pro/Enterprise) — *New Virtual Machine* → **Generation 2** → 6144 MB → *Default Switch* → new 40 GB disk → install from the x86_64 ISO. Then *Settings → Security*: keep Secure Boot on with the **Microsoft UEFI Certificate Authority** template; BLACK VEIL boots with AlmaLinux's signed boot chain, and CI checks it with Secure Boot on. (`try-black-veil.ps1` sets all of this for you.)
- **VirtualBox** (free) — *New* → ISO: the x86_64 ISO → Type **Linux**, Version **Red Hat (64-bit)** → tick **Enable EFI** → 6144 MB, 4 CPUs → 40 GB disk. In *Display*, give it 128 MB video memory with **VMSVGA**.
- **VMware Workstation Pro** (free for personal use) — *Create a New Virtual Machine* → the x86_64 ISO → **Red Hat Enterprise Linux 9 64-bit** (or "Other Linux 6.x 64-bit") → 40 GB → *Customize Hardware*: 6 GB RAM, 4 CPUs; *Options → Advanced → Firmware: UEFI*.
- **WSL** can't boot a desktop OS ISO; use one of the above.

### Linux

- **GNOME Boxes** — *+* → *Install from File* → the x86_64 ISO; give it 6 GB and 40 GB.
- **virt-manager** — *New VM* → local install media → the ISO → OS "AlmaLinux 10" (or "Red Hat Enterprise Linux 10") → 6144 MB, 4 CPUs, 40 GB → tick *Customize configuration before install* → *Overview → Firmware: UEFI*.

## 4. On real hardware

Write the ISO to a USB stick of 4 GB or more, raw:
- **Fedora Media Writer** on Windows, macOS or Linux;
- **balenaEtcher**;
- **Rufus** in *DD image* mode;
- `dd`.

Then boot from it. Secure Boot can stay on.

The walkthrough is in [install-to-external-drive.md](install-to-external-drive.md). It also covers keeping your changes on the stick, installing onto an external SSD you can carry between PCs, and what to do on PCs that refuse Microsoft's third-party certificate.

- **Intel Macs** boot it from USB when you hold **⌥ Option** at power-on.
  - Macs with a T2 chip need *Startup Security Utility → Allow booting from external media*.
  - They also need Secure Boot set to *No Security*.
- **Apple Silicon Macs** can't boot other operating systems from USB this way. Use a VM: UTM is free and runs the aarch64 ISO at near-native speed.
- **Tell us how it went**: open **Hardware Report** from BLACK VEIL's menu and paste what it writes into a [hardware report](https://github.com/xzchick/envy-black-veil/issues/new?template=hardware-report.yml).

## What to expect

- The live desktop opens on its own, with the ENVY look. Nothing is written to any disk until you run the installer.
- No accounts, no telemetry, nothing phoning home on a timer; SSH, printing and network discovery are off, and the firewall opens nothing.
- Add ENVY apps after installing: `envy-tools install vault veil hypothesis`, or the [ENVY Tools](https://github.com/xzchick/envy-tools) app.
