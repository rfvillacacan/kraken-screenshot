# Kraken Screenshot

Snap · queue · paste into any app — floating desktop capture for Linux (Wayland/X11).

**About the maker:** [Rolly Falco Villacacan](https://www.linkedin.com/in/rollyfalcovillacacan/)

## Features

- **Floating icon** — always on top, drag to move, double-click to expand/collapse
- **Select area** — interactive region capture
- **Fullscreen** — both monitors, or pick a single monitor
- **Side queue** — collapsible drawer; every shot is queued with preview and zoom
- **Per-shot actions** — Insert · Copy (image) · Save · Path (file path) · Remove
- **Insert / Insert All** — paste into the last focused app via clipboard + Ctrl+V
- **Tray menu** — show, area capture, quit
- **Shortcuts** (while the control panel is focused):
  - `Ctrl+Shift+A` area
  - `Ctrl+Shift+F` fullscreen
  - `Ctrl+Shift+C` copy selected image
  - `Ctrl+Shift+Q` toggle queue
  - `Esc` collapse / close drawer

## Requirements

- Python 3 + `python3-pyqt5`
- `flameshot` (recommended) or `scrot`
- Optional: `wl-clipboard` (`wl-copy`) and/or `xclip` for clipboard

```bash
sudo apt install python3-pyqt5 flameshot scrot wl-clipboard xclip
```

## Start

From the project root:

```bash
./run.sh
```

Or:

```bash
cd /path/to/kraken-screenshot
PYTHONPATH=. QT_QPA_PLATFORM=xcb python3 -m screenshot_tool
```

Run in the background (log to a file):

```bash
./run.sh >> /tmp/screenshot-tool.log 2>&1 &
```

On GNOME Wayland, `run.sh` defaults to `QT_QPA_PLATFORM=xcb` so the floating window can be dragged. Override with:

```bash
QT_QPA_PLATFORM=wayland ./run.sh
```

## Stop

Quit from the **system tray** menu (**Quit**), or stop the process from a terminal:

```bash
pkill -f 'python3 -m screenshot_tool'
```

Confirm nothing is left running:

```bash
pgrep -af 'python3 -m screenshot_tool' || echo "stopped"
```

If a Path/Copy left a clipboard helper behind (rare), clear those too:

```bash
pkill -f 'kraken-screenshot/tools/(wl-copy|xclip)' 2>/dev/null || true
# or, for this checkout:
pkill -f 'screenshot-desktop/tools/(wl-copy|xclip)' 2>/dev/null || true
```

## Layout

```
screenshot_tool/   # app, capture, queue, UI
tools/             # wl-copy, xclip, verify_features.py
data/captures/     # queued PNG cache
run.sh             # launcher
```
