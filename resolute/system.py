"""System stats, application launching and power actions."""

import os
import shlex
import shutil
import subprocess
from pathlib import Path

import psutil

from . import config


def battery():
    """(percent, plugged in, seconds left or None) or None when the machine has no battery."""
    try:
        b = psutil.sensors_battery()
    except (AttributeError, OSError):
        return None
    if b is None:
        return None
    left = b.secsleft if isinstance(b.secsleft, int) and b.secsleft >= 0 else None
    return b.percent, bool(b.power_plugged), left


class Stats:
    def __init__(self):
        psutil.cpu_percent(interval=None)  # prime the counter

    def cpu(self):
        return psutil.cpu_percent(interval=None)

    def ram(self):
        vm = psutil.virtual_memory()
        return vm.percent, vm.used, vm.total

    def disk(self):
        du = psutil.disk_usage(str(config.get("disk_path")))
        return du.percent, du.used, du.total


def _spawn(argv):
    """Start a program fully detached from the desk process."""
    try:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True,
                         cwd=str(Path.home()))
        return True
    except OSError:
        return False


def run_command(command):
    """Run a configured shell-style command string. Returns False if the program is missing."""
    argv = shlex.split(command)
    if not argv or not shutil.which(argv[0]):
        return False
    return _spawn(argv)


def open_path(path):
    return _spawn(["xdg-open", str(path)])


def open_url(url):
    """Open a web address in the configured or default browser."""
    custom = config.get("browser_command")
    if custom:
        argv = shlex.split(custom)
        return bool(argv) and shutil.which(argv[0]) is not None and _spawn(argv + [url])
    return open_path(url)


def open_terminal():
    custom = config.get("terminal_command")
    if custom:
        return run_command(custom)
    if shutil.which("exo-open"):  # XFCE's preferred terminal
        return _spawn(["exo-open", "--launch", "TerminalEmulator"])
    for cmd in ("x-terminal-emulator", "qterminal", "xfce4-terminal", "gnome-terminal", "konsole", "xterm"):
        if shutil.which(cmd):
            return _spawn([cmd])
    return False


def launch_desktop_file(path):
    if shutil.which("exo-open"):
        return _spawn(["exo-open", str(path)])
    return _spawn(["gio", "launch", str(path)])


def open_browser():
    custom = config.get("browser_command")
    if custom:
        return run_command(custom)
    if shutil.which("exo-open"):
        return _spawn(["exo-open", "--launch", "WebBrowser"])
    try:
        desktop = subprocess.run(["xdg-settings", "get", "default-web-browser"],
                                 capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        desktop = ""
    for base in _application_dirs():
        candidate = base / desktop
        if desktop and candidate.is_file():
            return launch_desktop_file(candidate)
    return open_path(config.get("homepage"))


def _application_dirs():
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    data_dirs = os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    return [data_home / "applications"] + [Path(d) / "applications" for d in data_dirs if d]


# --- virtual machines -----------------------------------------------------

# For each kind of VM (as systemd-detect-virt names it): its name, the guest tools process that resizes
# the screen to fit the VM's window (and an argument that picks it out), and the package that has it.
_GUEST_TOOLS = {
    "vmware": ("VMware", "vmtoolsd", "vmusr", "open-vm-tools-desktop"),  # the session's own vmtoolsd
    "oracle": ("VirtualBox", "VBoxClient", None, "virtualbox-guest-x11"),
    "kvm": ("QEMU/KVM", "spice-vdagent", None, "spice-vdagent"),
    "qemu": ("QEMU/KVM", "spice-vdagent", None, "spice-vdagent"),
}


def missing_guest_tools():
    """(VM name, package) when this is a virtual machine whose guest tools aren't running, else None."""
    if not shutil.which("systemd-detect-virt"):
        return None
    try:
        vm = subprocess.run(["systemd-detect-virt", "--vm"], capture_output=True, text=True, timeout=3).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return None
    if vm not in _GUEST_TOOLS:
        return None
    name, process, arg, package = _GUEST_TOOLS[vm]
    for proc in psutil.process_iter(["name", "cmdline"]):
        if proc.info["name"] == process and (arg is None or arg in (proc.info["cmdline"] or [])):
            return None
    return name, package


# --- power ----------------------------------------------------------------

def _in_xfce():
    return "XFCE" in os.environ.get("XDG_CURRENT_DESKTOP", "").upper() and shutil.which("xfce4-session-logout")


def lock():
    for argv in (["xflock4"], ["loginctl", "lock-session"]):
        if shutil.which(argv[0]):
            return _spawn(argv)
    return False


def suspend():
    return _spawn(["systemctl", "suspend"])


def logout():
    if _in_xfce():
        return _spawn(["xfce4-session-logout", "--logout", "--fast"])
    session = os.environ.get("XDG_SESSION_ID")
    return _spawn(["loginctl", "terminate-session", session] if session else ["loginctl", "terminate-user", os.environ.get("USER", "")])


def reboot():
    if _in_xfce():
        return _spawn(["xfce4-session-logout", "--reboot", "--fast"])
    return _spawn(["systemctl", "reboot"])


def poweroff():
    if _in_xfce():
        return _spawn(["xfce4-session-logout", "--halt", "--fast"])
    return _spawn(["systemctl", "poweroff"])
