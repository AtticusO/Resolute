#!/usr/bin/env bash
# Set a machine up to run Resolute properly: an Xfce session on X11.
#
# Resolute needs X11. On Wayland (the default on GNOME, and the only option on recent GNOME,
# which has dropped its X11 session) programs can't see or switch each other's windows, so the
# letter slots stay empty and the system's own taskbar can't be hidden. This script installs Xfce
# and the X server next to whatever desktop you have, and makes Xfce your session for the next
# login. GNOME (or any other desktop) stays installed and can still be chosen at the login screen.
#
#   ./setup-x11.sh           look at this machine and show what would be done (changes nothing)
#   ./setup-x11.sh --apply   do it, asking before each step
#
# Supported: Debian and its derivatives (Kali, ...), Ubuntu and its flavours, Arch and its
# derivatives (Manjaro, EndeavourOS, ...). Other distributions get a report and instructions.
#
# What it never does: remove a desktop, edit GDM's Wayland setting (turning Wayland off in GDM
# before another desktop works is a classic way to lock yourself out of the graphical login), or
# change the login screen without asking. Run it again at any time; it only does what is missing.
# A log of everything it runs is kept in ~/.cache/resolute/setup-x11.log.

set -u

APPLY=0
for arg in "$@"; do
    case "$arg" in
        --apply) APPLY=1 ;;
        -h|--help) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) echo "Unknown option: $arg (try --help)" >&2; exit 2 ;;
    esac
done

if [ "$(id -u)" -eq 0 ]; then
    echo "Run this as your normal user, not as root: it asks for sudo when it needs to," >&2
    echo "and it sets up the session for the user running it." >&2
    exit 1
fi

OS_RELEASE="${RESOLUTE_OS_RELEASE:-/etc/os-release}"  # overridable only for testing
LOG="${XDG_CACHE_HOME:-$HOME/.cache}/resolute/setup-x11.log"
mkdir -p "$(dirname "$LOG")"
echo "=== setup-x11.sh $(date '+%F %T') apply=$APPLY ===" >> "$LOG"

say()  { printf '%s\n' "$*"; printf '%s\n' "$*" >> "$LOG"; }
section() { printf '\n== %s ==\n' "$*"; }

# Run a command, recording it and its exit status in the log. Output is not piped through the
# log, so the package managers' own prompts still work.
run() {
    printf '  $ %s\n' "$*"
    printf '+ %s\n' "$*" >> "$LOG"
    "$@"
    local rc=$?
    printf '  (exit %s)\n' "$rc" >> "$LOG"
    return $rc
}

# y/n question, answered from the terminal; anything but y/yes (or no terminal at all) means no.
ask() {
    local answer
    if ! { true < /dev/tty; } 2>/dev/null; then  # can't just test the file: it exists even with no terminal
        say "  (no terminal to ask on, so skipping: $1)"
        return 1
    fi
    read -r -p "$1 [y/N] " answer < /dev/tty
    printf 'asked: %s -> %s\n' "$1" "$answer" >> "$LOG"
    case "$answer" in [Yy]|[Yy][Ee][Ss]) return 0 ;; *) return 1 ;; esac
}

# --- looking at the machine -------------------------------------------------------------------

session_type() {
    local t="${XDG_SESSION_TYPE:-}"
    if [ -z "$t" ] && [ -n "${XDG_SESSION_ID:-}" ] && command -v loginctl >/dev/null; then
        t="$(loginctl show-session "$XDG_SESSION_ID" -p Type --value 2>/dev/null)"
    fi
    if [ -z "$t" ] || [ "$t" = "tty" ]; then
        if [ -n "${WAYLAND_DISPLAY:-}" ]; then t=wayland
        elif [ -n "${DISPLAY:-}" ]; then t=x11
        else t="${t:-none}"
        fi
    fi
    echo "$t"
}

os_field() {  # os_field ID -> value from os-release, without quotes
    [ -r "$OS_RELEASE" ] || return
    sed -n "s/^$1=//p" "$OS_RELEASE" | head -n1 | tr -d '"'
}

