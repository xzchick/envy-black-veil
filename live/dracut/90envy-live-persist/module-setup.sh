#!/bin/bash
# shellcheck disable=SC2154  # dracut sets $moddir and $hostonly
# envy-live-persist: persistence for BLACK VEIL on a USB stick (a dracut module for
# the live image's initramfs).
#
# The live boot menu's "keep changes on this USB stick" entry adds
# rd.live.overlay=LABEL=ENVY-PERSIST to the kernel command line. On the first such
# boot from a stick, create-envy-persistence turns the stick's free space into a
# partition with that label; dracut's dmsquash-live then keeps the live system's
# changes there (an OverlayFS upper directory), on that boot and every later one.

check() {
    # Live images only, never a computer's own (host-only) initramfs; included
    # when the image build asks for it (dracut --add envy-live-persist).
    [[ $hostonly ]] && return 1
    return 255
}

depends() {
    echo dmsquash-live
    return 0
}

installkernel() {
    hostonly='' instmods ext4
}

install() {
    inst_multiple blkid mkdir mkfs.ext4 mount parted readlink rmdir setfattr udevadm umount
    inst_hook pre-udev 26 "$moddir/envy-persist-genrules.sh"
    # The initqueue runs its jobs in name order: create-… runs before
    # dmsquash-live-root mounts the live system and looks for the overlay.
    inst_script "$moddir/create-envy-persistence.sh" /sbin/create-envy-persistence
    dracut_need_initqueue
}
