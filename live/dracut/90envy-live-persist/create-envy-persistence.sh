#!/bin/sh
# shellcheck disable=SC1091  # dracut's library, in the initramfs
# create-envy-persistence: on the first "keep changes" boot from a BLACK VEIL USB
# stick, turn the stick's free space into its persistent storage.
#
# dracut's initqueue runs this with the live medium's /dev/disk/by-label path,
# before dmsquash-live mounts the live system. It acts only when all of these hold:
#   - the kernel command line asks for rd.live.overlay=LABEL=<label>, and no
#     filesystem has that label yet;
#   - the live system is on a partition of a writable disk that holds the whole
#     BLACK VEIL ISO it booted from, written to it raw (by Fedora Media Writer,
#     balenaEtcher, Rufus in DD mode or dd): the disk itself reads as that ISO;
#   - there's at least 1 GiB free after the ISO.
# Then it adds a partition in that space, formats it ext4 with the label, and makes
# the OverlayFS directories dmsquash-live looks for. Anything else (a DVD, a VM's
# CD drive, a stick with no room, a read-only one) is left untouched, and the live
# system runs without persistence, as the normal boot entry does.

command -v getarg > /dev/null || . /lib/dracut-lib.sh

if getargbool 0 rd.live.debug; then
    exec >> /run/initramfs/create-envy-persistence.log 2>&1
    set -x
fi

skip() {
    info "BLACK VEIL persistence: $*; this boot keeps no changes"
    exit 0
}

overlay=$(getarg rd.live.overlay=)
case "$overlay" in
    LABEL=?*) ;;
    *) exit 0 ;;
esac
label=${overlay#LABEL=}
label=${label%%:*}

# Set up already (on this stick or another disk): nothing to do.
if [ -e "/dev/disk/by-label/$label" ] || blkid -L "$label" > /dev/null 2>&1; then
    exit 0
fi

livedev=$(readlink -f "$1")
[ -b "$livedev" ] || skip "the live medium $1 isn't a block device"
part_sys=/sys/class/block/${livedev##*/}
[ -f "$part_sys/partition" ] || skip "the live system isn't on a partition (a DVD, or an ISO file)"
disk_sys=$(readlink -f "$part_sys/..")
disk=/dev/${disk_sys##*/}
read -r ro < "$disk_sys/ro"
[ "$ro" = 0 ] || skip "$disk is read-only"
# The whole ISO written to the device: the disk itself reads as the ISO it booted from.
[ "$(blkid -p -o value -s TYPE "$disk" 2> /dev/null)" = iso9660 ] \
    || skip "$disk holds more than a BLACK VEIL ISO; leaving it alone"
[ "$(blkid -p -o value -s LABEL "$disk" 2> /dev/null)" = "$(blkid -o value -s LABEL "$livedev" 2> /dev/null)" ] \
    || skip "$disk isn't the ISO this system booted from"

# The partition table, from parted's machine-readable listing:
#   /dev/sdb:<size>s:<transport>:<logical sector size>:<physical>:<gpt|msdos>:<model>:;
#   <number>:<start>s:<end>s:<size>s:<filesystem>:<name>:<flags>;
listing=$(parted --script --machine "$disk" unit s print 2> /dev/null) || skip "parted can't read $disk"
last=0 count=0 sectors=0 lss=0 table=
while IFS=: read -r f1 f2 f3 f4 f5 f6 f7; do
    case "$f1" in
        "$disk") sectors=${f2%s} lss=$f4 table=$f6 ;;
        [0-9]*)
            count=$((count + 1))
            [ "${f3%s}" -gt "$last" ] && last=${f3%s}
            ;;
    esac
done << EOF
$listing
EOF
: "$f5" "$f7"                                    # (unused fields)
case "$table" in
    gpt) name=$label ;;
    msdos)
        [ "$count" -lt 4 ] || skip "$disk has no free primary partition"
        name=primary
        ;;
    *) skip "$disk has no partition table parted understands" ;;
esac
[ "$lss" -gt 0 ] && [ "$sectors" -gt 0 ] || skip "parted didn't report $disk's size"

align=$((1048576 / lss))                         # partitions start on a 1 MiB boundary
start=$(((last / align + 1) * align))
room=$((sectors - 34 - start))                   # 34: the GPT's backup table at the very end
[ "$room" -ge $((1073741824 / lss)) ] || skip "less than 1 GiB free on $disk"

info "BLACK VEIL persistence: making $((room / (1048576 / lss))) MiB of $disk into '$label' (first boot only)"
# --fix: an ISO written to a bigger stick still has its GPT's backup table where the
# ISO ended; parted moves it to the end of the stick, so the free space can be used.
if ! parted --script --fix "$disk" unit s mkpart "$name" ext4 "${start}s" 100%; then
    warn "BLACK VEIL persistence: couldn't add a partition to $disk; this boot keeps no changes"
    exit 0
fi
udevadm settle

# The new partition: the last one on the disk, starting where it was asked to (or after).
new='' best=0 want=$((start * lss / 512))       # sysfs counts 512-byte sectors
for p in "$disk_sys"/*/partition; do
    [ -f "$p" ] || continue
    d=${p%/partition}
    read -r s < "$d/start"
    if [ "$s" -ge "$want" ] && [ "$s" -ge "$best" ]; then
        best=$s
        new=/dev/${d##*/}
    fi
done
if [ ! -b "$new" ] || ! mkfs.ext4 -q -F -L "$label" "$new"; then
    warn "BLACK VEIL persistence: couldn't format the new partition ${new:-on $disk}; this boot keeps no changes"
    exit 0
fi

# What dmsquash-live looks for there: <rd.live.dir>/overlay-<ISO label>-<ISO UUID>,
# the OverlayFS upper layer, with its work directory next to it.
live_dir=$(getarg rd.live.dir=)
[ -n "$live_dir" ] || live_dir=LiveOS
iso_label=$(blkid -s LABEL -o value "$1")
iso_uuid=$(blkid -s UUID -o value "$1")
mnt=/run/initramfs/envy-persist
mkdir -p "$mnt"
upper=$mnt/$live_dir/overlay-$iso_label-$iso_uuid
if mount -t ext4 "$new" "$mnt"; then
    mkdir -p "$mnt/$live_dir/ovlwork" "$upper"
    # The upper directory becomes the live system's / , so it needs /'s SELinux label
    # (root_t): unlabeled, every confined service would be denied the root directory.
    # (No policy is loaded yet in the initramfs, so the label is written as is.)
    setfattr -n security.selinux -v system_u:object_r:root_t:s0 "$upper" \
        || warn "BLACK VEIL persistence: couldn't set the SELinux label of $upper"
    umount "$mnt"
fi
rmdir "$mnt" 2> /dev/null
udevadm settle
info "BLACK VEIL persistence: ready on $new"
exit 0