# Which family of package tools to use.
#
# Future additions (not supported yet, they only get a report and instructions):
#   - Fedora / RHEL clones: dnf; group "xfce-desktop-environment", xorg-x11-server-Xorg,
#     python3-pyqt6, python3-psutil, python3-numpy, xprop, xdotool, pulseaudio-utils,
#     urw-base35-fonts, dejavu-sans-fonts, lightdm. Note RHEL 10 and its clones no longer ship
#     the X server at all, so they can't be supported this way.
#   - openSUSE: zypper; pattern "xfce", xorg-x11-server, python3-PyQt6, python3-psutil,
#     python3-numpy, xprop, xdotool, pulseaudio-utils, urw-base35-fonts, dejavu-fonts, lightdm;
#     the login screen is chosen with update-alternatives --set default-displaymanager.
#   - Void (xbps-install, runit services instead of systemd), Gentoo (emerge, USE flags),
#     Alpine (apk, OpenRC).
#   - Immutable systems (Fedora Silverblue/Kinoite, SteamOS, NixOS): packages are not installed
#     this way at all; they would need layering (rpm-ostree) or system configuration instead.
distro_family() {
    local id like
    if [ -e /run/ostree-booted ]; then echo immutable; return; fi
    id="$(os_field ID)"
    like="$(os_field ID_LIKE)"
    case " $id $like " in
        *" arch "*) echo arch ;;
        *" debian "*|*" ubuntu "*) echo debian ;;
        *) echo unsupported ;;
    esac
}

# The login screen (display manager) systemd starts, e.g. gdm3, gdm, lightdm, sddm, or none.
login_screen() {
    local unit
    unit="$(readlink -f /etc/systemd/system/display-manager.service 2>/dev/null)"
    if [ -n "$unit" ] && [ -e "$unit" ]; then
        basename "$unit" .service
    elif [ -r /etc/X11/default-display-manager ]; then
        basename "$(cat /etc/X11/default-display-manager)"
    else
        echo none
    fi
}

# The kind of virtual machine this is (vmware, oracle for VirtualBox, kvm, qemu, ...) or none.
vm_kind() {
    local v=""
    command -v systemd-detect-virt >/dev/null && v="$(systemd-detect-virt --vm 2>/dev/null)"
    echo "${v:-none}"
}

installed() {  # installed PACKAGE -> true if the package manager has it installed
    case "$FAMILY" in
        debian) dpkg-query -W -f='${Status}' "$1" 2>/dev/null | grep -q "install ok installed" ;;
        arch)   pacman -Q "$1" >/dev/null 2>&1 ;;
    esac
}

missing() {  # missing PKG... -> the ones not installed, space separated
    local p out=""
    for p in "$@"; do installed "$p" || out="$out $p"; done
    echo "${out# }"
}

# --- what each family needs -------------------------------------------------------------------

set_packages() {
    case "$FAMILY" in
        debian)
            # xfce4 pulls in the session, window manager, panel and xfdesktop; xserver-xorg the X server.
            DESKTOP_PKGS=(xfce4 xserver-xorg)
            RESOLUTE_PKGS=(python3 python3-pyqt6 python3-psutil python3-numpy x11-utils xdotool
                           pulseaudio-utils fonts-urw-base35 fonts-dejavu-core exo-utils xdg-utils)
            OFFICE_PKGS=(libreoffice-writer libreoffice-impress)
            LOGIN_PKGS=(lightdm lightdm-gtk-greeter)
            ;;
        arch)
            # xfce4 is a package group (session, xfwm4, panel, xfdesktop, thunar, exo, ...).
            DESKTOP_PKGS=(xfce4 xorg-server)
            RESOLUTE_PKGS=(python python-pyqt6 python-psutil python-numpy xorg-xprop xdotool libpulse
                           gsfonts ttf-dejavu xdg-utils)
            OFFICE_PKGS=(libreoffice-fresh)
            LOGIN_PKGS=(lightdm lightdm-gtk-greeter)
            ;;
        # Future additions: package lists for the families listed above distro_family().
    esac

    # Guest tools let a virtual machine's screen follow the size of its window. Without them the
    # screen is often stuck at 4:3 (1024x768), and the VM shows bars around it.
    # Future additions: Hyper-V (hyperv-daemons), Parallels (its own Tools installer).
    VM_PKGS=(); VM_SERVICES=(); VM_NAME=""
    case "$VM:$FAMILY" in
        vmware:debian) VM_NAME=VMware; VM_PKGS=(open-vm-tools-desktop) ;;
        vmware:arch)   VM_NAME=VMware; VM_PKGS=(open-vm-tools gtkmm3)
                       VM_SERVICES=(vmtoolsd.service vmware-vmblock-fuse.service) ;;
        oracle:debian) VM_NAME=VirtualBox; VM_PKGS=(virtualbox-guest-x11) ;;
        oracle:arch)   VM_NAME=VirtualBox; VM_PKGS=(virtualbox-guest-utils); VM_SERVICES=(vboxservice.service) ;;
        kvm:*|qemu:*)  VM_NAME="QEMU/KVM"; VM_PKGS=(spice-vdagent) ;;
    esac
}

