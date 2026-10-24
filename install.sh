#!/bin/sh
# Make Resolute start automatically when you log in to XFCE.
#   ./install.sh            add the autostart entry
#   ./install.sh --remove   take it away again

dir="$(dirname "$(readlink -f "$0")")"
autostart="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/resolute.desktop"

if [ "$1" = "--remove" ]; then
    rm -f "$autostart" && echo "Removed $autostart"
    exit 0
fi

mkdir -p "$(dirname "$autostart")"
cat > "$autostart" <<EOF
[Desktop Entry]
Type=Application
Name=Resolute Desk
Comment=Roll-top desk desktop environment
Exec=$dir/resolute.sh
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$dir/resolute.sh"
echo "Installed $autostart"
echo "Resolute will replace the XFCE desktop at your next login, or run $dir/resolute.sh now."
