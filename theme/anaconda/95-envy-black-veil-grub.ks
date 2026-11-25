# ENVY BLACK VEIL: the themed GRUB menu on installed systems.
# Anaconda runs every *.ks in /usr/share/anaconda/post-scripts after it installs
# (live installs included), inside the new system. It writes /etc/default/grub
# itself during the install, so the theme is switched on here, at the very end.
%post
if [ -f /etc/default/grub ] && [ -f /boot/grub2/themes/envy-black-veil/theme.txt ]; then
    sed -i -e '/^GRUB_TERMINAL_OUTPUT=/d' -e '/^GRUB_THEME=/d' -e '/^GRUB_GFXMODE=/d' /etc/default/grub
    cat >> /etc/default/grub << 'EOF'
GRUB_TERMINAL_OUTPUT="gfxterm"
GRUB_GFXMODE="auto"
GRUB_THEME="/boot/grub2/themes/envy-black-veil/theme.txt"
EOF
    grub2-mkconfig -o /boot/grub2/grub.cfg
fi
%end
