"""User settings, read from ~/.config/resolute/config.toml when present."""

import os
import tomllib
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "resolute" / "config.toml"

DEFAULTS = {
    "documents_dir": str(Path.home() / "Documents"),
    "files_start_dir": "~",  # where the Files drawer opens; Up goes all the way to /
    "mail_url": "https://mail.google.com",
    "note_file": "~/Documents/desk-note.txt",  # the note paper the quill brings up
    "sketch_file": "~/Documents/desk-sketch.png",  # the page of the sketch pad
    "text_editor_command": "libreoffice --writer",
    "slideshow_command": "libreoffice --impress",
    "code_editor_command": "code",  # VS Code, in the Programs drawer
    # Used when LibreOffice is not installed.
    "text_editor_fallback": "mousepad",
    "browser_command": "",  # empty = system default browser
    "terminal_command": "",  # empty = the desktop's preferred terminal
    "homepage": "https://duckduckgo.com",
    "disk_path": "/",
    "show_hidden_files": False,
    "stats_interval_ms": 1500,
}

_values = None


def _load():
    values = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, "rb") as f:
            values.update(tomllib.load(f))
    except FileNotFoundError:
        pass
    except tomllib.TOMLDecodeError as e:
        print(f"resolute: ignoring invalid config {CONFIG_PATH}: {e}")
    values["documents_dir"] = os.path.expanduser(values["documents_dir"])
    return values


def get(key):
    global _values
    if _values is None:
        _values = _load()
    return _values[key]
