#!/usr/bin/env bash
# try-black-veil.sh — try ENVY BLACK VEIL in a virtual machine, on macOS or Linux.
#
#   ./try-black-veil.sh envy-black-veil-0.1.0-aarch64.iso   # Apple Silicon Mac / ARM Linux
#   ./try-black-veil.sh envy-black-veil-0.1.0-x86_64.iso    # Intel Mac / x86 Linux
#   ./try-black-veil.sh                                      # boot what you installed
#
# Opens the live desktop in a window. Nothing on your computer changes beyond two
# files in the current folder: a 40 GB virtual disk (black-veil-disk.qcow2, which
# only grows as it's used) and the VM's firmware settings. To install, double-click "Install ENVY BLACK VEIL"
# on the live desktop and pick the 40 GB virtual disk; afterwards, run this
# script without an ISO to boot the installed system.
#
# Needs QEMU:  macOS: brew install qemu     Debian/Ubuntu: sudo apt install qemu-system ovmf
#              Fedora/AlmaLinux: sudo dnf install qemu-kvm edk2-ovmf   Arch: sudo pacman -S qemu-full edk2-ovmf
# It uses Apple's Hypervisor.framework on macOS and KVM on Linux, so a VM of your
# own computer's architecture runs at near-native speed. (Running the x86_64 ISO
# on an Apple Silicon Mac works but is emulated and slow: use the aarch64 ISO.)
#
# Env: DISK (disk image path), DISK_SIZE (40G), MEM (MiB, 6144), CPUS (4),
#      TRY_HEADLESS=1 (no window; used by CI to smoke-test this script).
set -euo pipefail

die() { printf 'try-black-veil: %s\n' "$*" >&2; exit 1; }
say() { printf '\033[38;5;51m==>\033[0m %s\n' "$*"; }

ISO="${1:-}"
DISK="${DISK:-black-veil-disk.qcow2}"
DISK_SIZE="${DISK_SIZE:-40G}"
MEM="${MEM:-6144}"
CPUS="${CPUS:-4}"
OS="$(uname -s)"
HOST_ARCH="$(uname -m)"
[ "$HOST_ARCH" = "arm64" ] && HOST_ARCH=aarch64

# The VM's architecture: from the ISO's name, else this computer's.
case "$ISO" in
    *aarch64*) ARCH=aarch64 ;;
    *x86_64*)  ARCH=x86_64 ;;
    *)         ARCH="$HOST_ARCH" ;;
esac
[ -z "$ISO" ] || [ -f "$ISO" ] || die "no such ISO: $ISO"
[ -n "$ISO" ] || [ -f "$DISK" ] || die "give the ISO to boot, e.g.: $0 envy-black-veil-0.1.0-${HOST_ARCH}.iso"

QEMU="qemu-system-$ARCH"
command -v "$QEMU" >/dev/null || die "$QEMU isn't installed. macOS: brew install qemu · Debian/Ubuntu: sudo apt install qemu-system ovmf · Fedora: sudo dnf install qemu-kvm edk2-ovmf"
command -v qemu-img >/dev/null || die "qemu-img isn't installed (it comes with QEMU)."

# UEFI firmware: wherever this platform's QEMU or distro keeps it.
share="$(dirname "$(command -v "$QEMU")")/../share/qemu"
if [ "$ARCH" = aarch64 ]; then
    code_candidates=("$share/edk2-aarch64-code.fd" /usr/share/AAVMF/AAVMF_CODE.fd
                     /usr/share/edk2/aarch64/QEMU_EFI-pflash.raw /usr/share/qemu/edk2-aarch64-code.fd)
    vars_candidates=("$share/edk2-arm-vars.fd" /usr/share/AAVMF/AAVMF_VARS.fd
                     /usr/share/edk2/aarch64/vars-template-pflash.raw /usr/share/qemu/edk2-arm-vars.fd)
