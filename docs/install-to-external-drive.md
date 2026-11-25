# Boot ENVY BLACK VEIL from an external SSD, HDD or USB drive

This guide covers two different things. Pick the one you want:

1. **Try it** — boot the *live* system from a USB stick, nothing installed, nothing changed on any disk. Good for a look, or to run the installer.
2. **Carry it** — do a *full install* onto an external SSD, HDD or USB drive so BLACK VEIL is a real, persistent, portable OS you can plug into almost any PC and boot. This is the one most people mean by "install it to an external drive."

> **One rule above all:** the installer can see every disk in the machine, including the computer's internal one. When you install to an external drive, select the **external drive** as the target *and* put the bootloader on that **same external drive**. Done right, the host computer's internal disk is never touched, and the external drive boots on its own.

---

## What you need

- The BLACK VEIL ISO — build it with [`build/build-iso.sh`](../build/build-iso.sh) on an AlmaLinux 10 host, or download the one CI builds and boot-tests on every change (the **ISO** workflow's `envy-black-veil-iso` artifact; a signed release is on the roadmap).
- A **USB stick (≥ 4 GB)** to boot the live system from.
- For "Carry it": a separate **external SSD / HDD / USB drive (≥ 32 GB; an SSD is strongly preferred)** to install onto. **Everything on it will be erased.**
- A 64-bit PC that can boot from USB (UEFI, ideally with Secure Boot that you can toggle).

Always check the ISO before writing it:

```sh
sha256sum -c envy-black-veil-0.1.0-x86_64.iso.sha256
```

---

## Step 1 — Write the ISO to the USB boot stick

The ISO is a hybrid image: write it raw to the whole USB device (not a partition, not a file copy).

**Linux**

```sh
# Find the stick's device node (e.g. /dev/sdb) — be certain which one it is:
lsblk -o NAME,SIZE,TYPE,TRAN,MODEL
# Write it (replace sdX with YOUR stick; this erases the stick):
sudo dd if=envy-black-veil-0.1.0-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

**macOS** — use [balenaEtcher](https://etcher.balena.io/) (simplest), or `diskutil list` then `sudo dd if=envy-black-veil-….iso of=/dev/rdiskN bs=4m` after `diskutil unmountDisk /dev/diskN`.

**Windows** — use [Fedora Media Writer](https://fedoraproject.org/workstation/download) or balenaEtcher. (Rufus works too; choose **DD image** mode if asked.)

---

## Step 2 — Boot the live system

1. Plug the USB stick in. Turn the PC on and open the one-time **boot menu** (often **F12**, **F11**, **F9**, or **Esc** — your PC shows which at power-on).
2. Choose the USB stick. Prefer the **UEFI** entry if both a UEFI and a legacy one are listed.
3. If it won't boot, enter firmware setup and **disable Secure Boot** (this image isn't signed for every vendor's key), then try again.
4. BLACK VEIL boots to the ENVY desktop, auto-logged-in as the live user (`liveuser`). Nothing is written to any disk yet.

From here you can just use it, or run the installer to carry it onto an external drive.

---

## Step 3 — "Carry it": install onto the external SSD/HDD/USB

> Plug in your **target external drive now**, alongside the USB boot stick. You will choose it explicitly.

1. Launch **Install ENVY BLACK VEIL** from the desktop (or the menu). This is Anaconda, AlmaLinux's own installer (Calamares isn't packaged for AlmaLinux 10).
2. **Language** — pick it, then **Continue**. You land on the **Installation Summary**.
3. **Installation Destination — this is the important screen.**
   - Under **Local Standard Disks**, select **only your external drive** (identify it by size and model, e.g. *Samsung T7 1TB*). Click the internal disk to **un-select** it if it's ticked. Anaconda only ever touches the disks selected here.
   - Leave **Storage Configuration** on **Automatic** to give the whole external drive to BLACK VEIL (you'll be offered to reclaim space if it isn't empty — delete everything on *that* drive).
   - Tick **Encrypt my data** for full-disk LUKS encryption (recommended for a drive you carry). The passphrase you set is the one the ENVY boot splash asks for.
   - **Boot loader:** click **Full disk summary and boot loader…** at the bottom and make sure the boot device is the **external drive**. With only the external drive selected, Anaconda puts the EFI system partition and GRUB there. Your internal disk is never written; the firmware just gets a boot-menu entry, which is harmless.
4. **User Creation** — your name, username and a strong password; tick **Make this user administrator**. The installed system does **not** auto-login (only the live session does). Root stays locked.
5. Check the summary hub has no warnings, then **Begin Installation**.
6. When it finishes, **shut down**, remove the USB boot stick (you can keep the external drive plugged in), and boot from the external drive via the firmware boot menu.

### Boot it on other computers

Because the bootloader lives on the external drive's own EFI partition — including AlmaLinux's standard fallback loader, `EFI/BOOT/BOOTX64.EFI`, which is what another PC looks for — you can move the drive to another PC and boot it from that PC's boot menu. Notes:

- **UEFI only.** The portable install is built for UEFI. On a strictly legacy-BIOS machine it may not boot.
- **Secure Boot** may need to be off on each host, as above.
- **First boot on new hardware** re-detects graphics and network; give it a moment. KDE Plasma falls back to software rendering if a GPU driver is missing.
- **USB sticks are slow and wear out.** A flash *stick* will run BLACK VEIL but feel sluggish and age faster under a full OS; an external **SSD** (USB-C/NVMe enclosure) is night-and-day better and is what this is meant for.

---

## Step 4 — Add your ENVY tools

BLACK VEIL ships as **just the OS**. Once it's installed and you're online, open a terminal and add whatever you want:

```sh
envy-tools list                       # everything available
envy-tools install vault veil hypothesis
envy-tools install all                # the whole suite
```

Each tool installs into one isolated environment and appears in the KDE menu. After that they run fully offline. (You can also use the standalone [ENVY Tools](https://github.com/xzchick/envy-tools) app, which installs each app's signed release build.) See [customizing.md](customizing.md).

---

## Safety checklist

- [ ] I identified the **target external drive** by size/model, not by guesswork.
- [ ] In **Installation Destination**, only the external drive is selected.
- [ ] The **boot loader** device is that same external drive, not the internal disk.
- [ ] I have nothing I need on the target drive — it will be **erased**.
- [ ] (Recommended) I enabled **encryption** for a drive I'll carry around.

If any box is unchecked, stop before clicking Install.
