// ENVY BLACK VEIL: make the ENVY wallpaper the default on every desktop.
// Plasma runs each script in this folder once per user (it remembers which ran).
var wallpaper = "file:///usr/share/wallpapers/EnvyBlackVeil/";
var all = desktops();
for (var i = 0; i < all.length; i++) {
    var d = all[i];
    d.wallpaperPlugin = "org.kde.image";
    d.currentConfigGroup = ["Wallpaper", "org.kde.image", "General"];
    d.writeConfig("Image", wallpaper);
}