# Packages apt can't find at all (on Ubuntu, PyQt6 lives in the "universe" component).
unavailable() {
    local p out=""
    [ "$FAMILY" = debian ] || { echo ""; return; }
    for p in "$@"; do
        apt-cache policy "$p" 2>/dev/null | grep -q "Candidate: [^(]" || out="$out $p"
    done
    echo "${out# }"
}

install_packages() {  # install_packages PKG...
    [ $# -gt 0 ] || return 0
    case "$FAMILY" in
        debian) run sudo apt-get install "$@" ;;
        arch)   run sudo pacman -S --needed "$@" ;;
    esac
}

# Make LightDM the login screen. Only called after the user has said yes.
switch_to_lightdm() {
    case "$FAMILY" in
        debian)
            # Pre-answer the "which display manager?" question so installing doesn't stop to ask.
            echo "lightdm shared/default-x-display-manager select lightdm" | run sudo debconf-set-selections
            run sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "${LOGIN_PKGS[@]}" || return 1
            run sudo sh -c 'echo /usr/sbin/lightdm > /etc/X11/default-display-manager'
            ;;
        arch)
            run sudo pacman -S --needed "${LOGIN_PKGS[@]}" || return 1
            ;;
    esac
    # lightdm.service is an alias of display-manager.service; --force replaces the old login screen's.
    run sudo systemctl enable --force lightdm.service
}

# Make Xfce the session the login screen picks for this user next time. Per-user, no root needed.
default_to_xfce() {
    # LightDM and GDM both read AccountsService; LightDM falls back to ~/.dmrc without it.
    if command -v busctl >/dev/null; then
        run busctl call org.freedesktop.Accounts "/org/freedesktop/Accounts/User$(id -u)" \
            org.freedesktop.Accounts.User SetXSession s xfce 2>/dev/null \
            || say "  (AccountsService didn't accept it; ~/.dmrc will still be used by LightDM)"
    fi
    printf '[Desktop]\nSession=xfce\n' > "$HOME/.dmrc"
    say "  Wrote ~/.dmrc (Session=xfce)"
}

# --- report -----------------------------------------------------------------------------------

SESSION="$(session_type)"
DESKTOP="${XDG_CURRENT_DESKTOP:-unknown}"
FAMILY="$(distro_family)"
DM="$(login_screen)"
NAME="$(os_field PRETTY_NAME)"; NAME="${NAME:-$(os_field NAME)}"

section "This machine"
say "  System:        ${NAME:-unknown}"
say "  Session:       $SESSION"
say "  Desktop:       $DESKTOP"
say "  Login screen:  $DM"
VM="$(vm_kind)"
if [ "$VM" = none ]; then say "  Machine:       not a virtual machine"; else say "  Machine:       virtual machine ($VM)"; fi

ALREADY=0
if [ "$SESSION" = x11 ] && [[ "$DESKTOP" == *XFCE* ]]; then
    ALREADY=1
    say "  Verdict:       already Xfce on X11, which is what Resolute needs."
else
    say "  Verdict:       Resolute needs an Xfce session on X11; this is $DESKTOP on $SESSION."
fi

case "$FAMILY" in
    debian|arch) ;;
    immutable)
        section "Not supported"
        say "  This is an image-based (immutable) system; packages can't be installed this way."
        say "  Install Xfce and the X server the way your system expects (for example by layering"
        say "  them with rpm-ostree), then log in to the \"Xfce Session\"."
        exit 0 ;;
    *)
        section "Not supported yet"
        say "  This script knows Debian, Ubuntu and Arch (and their derivatives)."
        say "  To do it by hand: install Xfce, the X server, and Resolute's requirements (see the"
        say "  README), make sure your login screen can start X11 sessions (LightDM can), then log"
        say "  out and choose \"Xfce Session\"."
        exit 0 ;;
