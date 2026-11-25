#!/bin/sh
# shellcheck disable=SC1091,SC2154  # dracut's library and its $root, in the initramfs
# When the kernel command line asks for persistence (rd.live.overlay=LABEL=...),
# queue create-envy-persistence for the live medium as soon as udev finds it.
# (A pre-udev hook: dracut sources it, so it must not exit.)

command -v getarg > /dev/null || . /lib/dracut-lib.sh

case "$(getarg rd.live.overlay=)" in
    LABEL=?*)
        case "$root" in
            live:/dev/*)
                printf 'SYMLINK=="%s", RUN+="/sbin/initqueue --settled --onetime --unique /sbin/create-envy-persistence %s"\n' \
                    "${root#live:/dev/}" "${root#live:}" >> /etc/udev/rules.d/95-envy-live-persist.rules
                ;;
        esac
        ;;
esac
