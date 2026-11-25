# ENVY BLACK VEIL — live ISO kickstart
# AlmaLinux 10 + KDE Plasma 6, themed in the ENVY neon palette.
#
# Built on AlmaLinux's own live-media recipe (github.com/AlmaLinux/sig-livemedia,
# kickstarts/10/x86_64/almalinux-live-kde.ks) with the ENVY identity, privacy
# defaults and the runtime ENVY apps need layered on top.
#
# One kickstart for x86_64 and aarch64: build/build-iso.sh drops the lines marked
# "x86_64-only" when building for other architectures.
#
# This builds JUST THE OS: a live, installable KDE desktop. The ENVY apps are not
# bundled; add any of them after install with `envy-tools install` (or the
# standalone ENVY Tools app). Build it with:  sudo ./build/build-iso.sh
#version=DEVEL

# --- Live system --------------------------------------------------------------
xconfig --startxonboot
keyboard 'us'
lang en_US.UTF-8
timezone Etc/UTC --utc
# Root is locked. The live session's user comes from livesys-scripts at boot,
# and the installer creates the real account on the installed system.
rootpw --lock
network --bootproto=dhcp --device=link --activate
shutdown

# --- Package sources ----------------------------------------------------------
url --url=https://repo.almalinux.org/almalinux/10/BaseOS/$basearch/os/
repo --name="appstream" --baseurl=https://repo.almalinux.org/almalinux/10/AppStream/$basearch/os/
repo --name="extras" --baseurl=https://repo.almalinux.org/almalinux/10/extras/$basearch/os/
repo --name="crb" --baseurl=https://repo.almalinux.org/almalinux/10/CRB/$basearch/os/
# KDE Plasma 6 and the live-session scripts come from EPEL.
repo --name="epel" --baseurl=https://dl.fedoraproject.org/pub/epel/10z/Everything/$basearch/
# The ENVY identity packages, built by build/build-iso.sh into this local repo.
repo --name="envy-local" --baseurl=file:///srv/envy-black-veil/repo

# --- Security defaults (privacy-first) ---------------------------------------
selinux --enforcing
# The firewall is on and opens nothing: no SSH or Cockpit (AlmaLinux's defaults)
# and no mDNS (AlmaLinux's KDE image opens it). DHCPv6 replies stay allowed.
firewall --enabled --remove-service=ssh --remove-service=cockpit
services --disabled="sshd" --enabled="NetworkManager,firewalld"

# --- Image layout (the live root filesystem livemedia-creator builds) --------
bootloader --location=none
zerombr
clearpart --all --initlabel
part / --size=10238

%packages
# Kernel
kernel
kernel-modules
kernel-modules-extra

# The live installer (Anaconda, the same one AlmaLinux's own live media uses)
anaconda
anaconda-install-env-deps
anaconda-live
@anaconda-tools
-fcoe-utils
-sdubby

# Live-media plumbing
dracut-live
glibc-all-langpacks
livesys-scripts
memtest86+		# x86_64-only (lorax's x86 boot menu needs it)
plymouth-system-theme
plymouth-plugin-script
plymouth-plugin-label

# KDE Plasma 6 desktop (from EPEL)
@^kde-desktop-environment
@standard
dolphin
konsole
kate
okular
gwenview
ark
spectacle
kcalc
plasma-systemmonitor
firefox
fuse
epel-release
# drop the tracker indexers gtk3 pulls in
-tracker-miners
-tracker
# BLACK VEIL's login screen is SDDM with the ENVY theme. Plasma 6's group also pulls
# in the newer Plasma Login Manager; with it installed, livesys would set the live
# auto-login up there instead of in SDDM.
-plasma-login-manager
-kde-settings-plasmalogin
# KDE Connect pairs phones over the network (it listens on port 1716 and announces
# itself with mDNS): not on by default in a privacy-first OS. Install it if you want it.
-kde-connect
-kdeconnectd
-kde-connect-libs

# The runtime every ENVY app needs, so `envy-tools install` works offline-first
python3
python3-pip
python3-cryptography
python3-pyqt6
git

