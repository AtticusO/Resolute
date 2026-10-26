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

# The entry is still installed on Wayland, but it only starts the desk in Xfce sessions,
# so point to the way to get one.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    echo "Warning: this session is Wayland, where Resolute can only partly work (open programs" >&2
    echo "won't appear in the letter slots, and the system taskbar can't be hidden). The login" >&2
    echo "entry only starts the desk in an Xfce session; run ./setup-x11.sh to set one up on X11." >&2
fi

mkdir -p "$(dirname "$autostart")"
cat > "$autostart" <<EOF
[Desktop Entry]
Type=Application
Name=Resolute Desk
Comment=Roll-top desk desktop environment
Exec=$dir/resolute.sh --autostart
OnlyShowIn=XFCE;
X-GNOME-Autostart-enabled=true
EOF
chmod +x "$dir/resolute.sh"
echo "Installed $autostart"
echo "Resolute will replace the XFCE desktop at your next login, or run $dir/resolute.sh now."
