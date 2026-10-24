#!/bin/sh
# Start the Resolute desk in place of XFCE's desktop (xfdesktop).
# XFCE's window manager keeps running, so programs still open in normal windows.
# When the desk is closed, the normal XFCE desktop is brought back.

cd "$(dirname "$(readlink -f "$0")")" || exit 1

if pgrep -x xfdesktop >/dev/null 2>&1; then
    xfdesktop --quit
    restore_xfdesktop=1
fi

python3 -m resolute "$@"
status=$?

if [ -n "$restore_xfdesktop" ]; then
    setsid xfdesktop >/dev/null 2>&1 &
fi
exit $status
