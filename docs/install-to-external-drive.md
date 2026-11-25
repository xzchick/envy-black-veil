# Run ENVY BLACK VEIL on a real computer: a USB stick, or an external drive

Three ways, from lightest to most permanent:

1. **Try it live.** Boot the live desktop from a USB stick. Nothing is written to any disk, and every boot starts fresh.
2. **Keep changes on the stick.** The same live stick, booted with *keep changes*: your files, settings and installed apps are still there next time.
3. **Carry it.** Do a full, encrypted install onto an external SSD, HDD or USB drive, and boot it on almost any PC. This is what most people mean by "install it to an external drive".

> **The one rule for carrying it:** the installer can see every disk in the computer, including its internal one. Select the **external drive** as the target *and* put the boot loader on that **same external drive**. Done this way, the computer's internal disk is never touched and the external drive boots on its own.

---

## What you need

- **The ISO**, from the [latest release](https://github.com/xzchick/envy-black-veil/releases/latest):
  - `envy-black-veil-0.1.0-x86_64.iso` for PCs and Intel Macs;
  - `envy-black-veil-0.1.0-aarch64.iso` for ARM PCs with UEFI firmware. Apple Silicon Macs can't boot other systems from USB; run BLACK VEIL there in a VM ([try-it.md](try-it.md)).
- **Check it** against the release's `SHA256SUMS.txt` (how to check on Windows, macOS and Linux: [try-it.md](try-it.md#1-get-the-right-iso)).
- **A USB stick of 4 GB or more.** To keep changes on it, use 8 GB or more: everything past the ISO's 2 GB becomes storage.
- For *carry it*: **an external SSD, HDD or USB drive** of 32 GB or more, separate from the stick. An SSD is strongly preferred. **Everything on it will be erased.**
- **A computer that boots from USB with UEFI.** Most PCs from the last ten years do.

---

## Step 1: Write the ISO to the USB stick

The ISO is a disk image: write it to the **whole stick**, as it is. Copying the file onto the stick won't boot, and neither will Rufus's default *ISO image* mode. **Everything on the stick is erased.**

**Windows**: [Fedora Media Writer](https://fedoraproject.org/workstation/download) (*Select .iso file*) or [balenaEtcher](https://etcher.balena.io/). With [Rufus](https://rufus.ie/), choose **Write in DD Image mode** when it asks.

**macOS**: balenaEtcher or Fedora Media Writer, or in Terminal:

```sh
diskutil list                                   # find the stick, e.g. /dev/disk4; be sure it's the right one
diskutil unmountDisk /dev/disk4
sudo dd if=envy-black-veil-0.1.0-x86_64.iso of=/dev/rdisk4 bs=4m   # note the r in rdisk
diskutil eject /dev/disk4
```

**Linux**: Fedora Media Writer, GNOME Disks (*Restore Disk Image…*), or:

```sh
lsblk -o NAME,SIZE,TYPE,TRAN,MODEL              # find the stick, e.g. /dev/sdb; be sure it's the right one
sudo dd if=envy-black-veil-0.1.0-x86_64.iso of=/dev/sdX bs=4M status=progress oflag=sync
```

Ventoy can start the ISO too, but it isn't tested, and *keep changes* doesn't work from Ventoy.

---

## Step 2: Boot from the stick

1. Plug the stick in, turn the computer on and open its one-time **boot menu**. The key is usually **F12**, **F11**, **F10**, **F9**, **F8** or **Esc**, and most PCs show it at power-on. On a Microsoft Surface, hold **Volume Down** while you press power. On an Intel Mac, hold **⌥ Option**.
2. Choose the stick. If it's listed twice, choose the **UEFI** entry.
3. **Leave Secure Boot on.** BLACK VEIL starts through AlmaLinux's signed boot chain, which carries both of Microsoft's third-party signatures (the 2011 and the 2023 certificates). PCs from before and after Microsoft's 2026 certificate change accept it. CI boots every build with Secure Boot on.

   Some PCs refuse it anyway. You may see *Secure Boot violation* or *Verification failed*, or land back in the boot menu. Those PCs trust only Windows out of the box, and the fix is a firmware setting that allows Microsoft's third-party certificate:
   - **Lenovo**: *Security → Secure Boot → Allow Microsoft 3rd Party UEFI CA*.
   - **Surface**: *Security → Secure Boot → Microsoft & 3rd party CA*.
   - **Other makers**: something like *Microsoft UEFI CA*.

   Turn Secure Boot off only when there's no such setting.
4. **Intel Macs with a T2 chip** also need *Startup Security Utility → Allow booting from external media*.
   They also need Secure Boot set to *No Security*: the T2 trusts only Windows' own certificate.

### The boot menu

| Entry | What it does |
| --- | --- |
| **Start ENVY BLACK VEIL** | The live desktop. Changes last until you shut down. |
| **Test this media & start ENVY BLACK VEIL** | Checks the stick first (a few minutes). This is the default, chosen after 60 seconds. |
| **Start ENVY BLACK VEIL and keep changes on this USB stick** | The live desktop, keeping your changes on the stick ([below](#keep-changes-on-the-usb-stick)). New since 0.1.0: in builds from the [ISO workflow](https://github.com/xzchick/envy-black-veil/actions/workflows/iso.yml) now, and in the next release. |
| **Troubleshooting → basic graphics mode** | Use it if the screen stays black or garbled. Some NVIDIA graphics cards need it. |

The live desktop opens by itself, logged in as `liveuser`. Nothing is written to the computer's disks unless you run the installer.

---

## Keep changes on the USB stick

Choose **…and keep changes on this USB stick** in the boot menu.

- **On the first boot**, BLACK VEIL turns the stick's free space (everything past the 2 GB ISO) into a storage partition named `ENVY-PERSIST`.
- **From then on** it keeps whatever you change: files, settings, Wi-Fi networks, and apps you add with `envy-tools` or `dnf`.
- **Every later boot** of that entry carries on where you left off.
- **The plain *Start* entry** still gives you a fresh system, and leaves what you kept alone.

Good to know:

- **It's not encrypted.** Anyone who has the stick can read what you keep on it. For anything private, *carry it* instead (step 3): a full install with **Encrypt my data** is what that's for.
- **It needs a stick written as in step 1, with at least 1 GB free past the ISO.**
  - An 8 GB stick gives you about 6 GB.
  - A DVD, a VM's CD drive or a Ventoy stick starts the same entry without keeping anything.
- **Writing a newer ISO to the stick starts over.** What you kept is erased with the old system.
- **Shut down from the menu** before you pull the stick out.
- **USB sticks are slow and wear out under an operating system's writes.** For daily use, an installed external SSD is far quicker.

---

## Step 3: Carry it: install onto an external SSD, HDD or USB drive

> Plug in your **target external drive now**, next to the USB stick. You'll choose it explicitly.

1. Launch **Install ENVY BLACK VEIL** from the desktop (or the menu). This is Anaconda, AlmaLinux's own installer.
2. **Language**: pick yours, then **Continue**. You land on the **Installation Summary**.
3. **Installation Destination**: this is the important screen.
   - Under **Local Standard Disks**, select **only your external drive**. Identify it by size and model, e.g. *Samsung T7 1TB*. If the internal disk is ticked, click it to **un-select** it. Anaconda only ever touches the disks selected here.
   - Leave **Storage Configuration** on **Automatic** to give the whole external drive to BLACK VEIL. If the drive isn't empty, you'll be offered to reclaim its space: delete everything on *that* drive.
   - Tick **Encrypt my data** for full-disk LUKS2 encryption, recommended for a drive you carry. The ENVY boot splash asks for this passphrase at every start.
   - **Boot loader**: click **Full disk summary and boot loader…** at the bottom and make sure the boot device is the **external drive**.
     - With only the external drive selected, Anaconda puts the EFI system partition and GRUB there.
     - Your internal disk is never written. The firmware just gets a boot-menu entry, which is harmless.
4. **User Creation**: your name, a username and a strong password. Tick **Make this user administrator**. The installed system does **not** log in by itself (only the live session does), and root stays locked.
5. Check the summary has no warnings, then **Begin Installation**.
6. When it finishes, **shut down**, remove the USB stick (keep the external drive plugged in), and boot from the external drive through the boot menu.

### Boot it on other computers

The boot loader lives on the external drive's own EFI partition. That includes the standard fallback loader, `EFI/BOOT/BOOTX64.EFI`, which is what another PC looks for. So you can move the drive to another PC and boot it from that PC's boot menu.

- **UEFI only.** The installed system boots with UEFI, not on a strictly legacy-BIOS machine.
- **Secure Boot** works as in step 2. Each PC must allow Microsoft's third-party certificate.
- **First boot on new hardware** detects the graphics and network again, so give it a moment.
- **USB sticks are slow and wear out.** A flash *stick* runs BLACK VEIL but feels sluggish and ages faster under a full OS. An external **SSD** (a USB-C or NVMe enclosure) is night-and-day better, and is what this is meant for.

---

## Step 4: Add your ENVY tools

BLACK VEIL ships as **just the OS**. Once it's installed and you're online, open a terminal and add whatever you want:

```sh
envy-tools list                       # everything available
envy-tools install vault veil hypothesis
envy-tools install all                # the whole suite
```

Each tool installs into one isolated environment and appears in the KDE menu, and runs fully offline after that. The standalone [ENVY Tools](https://github.com/xzchick/envy-tools) app installs each app's signed release build too. See [customizing.md](customizing.md).

---

## Tell us how it went

Every new computer BLACK VEIL meets teaches it something. A report where everything works is as useful as one where something doesn't.

1. In BLACK VEIL, open **Hardware Report** from the menu, or run `envy-hardware-report` in a terminal.
   - It writes `envy-hardware-report-<date>.md` to your home folder, with this computer's model, CPU, graphics, network, sound and battery, the driver each device uses, and any firmware that failed to load.
   - It leaves out serial numbers, MAC and IP addresses, UUIDs and your user and host names.
   - On a live stick without *keep changes*, the file goes when you shut down, so post it first.
   - BLACK VEIL 0.1.0 came out before the report did. There, get it first:

     ```sh
     curl -fsSLO https://raw.githubusercontent.com/xzchick/envy-black-veil/main/tools/envy-hardware-report
     bash envy-hardware-report
     ```
2. Read the report, then open a **[hardware report](https://github.com/xzchick/envy-black-veil/issues/new?template=hardware-report.yml)**.
3. Paste the report and tick what worked: Secure Boot, the display, Wi-Fi, Bluetooth, sound, webcam, suspend and resume, the installer, the passphrase at boot.

---

## Safety checklist for carrying it

- [ ] I identified the **target external drive** by size and model, not by guesswork.
- [ ] In **Installation Destination**, only the external drive is selected.
- [ ] The **boot loader** device is that same external drive, not the internal disk.
- [ ] I have nothing I need on the target drive: it will be **erased**.
- [ ] (Recommended) I turned on **encryption** for a drive I'll carry around.

If any box is unticked, stop before you click **Begin Installation**.
