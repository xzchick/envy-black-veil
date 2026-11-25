# ENVY BLACK VEIL identity packages: the theme and the release identity.
# build/build-iso.sh builds these into a local repo that the kickstart installs,
# so the live image boots fully themed.

%global debug_package %{nil}

Name:           envy-black-veil
Version:        0.1.0
Release:        4%{?dist}
Summary:        ENVY BLACK VEIL identity: theme and release identity
License:        MIT
URL:            https://github.com/xzchick/envy-black-veil
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  librsvg2-tools
BuildRequires:  grub2-tools-extra
BuildRequires:  dejavu-sans-fonts
BuildRequires:  dejavu-sans-mono-fonts

%description
Metapackage shell. Install the envy-black-veil-theme and envy-black-veil-release
subpackages to turn a stock AlmaLinux 10 + KDE Plasma 6 system into ENVY BLACK VEIL.

# ---------------------------------------------------------------------------
%package theme
Summary:        ENVY neon theme for KDE Plasma, SDDM, Plymouth, GRUB and Konsole
Requires:       plymouth
Requires:       plymouth-plugin-script
Requires:       plymouth-plugin-label
Requires:       sddm
Supplements:    (sddm and plymouth)

%description theme
The ENVY neon look: a Plasma colour scheme, an SDDM login theme, a Plymouth boot
splash with a LUKS passphrase prompt, a GRUB menu theme, a Konsole profile and
colour scheme, a desktop wallpaper (made the default once per user), and sensible
dark defaults in /etc/skel.

# ---------------------------------------------------------------------------
%package release
Summary:        ENVY BLACK VEIL release file, envy-tools and the hardware report

