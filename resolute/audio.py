"""Volume and device control through pactl (PulseAudio, or PipeWire's pulse server)."""

import json
import shutil
import subprocess


class Device:
    def __init__(self, name, description, volume, muted):
        self.name = name
        self.description = description
        self.volume = volume  # percent, 0-150
        self.muted = muted


class AudioState:
    """A snapshot: the default output and input plus every device to choose from."""

    def __init__(self, sinks=(), sources=(), sink=None, source=None):
        self.sinks = list(sinks)
        self.sources = list(sources)
        self.sink = sink
        self.source = source

    @property
    def available(self):
        return self.sink is not None or self.source is not None


def _run(*args, timeout=3):
    try:
        return subprocess.run(["pactl", *args], capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _devices(kind):
    try:
        entries = json.loads(_run("-f", "json", "list", kind) or "[]")
    except json.JSONDecodeError:
        return []
    devices = []
    for e in entries:
        if kind == "sources" and (e.get("monitor_source") or e["name"].endswith(".monitor")):
            continue  # "monitor of ..." loopbacks are not real inputs
        channels = [c.get("value_percent", "0%") for c in e.get("volume", {}).values()]
        levels = [int(c.rstrip("%")) for c in channels if c.rstrip("%").isdigit()]
        devices.append(Device(e["name"], e.get("description", e["name"]),
                              round(sum(levels) / len(levels)) if levels else 0, bool(e.get("mute"))))
    return devices


def read_state():
    """Query pactl. Blocking; call from a worker thread."""
    if not shutil.which("pactl"):
        return AudioState()
    sinks = _devices("sinks")
    sources = _devices("sources")
    default_sink = _run("get-default-sink").strip()
    default_source = _run("get-default-source").strip()
    sink = next((d for d in sinks if d.name == default_sink), sinks[0] if sinks else None)
    source = next((d for d in sources if d.name == default_source), sources[0] if sources else None)
    return AudioState(sinks, sources, sink, source)


def _fire(*args):
    """Changes are sent without waiting so the knobs never stall the animation."""
    try:
        subprocess.Popen(["pactl", *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass


def set_volume(kind, percent):
    target = "@DEFAULT_SINK@" if kind == "sink" else "@DEFAULT_SOURCE@"
    _fire(f"set-{kind}-volume", target, f"{int(percent)}%")


def set_mute(kind, muted):
    target = "@DEFAULT_SINK@" if kind == "sink" else "@DEFAULT_SOURCE@"
    _fire(f"set-{kind}-mute", target, "1" if muted else "0")


def set_default(kind, name):
    _fire(f"set-default-{kind}", name)
