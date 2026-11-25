#!/usr/bin/env python3
"""lorax's live-ISO templates with BLACK VEIL's additions (build/build-iso.sh uses this).

    lorax-templates.py DIR       copy lorax's templates to DIR and change them:
      1. every live boot menu (UEFI on both architectures, BIOS on x86_64) gets
         "Start ENVY BLACK VEIL ... and keep changes on this USB stick": the normal
         live boot plus rd.live.overlay=LABEL=ENVY-PERSIST, which the
         envy-live-persist dracut module and dracut's dmsquash-live turn into
         persistence on a USB stick (see live/dracut/);
         (the aarch64 menu's basic-graphics entry is also called "Start", not
         "Install", as on x86_64: it starts the live system);
      2. the aarch64 ISO gets the layout the x86_64 one already has (a GPT with the
         EFI system partition appended), so written to a USB stick it boots from that
         partition on any UEFI firmware and has a partition table persistence can
         grow into.
    lorax-templates.py --dracut-args
                                 the initramfs arguments for livemedia-creator: lorax's
                                 own for live images, plus envy-live-persist.

It stops with an error if lorax's templates don't look the way this expects, so a
lorax update can't silently drop BLACK VEIL's changes.
"""

import re
import shutil
import sys
from pathlib import Path

PERSIST_LABEL = "ENVY-PERSIST"
PERSIST_ARGS = f"rd.live.overlay=LABEL={PERSIST_LABEL} rd.live.overlay.nouserconfirmprompt"
PERSIST_TITLE = "Start @PRODUCT@ @VERSION@ and keep changes on this USB stick"
DRACUT_MODULE = "envy-live-persist"

# The boot menus to change, relative to the templates' live/ directory.
MENUS = ["config_files/x86/grub2-efi.cfg", "config_files/x86/grub2-bios.cfg",
         "config_files/aarch64/grub2-efi.cfg"]

# aarch64: lorax adds the EFI boot image as a file inside the ISO (CD boot only).
AARCH64_EFI_OLD = 'efiargs += " -eltorito-alt-boot -e {0} -no-emul-boot".format(img)'
# ...as x86_64 does it instead: appended as a GPT partition that El Torito also points at.
AARCH64_EFI_NEW = ('efiargs += " -partition_offset 16 -appended_part_as_gpt'
                   ' -append_partition 2 C12A7328-F81F-11D2-BA4B-00A0C93EC93B {1}/{0}'
                   ' -iso_mbr_part_type EBD0A0A2-B9E5-4433-87C0-68B6B72699C7'
                   ' -eltorito-alt-boot -e --interval:appended_partition_2:all:: -no-emul-boot"'
                   '.format(img, outroot)')


def die(msg: str) -> None:
    sys.exit(f"lorax-templates: {msg}")


def add_persistence_entry(cfg: Path) -> None:
    """Copy the menu's "Start" entry as a "keep changes" one, after "Test this media"."""
    text = cfg.read_text()
    start = re.search(r"^menuentry 'Start @PRODUCT@ @VERSION@' .*?^}\n", text, re.M | re.S)
    anchor = "submenu 'Troubleshooting -->'"
    if not start or anchor not in text or " rd.live.image " not in start.group(0):
        die(f"{cfg}: no 'Start' entry with rd.live.image, or no Troubleshooting submenu")
    if 'set default="1"' not in text or "'Test this media" not in text[start.end():text.index(anchor)]:
        die(f"{cfg}: expected 'Test this media' as the default, second entry")
    entry = (start.group(0)
             .replace("'Start @PRODUCT@ @VERSION@'", f"'{PERSIST_TITLE}'", 1)
             .replace(" rd.live.image ", f" rd.live.image {PERSIST_ARGS} ", 1))
    # After the default (second) entry, so the default stays "Test this media & start".
    i = text.index(anchor)
    text = text[:i] + entry + text[i:]
    cfg.write_text(text.replace("'Install @PRODUCT@ @VERSION@ in basic graphics mode'",
                                "'Start @PRODUCT@ @VERSION@ in basic graphics mode'"))


def hybrid_aarch64(tmpl: Path) -> None:
    text = tmpl.read_text()
    if text.count(AARCH64_EFI_OLD) != 1:
        die(f"{tmpl}: the EFI boot arguments aren't what this script changes")
    tmpl.write_text(text.replace(AARCH64_EFI_OLD, AARCH64_EFI_NEW))


def dracut_args() -> list[str]:
    """livemedia-creator --dracut-arg values: lorax's defaults plus our module.

    livemedia-creator splits each value at its first space into an option and its
    argument, so "--add" and its module list travel together.
    """
    from pylorax.creator import DRACUT_DEFAULT
    args, out, i = list(DRACUT_DEFAULT), [], 0
    if "--add" not in args:
        die("lorax's live dracut arguments have no --add")
    while i < len(args):
        if args[i] == "--add":
            out.append(f"--add {args[i + 1]} {DRACUT_MODULE}")
            i += 2
        else:
            out.append(args[i])
            i += 1
    return out


def main() -> None:
    if sys.argv[1:] == ["--dracut-args"]:
        print("\n".join(dracut_args()))
        return
    if len(sys.argv) != 2:
        die("usage: lorax-templates.py DIR | --dracut-args")
    from pylorax import find_templates
    src = Path(find_templates("/usr/share/lorax"))
    dst = Path(sys.argv[1])
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, symlinks=True)
    for menu in MENUS:
        add_persistence_entry(dst / "live" / menu)
    hybrid_aarch64(dst / "live" / "aarch64.tmpl")
    print(f"lorax templates: {src} -> {dst} (persistence entry, aarch64 USB layout)")


if __name__ == "__main__":
    main()
