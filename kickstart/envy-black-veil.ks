# ENVY BLACK VEIL — live ISO Kickstart
# AlmaLinux 10 + KDE Plasma 6, themed in the ENVY neon palette.
#
# This builds JUST THE OS: a live, installable KDE desktop with the ENVY look and
# the runtime every ENVY tool needs (Python 3 + Qt6 + cryptography). The tools
# themselves are NOT bundled — you add any of them after install with
# `envy-tools install` (see tools/install-envy-tools.sh). That keeps the image
# small and lets you pick only what you want.
#
# Build it on a Linux host with:  sudo ./build/build-iso.sh
# (that script stages the ENVY theme package and the repos this file expects).

# --- Install mode ------------------------------------------------------------
text
eula --agreed
lang en_US.UTF-8
keyboard --vckeymap=us --xlayouts='us'
timezone Etc/UTC --utc

# The live session auto-logs-in as `envy`. The account is unprivileged; the
# installer (Calamares) creates the real user on the installed system.
rootpw --lock
user --name=envy --groups=wheel --gecos="ENVY" --password=envy --plaintext
# Lock down the live defaults the moment you install — see docs/.

# --- Security defaults (privacy-first) --------------------------------------
selinux --enforcing
firewall --enabled
# No listening services by default: nothing phones home, nothing listens.
services --enabled=sddm,NetworkManager,firewalld,chronyd --disabled=sshd,cups

# --- Disk (live rootfs built by livemedia-creator) --------------------------
zerombr
clearpart --all --initlabel
part / --fstype ext4 --size 9216
bootloader --timeout=5 --append="rhgb quiet"

# --- Package repositories ----------------------------------------------------
# AlmaLinux BaseOS/AppStream come from the install tree livemedia-creator is
# pointed at. KDE Plasma 6 and Calamares live in EPEL. The ENVY theme package is
# served from a local repo that build-iso.sh creates next to this kickstart.
repo --name=epel --baseurl=https://dl.fedoraproject.org/pub/epel/10/Everything/x86_64/
repo --name=envy-local --baseurl=file:///run/install/repo/envy-repo

%packages --excludedocs
@core
@base-x
@fonts
@hardware-support
@standard
kernel
dracut-live
grub2-pc
grub2-efi-x64
shim-x64
efibootmgr

# --- KDE Plasma 6 desktop (from EPEL) ---------------------------------------
@kde-desktop
plasma-workspace
plasma-desktop
sddm
sddm-kcm
plymouth
plymouth-system-theme
dolphin
konsole
kate
okular
gwenview
ark
spectacle
kcalc
partitionmanager
plasma-systemmonitor
firefox

# --- Installer ---------------------------------------------------------------
calamares
calamares-branding-envy

# --- ENVY tool runtime (so any ENVY app installs cleanly after setup) -------
python3
python3-pip
python3-devel
python3-cryptography
python3-pyqt6
git

# --- ENVY identity: theme, defaults, release branding ----------------------
envy-black-veil-release
envy-black-veil-theme

# Trim things a privacy-minded, offline-first desktop does not want.
-PackageKit-command-not-found
-abrt
-abrt-addon-ccpp
-sendmail
%end

# --- Finishing touches on the built image -----------------------------------
%post --erroronfail
# Make the ENVY graphical boot splash the default.
plymouth-set-default-theme envy-black-veil || true

# Point SDDM at the ENVY login theme.
install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-envy.conf <<'EOF'
[Theme]
Current=envy-black-veil
EOF

# Make GRUB use the ENVY theme and quiet, branded boot.
if [ -f /boot/grub2/themes/envy-black-veil/theme.txt ]; then
    sed -i 's|^GRUB_TERMINAL_OUTPUT=.*||' /etc/default/grub || true
    grep -q '^GRUB_THEME=' /etc/default/grub \
        && sed -i 's|^GRUB_THEME=.*|GRUB_THEME=/boot/grub2/themes/envy-black-veil/theme.txt|' /etc/default/grub \
        || echo 'GRUB_THEME=/boot/grub2/themes/envy-black-veil/theme.txt' >> /etc/default/grub
fi

# Welcome note for the first terminal.
cat > /etc/motd <<'EOF'

  ENVY BLACK VEIL  —  a Linux world of my own.

  This is just the OS. Add any ENVY tool whenever you want:
      envy-tools list
      envy-tools install vault veil hypothesis

EOF

# The live user should land straight on the desktop.
install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/20-autologin.conf <<'EOF'
[Autologin]
User=envy
Session=plasma
EOF
%end
