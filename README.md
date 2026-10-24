# Resolute

A desktop environment shaped like a roll-top desk, built with Python 3 and PyQt6.

| On the desk | What it does |
|---|---|
| Stained glass lamp (left) | Start menu: search and launch any installed application, plus Lock, Sleep, Log Out, Restart and Shut Down |
| Letter slots (back centre) | One card per open program, with its icon and title: click to bring it forward, click the front one to minimise it, scroll if there are more than 11 |
| Radio (back left) | Left knob: speaker volume. Right knob: microphone level. Scroll or drag a knob to turn it, click it to mute. Click the glowing dial to choose speakers and microphone |
| Bronze gauges (on their stand) | CPU load, memory, CPU temperature and storage, updated every 1.5 s; hover one for details |
| Pen cup (back right) | Opens a terminal |
| Quill and inkwell (beside the pen cup) | Lays a sheet of note paper on the leather writing pad; type straight onto it. Whatever you write is saved automatically to a text file. Click the quill again, click the desk, press Esc or the × to put it away |
| Globe (top right) | Opens the default web browser |
| Mantel clock (front right) | The time, with a sweeping second hand. The small dial at six o'clock is the battery gauge (E to F, red below 20%, green pip when plugged in). Hover for the date or the exact charge |
| Sealed envelope (pigeonholes) | Opens Gmail in the default browser |
| Centre drawer | The view tilts down into it to show your `~/Documents` folder: click a folder to go into it, a file to open it, scroll for more |
| Left drawer (FILES) | Hanging folders for browsing the whole filesystem: click a folder to go in, Up to go back, a file to open it, scroll for more |
| Right drawer | Text Editor (LibreOffice Writer) and Slideshow (LibreOffice Impress) |

Click a drawer again, click anywhere on the desk, or press Esc to close it.

## Requirements

```
sudo apt install python3-pyqt6 python3-psutil python3-numpy libreoffice-writer libreoffice-impress
```

## Running

```
./resolute.sh              # as the desktop, replacing xfdesktop until it exits
python3 -m resolute --windowed   # in a normal window, for trying it out
./install.sh               # start it automatically at login (./install.sh --remove to undo)
```

"Close desk" at the bottom left of the start menu exits Resolute and brings back the normal XFCE desktop.

## Settings

Optional. Create `~/.config/resolute/config.toml` to override any of these:

```toml
documents_dir = "~/Documents"
files_start_dir = "~"         # where the Files drawer opens
mail_url = "https://mail.google.com"
note_file = "~/Documents/desk-note.txt"   # the quill's note paper
text_editor_command = "libreoffice --writer"
slideshow_command = "libreoffice --impress"
text_editor_fallback = "mousepad"
browser_command = ""          # empty = system default browser
terminal_command = ""         # empty = the desktop's preferred terminal
disk_path = "/"               # filesystem shown on the storage gauge
show_hidden_files = false
stats_interval_ms = 1500
```

## Layout

- `resolute/desk.py`: desk geometry and painting
- `resolute/gauges.py`: the dashboard gauges
- `resolute/globe.py`: the spinning globe
- `resolute/drawers.py`: drawer animation and contents
- `resolute/startmenu.py`: the start menu
- `resolute/taskslots.py`, `resolute/windows.py`: open-program cards, read from the window manager with `xprop`, switched with `xdotool`
- `resolute/clock.py`: the mantel clock and its battery gauge
- `resolute/lamp.py`, `resolute/pencup.py`, `resolute/note.py`: the stained glass lamp, the pen cup, and the quill with its note paper
- `resolute/radio.py`, `resolute/audio.py`: the radio, controlling audio through `pactl`
- `resolute/system.py`: stats, launching programs, power actions
- `resolute/textures.py`: lights the photographed wood and leather in `resolute/assets/` (CC0, see `CREDITS.md`); generates felt and wallpaper