else
    code_candidates=("$share/edk2-x86_64-code.fd" /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd
                     /usr/share/edk2/ovmf/OVMF_CODE.fd /usr/share/edk2/x64/OVMF_CODE.4m.fd /usr/share/qemu/edk2-x86_64-code.fd)
    vars_candidates=("$share/edk2-i386-vars.fd" /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd
                     /usr/share/edk2/ovmf/OVMF_VARS.fd /usr/share/edk2/x64/OVMF_VARS.4m.fd /usr/share/qemu/edk2-i386-vars.fd)
fi
CODE=""; for f in "${code_candidates[@]}"; do [ -f "$f" ] && { CODE="$f"; break; }; done
VARS_TEMPLATE=""; for f in "${vars_candidates[@]}"; do [ -f "$f" ] && { VARS_TEMPLATE="$f"; break; }; done
[ -n "$CODE" ] && [ -n "$VARS_TEMPLATE" ] || die "couldn't find UEFI firmware for $ARCH (install edk2-ovmf / ovmf / qemu-efi-aarch64)."

# The VM keeps its own firmware settings next to its disk, so an installed system
# stays bootable between runs.
VARS="${DISK%.qcow2}-$ARCH-vars.fd"
if [ ! -f "$VARS" ]; then
    cp "$VARS_TEMPLATE" "$VARS"
    # aarch64 pflash images must be exactly 64 MiB
    if [ "$ARCH" = aarch64 ] && [ "$(wc -c < "$VARS")" -lt 67108864 ]; then
        truncate -s 64M "$VARS" 2>/dev/null || dd if=/dev/zero bs=1 count=0 seek=67108864 of="$VARS" 2>/dev/null
    fi
fi
if [ ! -f "$DISK" ]; then
    say "Creating a $DISK_SIZE virtual disk to install onto: $DISK (grows only as it's used)"
    qemu-img create -q -f qcow2 "$DISK" "$DISK_SIZE"
fi

# Hardware acceleration when the VM matches this computer.
accel=(-accel tcg,thread=multi -cpu max)
if [ "$ARCH" = "$HOST_ARCH" ]; then
    if [ "$OS" = Darwin ]; then
        accel=(-accel hvf -cpu host)
    elif [ -w /dev/kvm ]; then
        accel=(-accel kvm -cpu host)
    else
        say "warning: /dev/kvm isn't usable (are you in the kvm group?); the VM will be slow."
    fi
else
    say "warning: running a $ARCH VM on a $HOST_ARCH computer is emulated and slow. Use the ${HOST_ARCH} ISO if you can."
fi

if [ "$ARCH" = aarch64 ]; then
    machine=(-machine virt)
    display_dev=(-device virtio-gpu-pci,edid=on,xres=1600,yres=900)
    cdrom=(-drive "file=$ISO,if=none,id=cd0,media=cdrom,readonly=on" -device virtio-scsi-pci,id=scsi0 -device scsi-cd,drive=cd0)
else
    machine=(-machine q35)
    display_dev=(-vga none -device virtio-vga,edid=on,xres=1600,yres=900)
    cdrom=(-drive "file=$ISO,media=cdrom,readonly=on")
fi
[ -n "$ISO" ] || cdrom=()
display=()
[ "${TRY_HEADLESS:-0}" = 1 ] && display=(-display none)

say "Starting ENVY BLACK VEIL ($ARCH, ${accel[1]%%,*}, ${MEM} MiB, ${CPUS} CPUs)${ISO:+ from $(basename "$ISO")}"
[ -n "$ISO" ] && say "The live desktop logs in by itself. Close the window to stop the VM."
exec "$QEMU" -name "ENVY BLACK VEIL" "${machine[@]}" "${accel[@]}" -smp "$CPUS" -m "$MEM" \
    -drive "if=pflash,format=raw,readonly=on,file=$CODE" -drive "if=pflash,format=raw,file=$VARS" \
    "${display_dev[@]}" -device qemu-xhci -device usb-kbd -device usb-tablet \
    -drive "file=$DISK,if=virtio" ${cdrom[@]+"${cdrom[@]}"} \
    -nic user,model=virtio-net-pci ${display[@]+"${display[@]}"}
