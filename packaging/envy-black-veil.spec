# ENVY BLACK VEIL identity packages: the theme and the release identity.
# build/build-iso.sh builds these into a local repo that the kickstart installs,
# so the live image boots fully themed.

%global debug_package %{nil}

Name:           envy-black-veil
Version:        0.1.0
Release:        2%{?dist}
Summary:        ENVY BLACK VEIL identity: theme and release identity
License:        MIT
URL:            https://github.com/xzchick/envy-black-veil
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  librsvg2-tools

%description
Metapackage shell. Install the envy-black-veil-theme and envy-black-veil-release
subpackages to turn a stock AlmaLinux 10 + KDE Plasma 6 system into ENVY BLACK VEIL.

# ---------------------------------------------------------------------------
%package theme
Summary:        ENVY neon theme for KDE Plasma, SDDM, Plymouth, GRUB and Konsole
Requires:       plymouth
Requires:       sddm
Supplements:    (sddm and plymouth)

%description theme
The ENVY neon look: a Plasma colour scheme, an SDDM login theme, a Plymouth boot
splash with a LUKS passphrase prompt, a GRUB menu theme, a Konsole profile and
colour scheme, a desktop wallpaper (made the default once per user), and sensible
dark defaults in /etc/skel.

# ---------------------------------------------------------------------------
%package release
Summary:        ENVY BLACK VEIL release file and the envy-tools installer

%description release
Marks the system as ENVY BLACK VEIL (/etc/envy-black-veil-release) and installs
`envy-tools`, the on-demand installer for the ENVY application suite. AlmaLinux's
own release package stays in place, so dnf, repositories and updates keep working
exactly as on AlmaLinux 10.

# ---------------------------------------------------------------------------
%prep
%autosetup

%build
# Render the SVG art to the PNGs the themes reference.
rsvg-convert -w 820 -h 300 theme/plymouth/envy-black-veil/logo.svg  -o theme/plymouth/envy-black-veil/logo.png
rsvg-convert -w 48  -h 48  theme/plymouth/envy-black-veil/spark.svg -o theme/plymouth/envy-black-veil/spark.png
rsvg-convert -w 1920 -h 1080 theme/grub/envy-black-veil/background.svg -o theme/grub/envy-black-veil/background.png
rsvg-convert -w 2560 -h 1440 theme/wallpaper/envy-black-veil.svg -o wallpaper-2560x1440.png

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
%{_sysconfdir}/skel/.config/kdeglobals
%{_sysconfdir}/skel/.config/konsolerc

%files release
%license LICENSE
%config(noreplace) %{_sysconfdir}/envy-black-veil-release
%{_bindir}/envy-tools

%changelog
* Tue Nov 24 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-2
- Build on AlmaLinux 10's own live-media recipe: Anaconda live installer (Calamares
  is not packaged for EL10), livesys live session, the ENVY wallpaper as the default.
- Keep AlmaLinux's release package; ship /etc/envy-black-veil-release instead of
  replacing os-release, so dnf and updates work unchanged.

* Sun Nov 08 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-1
- First ENVY BLACK VEIL identity packages: theme, release branding, Calamares branding.