esac

set_packages
NEED_DESKTOP="$(missing "${DESKTOP_PKGS[@]}")"
NEED_RESOLUTE="$(missing "${RESOLUTE_PKGS[@]}")"
NEED_OFFICE="$(missing "${OFFICE_PKGS[@]}")"
NEED_VM=""
[ ${#VM_PKGS[@]} -gt 0 ] && NEED_VM="$(missing "${VM_PKGS[@]}")"

# Xfce's panels (the top bar, and on Xubuntu a dock at the bottom) sit over the desk unless they
# auto-hide. Their settings only exist once Xfce has been logged in to, so this is only offered there.
PANELS=""; PANELS_SHOWN=""
if [ "$ALREADY" -eq 1 ] && command -v xfconf-query >/dev/null; then
    PANELS="$(xfconf-query -c xfce4-panel -p /panels 2>/dev/null | grep -E '^[0-9]+$' | tr '\n' ' ')"
    for id in $PANELS; do
        [ "$(xfconf-query -c xfce4-panel -p "/panels/panel-$id/autohide-behavior" 2>/dev/null)" = 2 ] \
            || PANELS_SHOWN="$PANELS_SHOWN $id"
    done
    PANELS_SHOWN="${PANELS_SHOWN# }"
fi

# Recent GDM may only start Wayland sessions, so an Xfce/X11 session might never be offered.
# LightDM reliably starts X11 sessions. SDDM, LXDM, XDM and LightDM itself can be kept as they are.
case "$DM" in
    gdm|gdm3|none) WANT_LIGHTDM=1 ;;
    *) WANT_LIGHTDM=0 ;;
esac

section "Plan"
say "  Xfce and the X server:       ${NEED_DESKTOP:-installed}"
say "  Resolute's requirements:     ${NEED_RESOLUTE:-installed}"
say "  Office programs (optional):  ${NEED_OFFICE:-installed}"
if [ "$WANT_LIGHTDM" -eq 1 ]; then
    if [ "$DM" = none ]; then
        say "  Login screen:                none found; offer to install LightDM (asks first)"
    else
        say "  Login screen:                $DM may not start X11 sessions; offer to switch to LightDM (asks first)"
    fi
else
    say "  Login screen:                keep $DM"
fi
if [ -n "$VM_NAME" ]; then
    say "  $VM_NAME guest tools:$(printf '%*s' $((16 - ${#VM_NAME})) '')${NEED_VM:-installed}"
elif [ "$VM" != none ]; then
    say "  Guest tools:                 no package known for $VM; install its guest tools by hand"
fi
if [ "$ALREADY" -eq 1 ]; then
    if [ -n "$PANELS_SHOWN" ]; then
        say "  Xfce panels:                 panel $PANELS_SHOWN always shown; offer to auto-hide (asks first)"
    elif [ -n "$PANELS" ]; then
        say "  Xfce panels:                 already auto-hide"
    fi
    say "  Default session:             already Xfce"
else
    say "  Default session:             make Xfce the session for your next login (asks first)"
fi

if [ "$FAMILY" = debian ]; then
    GONE="$(unavailable $NEED_DESKTOP $NEED_RESOLUTE $NEED_VM)"
    if [ -n "$GONE" ]; then
        say ""
        say "  apt can't find: $GONE"
        if [ "$(os_field ID)" = ubuntu ]; then
            say "  On Ubuntu these are in \"universe\" or \"multiverse\":"
            say "    sudo add-apt-repository universe && sudo add-apt-repository multiverse && sudo apt update"
        else
            say "  Try: sudo apt update"
        fi
    fi
fi

if [ "$APPLY" -eq 0 ]; then
    section "Nothing changed"
    say "  Run ./setup-x11.sh --apply to do this. It asks before each step."
    exit 0
fi

# --- doing it ---------------------------------------------------------------------------------

