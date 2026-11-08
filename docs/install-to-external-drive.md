# Boot ENVY BLACK VEIL from an external SSD, HDD or USB drive

This guide covers two different things. Pick the one you want:

1. **Try it** — boot the *live* system from a USB stick, nothing installed, nothing changed on any disk. Good for a look, or to run the installer.
2. **Carry it** — do a *full install* onto an external SSD, HDD or USB drive so BLACK VEIL is a real, persistent, portable OS you can plug into almost any PC and boot. This is the one most people mean by "install it to an external drive."

> **One rule above all:** the installer can see every disk in the machine, including the computer's internal one. When you install to an external drive, select the **external drive** as the target *and* put the bootloader on that **same external drive**. Done right, the host computer's internal disk is never touched, and the external drive boots on its own.

---

## What you need

- The BLACK VEIL ISO — build it with [`build/build-iso.sh`](../build/build-iso.sh) on a Linux host, or download it from [Releases](https://github.com/xzchick/envy-black-veil/releases).
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
4. BLACK VEIL boots to the ENVY desktop, auto-logged-in as the live user. Nothing is written to any disk yet.

From here you can just use it, or run the installer to carry it onto an external drive.

---

## Step 3 — "Carry it": install onto the external SSD/HDD/USB

> Plug in your **target external drive now**, alongside the USB boot stick. You will choose it explicitly.

1. Launch **Install ENVY BLACK VEIL** from the desktop (or the menu). The ENVY-branded Calamares installer opens.
2. **Welcome / Location / Keyboard** — language, timezone, keyboard. Next through them.
3. **Partitions — this is the important screen.**
   - At the top, find the **"Install to"** / storage-device selector and choose your **external drive** by size and model (e.g. *Samsung T7 1TB*, `/dev/sdc`). Double-check it is **not** the internal disk (often the largest internal NVMe/SATA device).
   - Choose **Erase disk** to give the whole external drive to BLACK VEIL.
   - Tick **Encrypt system** and set a strong passphrase if you want full-disk encryption (recommended for a drive you carry around — it's the LUKS passphrase the ENVY boot splash will ask for).
   - **Bootloader location:** make sure the "Install boot loader on:" option points at the **external drive itself** (its own EFI partition), *not* the internal disk. Calamares defaults to the device you're installing to; just confirm it. This is what makes the drive self-contained and keeps the host PC untouched.
4. **Users** — your name, username, a strong password. The installed system does **not** auto-login (only the live session did).
5. **Summary** — read it. Confirm the target is your external drive and the bootloader goes there too. Then **Install**.
6. When it finishes, **shut down**, remove the USB boot stick (you can keep the external drive plugged in), and boot from the external drive via the firmware boot menu.

### Boot it on other computers

Because the bootloader lives on the external drive's own EFI partition, you can move the drive to another PC and boot it from that PC's boot menu. Notes:

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

Each tool installs into one isolated environment and appears in the KDE menu. After that they run fully offline. See [customizing.md](customizing.md).

---

## Safety checklist

- [ ] I identified the **target external drive** by size/model, not by guesswork.
- [ ] The installer's **"Install to"** is the external drive.
- [ ] The **bootloader location** is that same external drive, not the internal disk.
- [ ] I have nothing I need on the target drive — it will be **erased**.
- [ ] (Recommended) I enabled **encryption** for a drive I'll carry around.

If any box is unchecked, stop before clicking Install.