# The ENVY identity: theme, defaults, release file and envy-tools
envy-black-veil-theme
envy-black-veil-release

# Firmware for common laptop audio
alsa-sof-firmware

# Nothing that phones home or listens by default
-PackageKit-command-not-found
%end

# --- Finishing touches on the built image ------------------------------------
%post --erroronfail
# Live session: livesys creates the live user and logs it into Plasma.
systemctl enable livesys.service
systemctl enable livesys-late.service
sed -i 's/^livesys_session=.*/livesys_session="kde"/' /etc/sysconfig/livesys

# EPEL packages SDDM disabled; the desktop needs it.
systemctl enable sddm.service

# tmpfs for /tmp and /var/tmp, so caches don't fill the live overlay
systemctl enable tmp.mount
cat >> /etc/fstab << EOF
vartmp   /var/tmp    tmpfs   defaults   0  0
EOF

# Privacy: nothing listens on the network by default. Printing and network
# discovery stay installed but off until you turn them on.
# (Cockpit comes in with the installer's dependencies; its socket would listen on 9090.)
for unit in cups.service cups.socket cups-browsed.service avahi-daemon.service avahi-daemon.socket \
            cockpit.socket cockpit.service; do
    systemctl disable "$unit" 2>/dev/null || :
done

# The ENVY boot splash and login screen
plymouth-set-default-theme envy-black-veil
install -d -m 0755 /etc/sddm.conf.d
cat > /etc/sddm.conf.d/10-envy.conf << 'EOF'
[Theme]
Current=envy-black-veil
EOF

# A name of its own: installed systems start as black-veil. The live session
# renames itself to localhost-live at boot, then runs livesys's hook for derived
# spins, which names it back.
echo black-veil > /etc/hostname
install -d -m 0755 /var/lib/livesys
cat > /var/lib/livesys/livesys-session-extra << 'EOF'
# ENVY BLACK VEIL live-session extras (sourced by livesys at first live boot; the
# installer copies the untouched image, so none of this reaches installed systems)
hostnamectl set-hostname black-veil
# The live user logs straight into Plasma through SDDM.
mkdir -p /etc/sddm.conf.d
cat > /etc/sddm.conf.d/90-envy-live-autologin.conf << EOT
[Autologin]
User=liveuser
Session=plasma.desktop
EOT
EOF

# The installer: livesys's KDE setup puts /usr/share/applications/liveinst.desktop
# on the live user's desktop, menu and favourites at boot, so name it here. (Don't
# create /home/liveuser now: livesys would then skip /etc/skel, and with it the
# ENVY colours.) Icon fix as in AlmaLinux's live media.
cp -a /usr/share/icons/hicolor/scalable/apps/org.fedoraproject.AnacondaInstaller.svg \
  /usr/share/icons/hicolor/48x48/apps/ 2>/dev/null || :
sed -i 's/^Name=.*/Name=Install ENVY BLACK VEIL/' /usr/share/applications/liveinst.desktop

# Welcome note for the first terminal
cat > /etc/motd << 'EOF'

  ENVY BLACK VEIL  —  a Linux world of my own.

  This is just the OS. Add any ENVY app whenever you want:
      envy-tools list
      envy-tools install vault veil hypothesis

EOF

# Housekeeping, as AlmaLinux's live media does it
rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux-10 2>/dev/null || rpm --import /etc/pki/rpm-gpg/RPM-GPG-KEY-AlmaLinux || :
rm -f /var/lib/rpm/__db*
rm -f /core*
rm -f /var/lib/systemd/random-seed
echo 'File created by kickstart. See systemd-update-done.service(8).' | tee /etc/.updated >/var/.updated
rm -f /boot/*-rescue*
systemctl disable network 2>/dev/null || :
rm -f /etc/machine-id
touch /etc/machine-id
dnf config-manager --enable crb || :

echo "Packages in the ENVY BLACK VEIL image:"
rpm -qa | sort
%end