section "Applying"
if [ -n "$NEED_DESKTOP$NEED_RESOLUTE" ]; then
    if ask "Install Xfce, the X server and Resolute's requirements ($NEED_DESKTOP $NEED_RESOLUTE)?"; then
        [ "$FAMILY" = debian ] && run sudo apt-get update
        # shellcheck disable=SC2086  # word splitting of the package lists is intended
        install_packages $NEED_DESKTOP $NEED_RESOLUTE || say "  Installing failed; see the messages above."
    fi
fi
if [ -n "$NEED_OFFICE" ]; then
    if ask "Also install the office programs used by the PROGRAMS drawer ($NEED_OFFICE)? They are large"; then
        # shellcheck disable=SC2086
        install_packages $NEED_OFFICE || say "  Installing failed; Resolute falls back to a plain text editor."
    fi
fi

if [ -n "$NEED_VM" ]; then
    if ask "Install $VM_NAME's guest tools ($NEED_VM) so the screen follows the window size?"; then
        # shellcheck disable=SC2086
        if install_packages $NEED_VM; then
            [ ${#VM_SERVICES[@]} -gt 0 ] && run sudo systemctl enable --now "${VM_SERVICES[@]}"
            VM_INSTALLED=1
        else
            say "  Installing failed; see the messages above."
        fi
    fi
fi

if [ -n "$PANELS_SHOWN" ]; then
    if ask "Make Xfce's panels auto-hide (they slide back in when the pointer reaches their edge)?"; then
        for id in $PANELS_SHOWN; do
            run xfconf-query -c xfce4-panel -p "/panels/panel-$id/autohide-behavior" -n -t uint -s 2
        done
    fi
fi

if [ "$WANT_LIGHTDM" -eq 1 ]; then
    say ""
    say "  The login screen decides which sessions you can pick when you log in."
    [ "$DM" != none ] && say "  $DM stays installed; to go back later: sudo systemctl enable --force $DM.service"
    if ask "Change the login screen from $DM to LightDM?"; then
        echo "previous login screen: $DM" >> "$LOG"
        switch_to_lightdm || say "  Switching the login screen failed; $DM is still in use."
    else
        say "  Keeping $DM. If \"Xfce Session\" isn't offered when you log in, run this again."
    fi
fi

if [ "$ALREADY" -eq 1 ]; then
    :
elif [ -e /usr/share/xsessions/xfce.desktop ]; then
    if ask "Make Xfce the default session for your next login (other desktops stay selectable)?"; then
        default_to_xfce
    fi
else
    say "  Xfce's session isn't installed yet, so the default session was left alone."
fi

section "Next"
if [ "$ALREADY" -eq 1 ]; then
    say "  Run ./resolute.sh, and ./install.sh to start the desk at every login."
else
    say "  1. Log out (or reboot, if the login screen was changed)."
    say "  2. On the login screen, choose \"Xfce Session\" (not one marked Wayland, if listed)."
    say "  3. Check with:  echo \$XDG_SESSION_TYPE   (it should say x11)"
    say "  4. Then run ./resolute.sh, and ./install.sh to start the desk at every login."
    say "  5. Once in Xfce, make its panels (top bar, and the dock on Xubuntu) auto-hide; run this"
    say "     again, or:"
    say "     for p in \$(xfconf-query -c xfce4-panel -p /panels | grep -E '^[0-9]+\$'); do"
    say "         xfconf-query -c xfce4-panel -p /panels/panel-\$p/autohide-behavior -n -t uint -s 2; done"
fi
say ""
say "  The desk is laid out for a 16:9 screen (1920x1080, 1600x900, ...); other shapes work, with"
say "  more desk showing below or bars at the sides. Check yours with:  xrandr | grep '*'"
case "$VM" in
    vmware) say "  In VMware, turn on View > Autosize > Autofit Guest (Workstation/Player) or"
            say "  View > Resize Virtual Machine (Fusion), so the screen follows the window." ;;
    oracle) say "  In VirtualBox, turn on View > Auto-resize Guest Display, so the screen follows the window." ;;
    kvm|qemu) say "  In virt-manager, turn on View > Scale Display > Auto resize VM with window." ;;
esac
[ "${VM_INSTALLED:-0}" -eq 1 ] && say "  Reboot once for the $VM_NAME guest tools to take effect."
say "  Log: $LOG"
