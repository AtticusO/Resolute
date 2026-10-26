# Resolute

A desktop environment shaped like a roll-top desk, seen from the chair. It is written in Python 3 with PyQt6 and runs on an XFCE session under X11, taking the place of XFCE's own desktop (`xfdesktop`) while keeping XFCE's window manager, so programs still open in normal windows. At most it consumes just under 300 MB (during initial startup), and runs around just under 200 MB. It has character, personality, and the ability to customize. Use it, change it, play with it. Do anythin but not use it. 

## On the desk

| Object | What it does |
|---|---|
| Stained glass lamp (back left) | Start menu: search and launch any installed application (Kali's tools are under Security Tools), plus Lock, Sleep, Log Out, Restart and Shut Down. Log Out, Restart and Shut Down ask first. "Close desk" at the bottom left exits Resolute |
| Pad of sticky notes (in front of the lamp) | Press on the pad and drag: a note peels off and comes with the pointer. Let go over the desk top and it lies there; let go over the organiser and it sticks to it. Double-click a note to write on it (click inside it to move the cursor), and press Esc or click anywhere else when you're done. Drag a note to move it; right-click it to write on it or throw it away. Notes are saved in `~/.config/resolute/stickies.json` |
| Radio (back left, beside the gauges) | Left knob: speaker volume. Right knob: microphone level. Scroll over a knob or drag it up and down to turn it; click it to mute (a red lamp shows when muted). Click the glowing dial to choose which speakers and microphone to use |
| Bronze gauges (on their stand, back centre) | CPU, RAM, TEMP (CPU temperature) and DISK, updated every 1.5 s. TEMP shows `--°C` with its amber lamp lit when the machine has no temperature sensor (for example in a virtual machine). Hover a gauge for the exact figures |
| Your name (on the arch over the letter slots) | Your username, lettered in gilt; a long name is set smaller to fit |
| Letter slots (in the organiser, back centre) | One card per open program, with its icon and title. Click a card to bring that window forward; click the card of the window already in front to minimise it. The front window's card stands taller with a brass edge; minimised ones sit lower. Scroll over the slots if more than 11 programs are open |
| Pigeon holes (the organiser's cubbies) | Right-click a pigeon hole and choose "Add an application…" to put a program there: it stands in the pigeon hole as a cloth-bound book, coloured after its icon, with its name running down the spine above its logo. Click the book to start the program; right-click it to open it or take it off the shelf. Each pigeon hole holds about four books. They are saved in `~/.config/resolute/shelves.json` |
| Sealed letter (on the desk, in front of the inkwell) | Opens Gmail in the default browser |
| Pen cup (back right of the gauges) | Opens a terminal (XFCE's preferred one) |
| Quill and inkwell (beside the pen cup) | Lays a sheet of note paper on the leather writing pad; type straight onto it, click on it to move the cursor. It saves automatically to a text file. Click the quill again, click elsewhere on the desk, press Esc or click the × on the page to put it away |
| Globe (back right) | Opens the default web browser. It turns slowly, faster when you hover |
| Mantel clock (right, in front of the globe) | The time, with a sweeping second hand. The small dial at six o'clock is the battery gauge: E to F, red below 20%, a green pip when plugged in. Hover the clock for the date, or the small dial for the exact charge |
| FILES drawer (left) | Hanging file folders for browsing the whole filesystem, starting in your home folder. Click a folder to go in, ▲ Up to go back up (all the way to `/`), a file to open it; scroll for more |
| DOCUMENTS drawer (centre) | Your `~/Documents` folder as folders and papers. Click a folder to go into it, Back to return, a file to open it; scroll for more. Text (`.txt`) files open on the writing pad as a sheet of note paper, just like the quill's note, and are saved back to the file as you type |
| PROGRAMS drawer (right) | Text Editor (LibreOffice Writer), Slideshow (LibreOffice Impress) and VS Code, plus any programs you drag in (see below). If Writer is missing, a plain text editor opens instead |

To add a program to the PROGRAMS drawer, drag it from the start menu, or drag a launcher (`.desktop`) file or a program file (such as an AppImage) from a file manager, onto the drawer. Hold it over the closed drawer for a moment and the drawer slides open; drop it on the drawer front or inside. Each added program sits on a card with its own icon. Right-click a card to open it or take it out of the drawer. The drawer is saved in `~/.config/resolute/programs.json`.

Opening a drawer tilts the view down into it. Click the drawer front again, click anywhere on the desk, or press Esc to close it (while you are writing on a sticky note or the note paper is out, Esc finishes that instead).

## Requirements

An XFCE session running on **X11** (Wayland is not supported; see [How it works with X11](#how-it-works-with-x11)). Kali's default desktop is exactly this.

```
sudo apt install python3-pyqt6 python3-psutil python3-numpy \
    x11-utils xdotool pulseaudio-utils fonts-urw-base35 fonts-dejavu-core \
    libreoffice-writer libreoffice-impress
```

- `x11-utils` (`xprop`) and `xdotool`: listing and switching open programs, and marking the desk as the desktop
- `pulseaudio-utils` (`pactl`): the radio; works with PulseAudio or PipeWire
- `fonts-urw-base35` and `fonts-dejavu-core`: the C059, Z003 and DejaVu fonts used on the labels, dials and note paper
- `exo-utils`, `xdg-utils` and `xfconf` are used too; they come with XFCE

### On Wayland (Ubuntu, Fedora, recent GNOME)

Many distributions now log in to GNOME on Wayland by default, and recent GNOME has no X11 session at all. Resolute still starts there, with a warning, but open programs don't appear in the letter slots, the desk may not stay behind other windows, and the system's own top bar or dock can't be hidden. Check with `echo $XDG_SESSION_TYPE`.

`setup-x11.sh` sets such a machine up for the full desk: it installs Xfce, the X server and the packages above next to your current desktop, and makes Xfce your session for the next login. In a virtual machine it also offers the guest tools, and inside Xfce it offers to make the panels auto-hide. It supports Debian, Ubuntu and Arch (and their derivatives); other systems get a report and instructions.

```
./setup-x11.sh           # look at this machine and show what would be done (changes nothing)
./setup-x11.sh --apply   # do it, asking before each step
```

It asks before installing anything, and if your login screen is GDM (which may not offer X11 sessions) it offers to switch it to LightDM, only if you answer yes; it prints how to switch back. It never removes your current desktop or changes GDM's Wayland setting. Afterwards, log out, choose "Xfce Session" on the login screen, and run `./resolute.sh`.

## Running

```
./resolute.sh                    # as your desktop, in place of xfdesktop
python3 -m resolute --windowed   # in a normal window, for trying it out
./install.sh                     # start it automatically at login
./install.sh --remove            # stop starting it at login
```

`resolute.sh` closes `xfdesktop`, runs the desk, and brings `xfdesktop` back when the desk exits (for example with "Close desk" in the start menu). `install.sh` adds `~/.config/autostart/resolute.desktop`, which runs `resolute.sh --autostart`: at login the desk starts straight away and, for its first 20 seconds, closes `xfdesktop` if XFCE starts it, so the desk is never covered whichever starts first.

Startup takes about two seconds while the textures, the lamp and the globe are rendered. Once running, the desk uses about 200 MB of memory.

For development, `python3 -m resolute --screenshot out.png [--open files|documents|programs|note|menu]` renders one frame to a file and exits.

### Hiding the XFCE panel

The desk fills the whole screen. To have XFCE's panels get out of the way (each reappears when the pointer touches its screen edge), make them all auto-hide. This covers the top bar and, on Xubuntu, the dock at the bottom:

```
# always auto-hide
for p in $(xfconf-query -c xfce4-panel -p /panels | grep -E '^[0-9]+$'); do
    xfconf-query -c xfce4-panel -p /panels/panel-$p/autohide-behavior -n -t uint -s 2; done
# back to normal
for p in $(xfconf-query -c xfce4-panel -p /panels | grep -E '^[0-9]+$'); do
    xfconf-query -c xfce4-panel -p /panels/panel-$p/autohide-behavior -n -t uint -s 0; done
```

`setup-x11.sh` offers to do this when it is run inside an Xfce session.

### Screen shape

The desk is laid out for a 16:9 screen (1920×1080, 1600×900 and so on). On a taller screen (4:3, 16:10) it stays at the top and more of the desk shows below; on a wider one it sits between bars at the sides. Check yours with `xrandr | grep '*'`. A virtual machine stuck at 4:3 (often 1024×768) usually lacks its guest tools: `setup-x11.sh` offers them for VMware (`open-vm-tools-desktop`), VirtualBox and QEMU/KVM, and then the VM's screen can follow its window (in VMware, View > Autosize > Autofit Guest).

## Settings

Optional. Create `~/.config/resolute/config.toml` to override any of these:

```toml
documents_dir = "~/Documents"                # the DOCUMENTS drawer
files_start_dir = "~"                        # where the FILES drawer opens
note_file = "~/Documents/desk-note.txt"      # the quill's note paper
mail_url = "https://mail.google.com"         # the sealed letter
text_editor_command = "libreoffice --writer"
slideshow_command = "libreoffice --impress"
code_editor_command = "code"                 # VS Code in the PROGRAMS drawer
text_editor_fallback = "mousepad"            # used when Writer is not installed
browser_command = ""                         # empty = the system default browser
homepage = "https://duckduckgo.com"          # opened by the globe if no default browser is found
terminal_command = ""                        # empty = XFCE's preferred terminal
disk_path = "/"                              # filesystem shown on the DISK gauge
show_hidden_files = false                    # dot-files in the drawers
stats_interval_ms = 1500                     # how often the gauges update
```

Resolute also keeps what you set up on the desk in the same folder, so it is there after a restart:

- `programs.json`: programs added to the PROGRAMS drawer
- `shelves.json`: the books in the pigeon holes
- `stickies.json`: the sticky notes, with where they are and what is written on them

Delete a file to clear that part of the desk.

## How it works with X11

Resolute is an ordinary X11 program, not an X server or window manager. Xorg owns the screen and input, and xfwm4 (XFCE's window manager) arranges windows.

- **Becoming the desktop.** Before its window is shown, the desk sets its window type to `_NET_WM_WINDOW_TYPE_DESKTOP` with `xprop`. xfwm4 then keeps it below every other window, undecorated, on every workspace, and out of Alt+Tab.
- **The letter slots.** Once a second, a background thread reads the window manager's `_NET_CLIENT_LIST` and `_NET_ACTIVE_WINDOW` from the root window, and each window's title, `WM_CLASS` (used to find its icon), type and state, skipping panels, desktops and its own window.
- **Switching windows.** Clicking a card asks the window manager to activate or minimise that window through `xdotool`; Resolute never moves other programs' windows itself.
- **Menus and the note.** The start menu, the application picker for the pigeon holes and the audio device menu are Qt pop-ups. The note paper and the sticky notes are written with real text editors running in a hidden window; the desk forwards keys and clicks to them and draws their pages onto the desk in perspective.
- **Dragging programs in.** Dropping onto the PROGRAMS drawer uses the standard X11 drag-and-drop protocol (XDND), so launchers and programs can come from the start menu or from any file manager.

Wayland does not let a program mark itself as the desktop, read other programs' windows or control them in this way, which is why Resolute needs X11.

## Layout

- `resolute.sh`: starts the desk in place of `xfdesktop` (and `--autostart` mode for login); warns when the session is Wayland
- `install.sh`: adds or removes the login entry; warns when the session is Wayland
- `setup-x11.sh`: sets a Wayland/GNOME machine up with an Xfce session on X11 (Debian, Ubuntu, Arch), plus VM guest tools and auto-hiding panels
- `resolute/__main__.py`: command-line options (`--windowed`, `--screenshot`, `--open`)
- `resolute/app.py`: the desk window: scaling, the camera tilt into drawers, input, polling, repainting only what changed
- `resolute/config.py`: settings and their defaults
- `resolute/desk.py`: desk geometry and painting: organiser, letter slots, writing pad, drawers, gauge stand, the sealed letter (and, in the static layer, the sticky notes lying on the desk top)
- `resolute/drawers.py`: drawer animation and the FILES, DOCUMENTS and PROGRAMS contents (notepad, slides, the VS Code notebook and the cards for added programs)
- `resolute/startmenu.py`: the start menu (its entries can be dragged out), application list and power actions
- `resolute/gauges.py`: the bronze gauges
- `resolute/radio.py`, `resolute/audio.py`: the radio, controlling audio through `pactl`
- `resolute/taskslots.py`, `resolute/windows.py`: open-program cards, read with `xprop`, switched with `xdotool`
- `resolute/lamp.py`: the stained glass lamp, rendered per pixel with numpy
- `resolute/globe.py`: the globe, rendered per pixel with numpy
- `resolute/clock.py`: the mantel clock and its battery gauge
- `resolute/pencup.py`: the pen cup
- `resolute/note.py`: the inkwell and quill, and the note paper with its hidden editor
- `resolute/shelves.py`: the books standing in the pigeon holes, one per application
- `resolute/stickies.py`: the sticky-note pad and the notes peeled off it, with their hidden editor
- `resolute/system.py`: system stats, launching programs, opening files and URLs, power actions
- `resolute/textures.py`: lights the photographed wood and leather; generates the felt and wallpaper
- `resolute/assets/`: photographed wood and leather textures (CC0, from ambientCG; see `CREDITS.md`)
- `obj_inspo/`: the reference images the desk, dials, radio, lamp and clock were modelled on
