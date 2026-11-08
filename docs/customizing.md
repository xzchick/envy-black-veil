# Customizing ENVY BLACK VEIL

## Add or remove ENVY tools

BLACK VEIL is just the OS; the apps are opt-in.

```sh
envy-tools list                       # everything, and what's installed
envy-tools install vault              # add one
envy-tools install vault veil oracle  # add several
envy-tools install all                # the whole suite
envy-tools installed                  # what you have
envy-tools update all                 # reinstall at the latest version
envy-tools remove veil                # take one off
```

Every tool installs into one isolated virtualenv under `~/.local/share/envy-tools/`, drops a launcher in `~/.local/bin`, and adds a KDE menu entry — nothing touches the system Python. Installing needs the network; running the tools never does.

## The ENVY theme

Everything the look is made of lives in [`theme/`](../theme):

| Piece | File | Lands at |
| :--- | :--- | :--- |
| Plasma colours | `plasma/color-schemes/EnvyNeon.colors` | `/usr/share/color-schemes/` |
| Login (SDDM) | `sddm/envy-black-veil/` | `/usr/share/sddm/themes/` |
| Boot splash | `plymouth/envy-black-veil/` | `/usr/share/plymouth/themes/` |
| Boot menu | `grub/envy-black-veil/` | `/boot/grub2/themes/` |
| Terminal | `konsole/Envy.*` | `/usr/share/konsole/` |
| Wallpaper | `wallpaper/envy-black-veil.svg` | `/usr/share/wallpapers/EnvyBlackVeil/` |
| New-user defaults | `skel/.config/` | `/etc/skel/.config/` |

The palette is one set of tokens:

```
BG #050713   PANEL #0a0e22   INK #f2f4ff   MUTED #b9c3df   DIM #6f7898
PINK #ff3db4  CYAN #35e8ff   LAVENDER #ac8cff  VIOLET #8547e8
AMBER #ffb347  GREEN #49e3a6  LINE #1f2547
```

Change a colour in one `.svg` or `.colors` file, rebuild the theme RPM (or copy the file into place on a running system), and the look follows.

### Apply a changed theme on a running system

```sh
# colours
cp theme/plasma/color-schemes/EnvyNeon.colors ~/.local/share/color-schemes/
plasma-apply-colorscheme EnvyNeon
# boot splash
sudo cp -r theme/plymouth/envy-black-veil /usr/share/plymouth/themes/
sudo plymouth-set-default-theme -R envy-black-veil
```

## Defaults and security

- SELinux is **enforcing**, the firewall is **on**, and **nothing listens** (`sshd` and `cups` are off by default). Turn on only what you need.
- The **live** session auto-logs-in; an **installed** system does not (Calamares removes the autologin drop-in).
- For a portable install you carry around, enable **LUKS encryption** in the installer — the ENVY boot splash prompts for the passphrase.
