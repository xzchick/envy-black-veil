# ENVY BLACK VEIL identity packages: the theme, the release branding and the
# Calamares installer branding. build/build-iso.sh builds these into a local repo
# that the kickstart installs, so the live image boots fully themed.

%global debug_package %{nil}

Name:           envy-black-veil
Version:        0.1.0
Release:        1%{?dist}
Summary:        ENVY BLACK VEIL identity: theme, release branding and installer branding
License:        MIT
URL:            https://github.com/xzchick/envy-black-veil
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
BuildRequires:  librsvg2-tools

%description
Metapackage shell. Install the envy-black-veil-theme, envy-black-veil-release and
calamares-branding-envy subpackages to turn a stock AlmaLinux + KDE Plasma system
into ENVY BLACK VEIL.

# ---------------------------------------------------------------------------
%package theme
Summary:        ENVY neon theme for KDE Plasma, SDDM, Plymouth, GRUB and Konsole
Requires:       plymouth
Requires:       sddm
Supplements:    (sddm and plymouth)

%description theme
The ENVY neon look: a Plasma colour scheme, an SDDM login theme, a Plymouth boot
splash with a LUKS passphrase prompt, a GRUB menu theme, a Konsole profile and
colour scheme, a desktop wallpaper, and sensible dark defaults in /etc/skel.

# ---------------------------------------------------------------------------
%package release
Summary:        ENVY BLACK VEIL release identity and the envy-tools installer
Provides:       system-release = %{version}
Provides:       system-release(releasever) = %{version}

%description release
Brands the system as ENVY BLACK VEIL (os-release, MOTD) and installs `envy-tools`,
the on-demand installer for the ENVY application suite.

# ---------------------------------------------------------------------------
%package -n calamares-branding-envy
Summary:        ENVY BLACK VEIL branding and configuration for the Calamares installer
Requires:       calamares
BuildArch:      noarch

%description -n calamares-branding-envy
ENVY branding, slideshow and the install module sequence for Calamares, including
support for installing to an external USB, SSD or HDD.

# ---------------------------------------------------------------------------
%prep
%autosetup

%build
# Render the SVG art to the PNGs the themes reference.
rsvg-convert -w 820 -h 300 theme/plymouth/envy-black-veil/logo.svg  -o theme/plymouth/envy-black-veil/logo.png
rsvg-convert -w 48  -h 48  theme/plymouth/envy-black-veil/spark.svg -o theme/plymouth/envy-black-veil/spark.png
rsvg-convert -w 1920 -h 1080 theme/grub/envy-black-veil/background.svg -o theme/grub/envy-black-veil/background.png
rsvg-convert -w 2560 -h 1440 theme/wallpaper/envy-black-veil.svg -o wallpaper-2560x1440.png
rsvg-convert -w 420 -h 154 theme/plymouth/envy-black-veil/logo.svg -o calamares-logo.png
rsvg-convert -w 820 -h 300 theme/plymouth/envy-black-veil/logo.svg -o calamares-welcome.png

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

# Dark defaults for every new user
install -Dm644 theme/skel/.config/kdeglobals %{buildroot}%{_sysconfdir}/skel/.config/kdeglobals
install -Dm644 theme/skel/.config/konsolerc  %{buildroot}%{_sysconfdir}/skel/.config/konsolerc

# --- release -------------------------------------------------------------
install -Dm644 release/os-release %{buildroot}%{_prefix}/lib/os-release
install -Dm755 tools/envy-tools   %{buildroot}%{_bindir}/envy-tools

# --- calamares branding --------------------------------------------------
install -d %{buildroot}%{_datadir}/calamares/branding/envy
cp -a installer/calamares/branding/envy/. %{buildroot}%{_datadir}/calamares/branding/envy/
install -Dm644 calamares-logo.png    %{buildroot}%{_datadir}/calamares/branding/envy/logo.png
install -Dm644 calamares-welcome.png %{buildroot}%{_datadir}/calamares/branding/envy/welcome.png
install -Dm644 installer/calamares/settings.conf         %{buildroot}%{_sysconfdir}/calamares/settings.conf
install -Dm644 installer/calamares/shellprocess-envy.conf %{buildroot}%{_sysconfdir}/calamares/modules/shellprocess-envy.conf

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
%{_sysconfdir}/skel/.config/kdeglobals
%{_sysconfdir}/skel/.config/konsolerc

%files release
%license LICENSE
%{_prefix}/lib/os-release
%{_bindir}/envy-tools

%files -n calamares-branding-envy
%license LICENSE
%{_datadir}/calamares/branding/envy/
%config(noreplace) %{_sysconfdir}/calamares/settings.conf
%config(noreplace) %{_sysconfdir}/calamares/modules/shellprocess-envy.conf

%changelog
* Sun Nov 08 2026 Envy <235594225+xzchick@users.noreply.github.com> - 0.1.0-1
- First ENVY BLACK VEIL identity packages: theme, release branding, Calamares branding.
