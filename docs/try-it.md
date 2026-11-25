# Try ENVY BLACK VEIL on your computer — Windows, macOS or Linux

Two ways, from safest to most real:

1. **In a virtual machine** — BLACK VEIL runs in a window on your current system. Nothing on your computer changes. Best for a first look, and you can even install it onto the VM's virtual disk.
2. **From a USB stick** — boot your actual computer into the live desktop. Nothing is written to your disks unless you run the installer. See [install-to-external-drive.md](install-to-external-drive.md).

## 1. Get the right ISO

| Your computer | ISO to use |
| --- | --- |
| Windows PC, Linux PC, Intel Mac | `envy-black-veil-0.1.0-x86_64.iso` |
| Apple Silicon Mac (M1–M4), ARM Windows / Linux devices | `envy-black-veil-0.1.0-aarch64.iso` |

Both are built and boot-tested by CI on every change: open the [**ISO** workflow](https://github.com/xzchick/envy-black-veil/actions/workflows/iso.yml), pick the latest green run, and download **envy-black-veil-iso** (x86_64) or **envy-black-veil-iso-aarch64** from its *Artifacts* (needs a free GitHub account; each build is kept 14 days). A signed release download is on the roadmap.

Check it before you use it:

```sh
sha256sum -c envy-black-veil-0.1.0-x86_64.iso.sha256          # Linux
shasum -a 256 -c envy-black-veil-0.1.0-aarch64.iso.sha256     # macOS
```

```powershell
# Windows PowerShell: compare with the .sha256 file
(Get-FileHash .\envy-black-veil-0.1.0-x86_64.iso -Algorithm SHA256).Hash.ToLower()
Get-Content .\envy-black-veil-0.1.0-x86_64.iso.sha256
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

> CI boots, installs and re-boots BLACK VEIL in QEMU/KVM with UEFI firmware on every change. The steps below are each app's standard way to run an AlmaLinux 10 KDE live ISO; they aren't machine-tested by CI.

### macOS

- **UTM** (free, [mac.getutm.app](https://mac.getutm.app)) — *Create a New Virtual Machine* → **Virtualize** → **Linux** → choose the **aarch64** ISO (Apple Silicon) → 6 GB RAM, 4 cores → 40 GB disk → Save → ▶. On an Intel Mac choose the x86_64 ISO. After installing, remove the ISO from the VM's CD drive.
- **Parallels Desktop** / **VMware Fusion** — new VM from an image file, choose the aarch64 ISO on Apple Silicon (x86_64 on Intel), OS type "Other Linux" / "Red Hat 64-bit", UEFI.

### Windows

- **Hyper-V** (Windows Pro/Enterprise) — *New Virtual Machine* → **Generation 2** → 6144 MB → *Default Switch* → new 40 GB disk → install from the x86_64 ISO. Then *Settings → Security*: keep Secure Boot on with the **Microsoft UEFI Certificate Authority** template (BLACK VEIL uses AlmaLinux's signed boot chain), or turn Secure Boot off if it won't start.
- **VirtualBox** (free) — *New* → ISO: the x86_64 ISO → Type **Linux**, Version **Red Hat (64-bit)** → tick **Enable EFI** → 6144 MB, 4 CPUs → 40 GB disk. In *Display*, give it 128 MB video memory with **VMSVGA**.
- **VMware Workstation Pro** (free for personal use) — *Create a New Virtual Machine* → the x86_64 ISO → **Red Hat Enterprise Linux 9 64-bit** (or "Other Linux 6.x 64-bit") → 40 GB → *Customize Hardware*: 6 GB RAM, 4 CPUs; *Options → Advanced → Firmware: UEFI*.
- **WSL** can't boot a desktop OS ISO; use one of the above.

### Linux

- **GNOME Boxes** — *+* → *Install from File* → the x86_64 ISO; give it 6 GB and 40 GB.
- **virt-manager** — *New VM* → local install media → the ISO → OS "AlmaLinux 10" (or "Red Hat Enterprise Linux 10") → 6144 MB, 4 CPUs, 40 GB → tick *Customize configuration before install* → *Overview → Firmware: UEFI*.

## 4. On real hardware

Write the ISO to a USB stick (≥ 4 GB) and boot from it — **Fedora Media Writer** (Windows, macOS, Linux), **balenaEtcher**, **Rufus** in *DD image* mode, or `dd` on Linux. The full walkthrough, including installing onto an external SSD you can carry between PCs, is in [install-to-external-drive.md](install-to-external-drive.md).

- **Intel Macs** boot it from USB by holding **⌥ Option** at power-on. Macs with a T2 chip need *Startup Security Utility → Allow booting from external media* (and Secure Boot set to *No Security* if it won't start).
- **Apple Silicon Macs** can't boot other operating systems from USB this way — use a VM (UTM is free and runs the aarch64 ISO at near-native speed).

## What to expect

- The live desktop opens on its own, with the ENVY look. Nothing is written to any disk until you run the installer.
- No accounts, no telemetry, nothing phoning home on a timer; SSH, printing and network discovery are off, and the firewall opens nothing.
- Add ENVY apps after installing: `envy-tools install vault veil hypothesis`, or the [ENVY Tools](https://github.com/xzchick/envy-tools) app.
