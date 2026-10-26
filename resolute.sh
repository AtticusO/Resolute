#!/bin/sh
# Start the Resolute desk in place of XFCE's desktop (xfdesktop).
# XFCE's window manager keeps running, so programs still open in normal windows.
# When the desk is closed, the normal XFCE desktop is brought back.

cd "$(dirname "$(readlink -f "$0")")" || exit 1

# Resolute is built for X11. It still starts on Wayland, but with much of it not working,
# so say so: in the terminal, and as a desktop notification for when it starts at login.
if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] || [ -n "${WAYLAND_DISPLAY:-}" ]; then
    warning="Resolute is running on Wayland, where it can only partly work:
- open programs won't appear in the letter slots, and can't be switched from there
- the desk may not stay behind other windows, and may show up in the taskbar and Alt+Tab
- the system's own taskbar or top bar can't be hidden
For the full desk, log in to an Xfce session on X11: run ./setup-x11.sh to set it up."
    printf 'Warning: %s\n' "$warning" >&2
    if command -v notify-send >/dev/null 2>&1; then
        notify-send -a Resolute -i dialog-warning -t 15000 "Resolute on Wayland" "$warning" >/dev/null 2>&1 &
    fi
fi

if [ "$1" = "--autostart" ]; then
    # At login XFCE may start its own desktop just after us (or, with a saved session, not at all).
    # Start straight away, and for the first 20 seconds replace xfdesktop if it turns up.
    shift
    restore_xfdesktop=1
    (
        for _ in $(seq 40); do
            pgrep -x xfdesktop >/dev/null 2>&1 && xfdesktop --quit
            sleep 0.5
        done
    ) &
elif pgrep -x xfdesktop >/dev/null 2>&1; then
    xfdesktop --quit
    restore_xfdesktop=1
fi

python3 -m resolute "$@"
status=$?

if [ -n "$restore_xfdesktop" ]; then
    setsid xfdesktop >/dev/null 2>&1 &
fi
exit $status