%description release
Marks the system as ENVY BLACK VEIL (/etc/envy-black-veil-release), installs
`envy-tools`, the on-demand installer for the ENVY application suite, and
`envy-hardware-report` (the menu's Hardware Report), which describes this computer's
hardware for a BLACK VEIL hardware report without anything that identifies you; and sets
the privacy defaults: no NetworkManager connectivity check, no geolocation lookup
in the installer, and Firefox without telemetry, studies or sponsored content. AlmaLinux's own release package stays in
place, so dnf, repositories and updates keep working exactly as on AlmaLinux 10.

# ---------------------------------------------------------------------------
%package live
Summary:        ENVY BLACK VEIL live media: keep changes on a USB stick
Requires:       attr
Requires:       dracut-live
Requires:       e2fsprogs
Requires:       parted

%description live
A dracut module for the live image's initramfs. The live boot menu's "keep changes
on this USB stick" entry asks for persistence; on its first boot from a USB stick
the module turns the stick's free space into an ext4 partition labelled
ENVY-PERSIST, and dracut's dmsquash-live keeps the live system's changes there.
It only ever adds a partition after a BLACK VEIL ISO written whole to a writable
disk, and never touches a host-only (installed system's) initramfs.

# ---------------------------------------------------------------------------
%prep
%autosetup

%build
# Render the SVG art to the PNGs the themes reference.
rsvg-convert -w 820 -h 300 theme/plymouth/envy-black-veil/logo.svg  -o theme/plymouth/envy-black-veil/logo.png
rsvg-convert -w 48  -h 48  theme/plymouth/envy-black-veil/spark.svg -o theme/plymouth/envy-black-veil/spark.png
# The disk-passphrase prompt, as images (fonts can't be counted on in the initramfs)
rsvg-convert -w 440 -h 30  theme/plymouth/envy-black-veil/prompt.svg -o theme/plymouth/envy-black-veil/prompt.png
rsvg-convert -w 440 -h 52  theme/plymouth/envy-black-veil/entry.svg  -o theme/plymouth/envy-black-veil/entry.png
rsvg-convert -w 14  -h 14  theme/plymouth/envy-black-veil/bullet.svg -o theme/plymouth/envy-black-veil/bullet.png
rsvg-convert -w 1920 -h 1080 theme/grub/envy-black-veil/background.svg -o theme/grub/envy-black-veil/background.png
rsvg-convert -w 2560 -h 1440 theme/wallpaper/envy-black-veil.svg -o wallpaper-2560x1440.png

# GRUB can't read TrueType: convert DejaVu to GRUB's .pf2 fonts. -n sets the family;
# GRUB names each font "<family> <Regular|Bold> <size>", which is what theme.txt
# asks for ("DejaVu Sans Regular 16"). (grub-mkfont/fonts paths differ on Debian CI.)
MKFONT=$(command -v grub2-mkfont || command -v grub-mkfont)
SANS=$(find /usr/share/fonts -name DejaVuSans.ttf | head -n 1)
SANSB=$(find /usr/share/fonts -name DejaVuSans-Bold.ttf | head -n 1)
MONO=$(find /usr/share/fonts -name DejaVuSansMono.ttf | head -n 1)
$MKFONT -n "DejaVu Sans" -s 12 -o grub-dejavu-sans-12.pf2 "$SANS"
$MKFONT -n "DejaVu Sans" -s 13 -o grub-dejavu-sans-13.pf2 "$SANS"
$MKFONT -n "DejaVu Sans" -s 16 -o grub-dejavu-sans-16.pf2 "$SANS"
$MKFONT -n "DejaVu Sans" -s 28 -o grub-dejavu-sans-bold-28.pf2 "$SANSB"
$MKFONT -n "DejaVu Sans Mono" -s 16 -o grub-dejavu-sans-mono-16.pf2 "$MONO"   # GRUB's command line

%install
# --- theme ---------------------------------------------------------------
install -Dm644 theme/plasma/color-schemes/EnvyNeon.colors %{buildroot}%{_datadir}/color-schemes/EnvyNeon.colors
install -Dm644 theme/konsole/Envy.profile      %{buildroot}%{_datadir}/konsole/Envy.profile
install -Dm644 theme/konsole/Envy.colorscheme  %{buildroot}%{_datadir}/konsole/Envy.colorscheme

# SDDM theme
install -d %{buildroot}%{_datadir}/sddm/themes/envy-black-veil
cp -a theme/sddm/envy-black-veil/. %{buildroot}%{_datadir}/sddm/themes/envy-black-veil/

# Plymouth theme
install -d %{buildroot}%{_datadir}/plymouth/themes/envy-black-veil
cp -a theme/plymouth/envy-black-veil/. %{buildroot}%{_datadir}/plymouth/themes/envy-black-veil/
rm -f %{buildroot}%{_datadir}/plymouth/themes/envy-black-veil/*.svg

# GRUB theme
install -d %{buildroot}/boot/grub2/themes/envy-black-veil
install -Dm644 theme/grub/envy-black-veil/theme.txt       %{buildroot}/boot/grub2/themes/envy-black-veil/theme.txt
install -Dm644 theme/grub/envy-black-veil/background.png   %{buildroot}/boot/grub2/themes/envy-black-veil/background.png
install -m644 grub-*.pf2 %{buildroot}/boot/grub2/themes/envy-black-veil/

# The themed GRUB menu on installed systems: grub2-mkconfig (run by the installer and
# afterwards) picks this up; and ENVY BLACK VEIL names on the boot menu's entries.
install -Dm755 theme/grub/grub.d/05_envy_black_veil %{buildroot}%{_sysconfdir}/grub.d/05_envy_black_veil
install -Dm755 theme/kernel/96-envy-black-veil-title.install \
    %{buildroot}%{_prefix}/lib/kernel/install.d/96-envy-black-veil-title.install

# Wallpaper
install -Dm644 wallpaper-2560x1440.png %{buildroot}%{_datadir}/wallpapers/EnvyBlackVeil/contents/images/2560x1440.png
install -Dm644 theme/wallpaper/metadata.json %{buildroot}%{_datadir}/wallpapers/EnvyBlackVeil/metadata.json

# Make the ENVY wallpaper the default (Plasma runs this once per user)
install -Dm644 theme/plasma/updates/envy-black-veil-wallpaper.js \
    %{buildroot}%{_datadir}/plasma/shells/org.kde.plasma.desktop/contents/updates/envy-black-veil-wallpaper.js

# Dark defaults for every new user
install -Dm644 theme/skel/.config/kdeglobals %{buildroot}%{_sysconfdir}/skel/.config/kdeglobals
install -Dm644 theme/skel/.config/konsolerc  %{buildroot}%{_sysconfdir}/skel/.config/konsolerc

# --- release -------------------------------------------------------------
install -d %{buildroot}%{_sysconfdir}
echo "ENVY BLACK VEIL release %{version} (Nebula) — AlmaLinux 10 + KDE Plasma 6" \
    > %{buildroot}%{_sysconfdir}/envy-black-veil-release
install -Dm755 tools/envy-tools   %{buildroot}%{_bindir}/envy-tools
install -Dm755 tools/envy-hardware-report %{buildroot}%{_bindir}/envy-hardware-report
install -Dm644 tools/desktop/envy-hardware-report.desktop \
    %{buildroot}%{_datadir}/applications/envy-hardware-report.desktop
install -Dm644 privacy/90-envy-privacy.conf \
    %{buildroot}%{_sysconfdir}/NetworkManager/conf.d/90-envy-privacy.conf
install -Dm644 privacy/firefox-policies.json %{buildroot}%{_sysconfdir}/firefox/policies/policies.json
install -Dm644 privacy/anaconda-90-envy-privacy.conf %{buildroot}%{_sysconfdir}/anaconda/conf.d/90-envy-privacy.conf

# --- live ----------------------------------------------------------------
install -d %{buildroot}%{_prefix}/lib/dracut/modules.d/90envy-live-persist
install -m755 live/dracut/90envy-live-persist/module-setup.sh \
    live/dracut/90envy-live-persist/envy-persist-genrules.sh \
    live/dracut/90envy-live-persist/create-envy-persistence.sh \
    %{buildroot}%{_prefix}/lib/dracut/modules.d/90envy-live-persist/

%post theme
if [ $1 -ge 1 ] && command -v plymouth-set-default-theme >/dev/null 2>&1; then
    plymouth-set-default-theme envy-black-veil >/dev/null 2>&1 || :
fi

%files theme
%license LICENSE
%{_datadir}/color-schemes/EnvyNeon.colors
%{_datadir}/konsole/Envy.profile
%{_datadir}/konsole/Envy.colorscheme
%{_datadir}/sddm/themes/envy-black-veil/
%{_datadir}/plymouth/themes/envy-black-veil/
/boot/grub2/themes/envy-black-veil/
%{_datadir}/wallpapers/EnvyBlackVeil/
%{_datadir}/plasma/shells/org.kde.plasma.desktop/contents/updates/envy-black-veil-wallpaper.js
%{_sysconfdir}/grub.d/05_envy_black_veil
%{_prefix}/lib/kernel/install.d/96-envy-black-veil-title.install
%{_sysconfdir}/skel/.config/kdeglobals
%{_sysconfdir}/skel/.config/konsolerc

%files release
%license LICENSE
%config(noreplace) %{_sysconfdir}/envy-black-veil-release
%{_bindir}/envy-tools
%{_bindir}/envy-hardware-report
%{_datadir}/applications/envy-hardware-report.desktop
%config(noreplace) %{_sysconfdir}/NetworkManager/conf.d/90-envy-privacy.conf
%dir %{_sysconfdir}/firefox
%dir %{_sysconfdir}/firefox/policies
%config(noreplace) %{_sysconfdir}/firefox/policies/policies.json
%config(noreplace) %{_sysconfdir}/anaconda/conf.d/90-envy-privacy.conf

%files live
%license LICENSE
%{_prefix}/lib/dracut/modules.d/90envy-live-persist/

%changelog
* Wed Nov 25 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-4
- New envy-black-veil-live: the live boot menu's "keep changes on this USB stick"
  entry turns a stick's free space into persistent storage on its first boot,
  labelled for SELinux so the live system runs enforcing on it.
- envy-hardware-report and the menu's Hardware Report: this computer's hardware,
  drivers and firmware problems as a Markdown report to share, without serial
  numbers, addresses or names.

* Wed Nov 25 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-3
- GRUB menu: fonts named the way GRUB looks them up (it fell back to the bold
  title font for everything), and a wider menu for long entry names.
- The boot splash's disk-passphrase prompt is drawn from images: Plymouth 24's
  FreeType text plugin finds no font in the initramfs, so the text-only prompt
  was invisible and the splash just waited.
- The ENVY GRUB menu on installed systems now comes from /etc/grub.d (Anaconda 40
  no longer runs /usr/share/anaconda/post-scripts), and boot entries are named
  ENVY BLACK VEIL by a kernel-install hook.
- Privacy defaults in the release package: no NetworkManager connectivity check, no
  installer geolocation lookup, and Firefox policies with telemetry, studies, Pocket
  and sponsored content off.

* Tue Nov 24 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-2
- Build on AlmaLinux 10's own live-media recipe: Anaconda live installer (Calamares
  is not packaged for EL10), livesys live session, the ENVY wallpaper as the default.
- Keep AlmaLinux's release package; ship /etc/envy-black-veil-release instead of
  replacing os-release, so dnf and updates work unchanged.

* Sun Nov 08 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-1
- First ENVY BLACK VEIL identity packages: theme, release branding, Calamares branding.
