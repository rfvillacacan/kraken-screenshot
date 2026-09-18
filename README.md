# Kraken Screenshot

Snap · queue · paste into any app — floating desktop capture for Linux (Wayland/X11).

**About the maker:** [Rolly Falco Villacacan](https://www.linkedin.com/in/rollyfalcovillacacan/)

## Features

- **Floating icon** — always on top, drag to move, double-click to expand/collapse
- **Select area** — interactive region capture
- **Fullscreen** — both monitors, or pick a single monitor
- **Side queue** — collapsible panel; every shot is queued with preview
- **Copy / Save / Delete / Clear** — use any queued shot later
- **Tray menu** — show, area capture, quit
- **Shortcuts** (while control panel is focused):
  - `Ctrl+Shift+A` area
  - `Ctrl+Shift+F` fullscreen
  - `Ctrl+Shift+C` copy selected
  - `Ctrl+Shift+Q` toggle queue
  - `Esc` collapse

## Requirements

- Python 3 + `python3-pyqt5`
- `flameshot` (recommended) or `scrot`
- Optional: `wl-clipboard` (`wl-copy`) for reliable Wayland clipboard

```bash
sudo apt install python3-pyqt5 flameshot scrot wl-clipboard
```

## Run

```bash
./run.sh
```

Or:

```bash
PYTHONPATH=. python3 -m screenshot_tool
```

## Backup policy

Before changes, create a timestamped archive under `backups/` and `/srv/ai/PROJECTS/backups/`.

## Layout

```
screenshot_tool/
  app.py            # controller
  capture.py        # flameshot/scrot backends
  queue.py          # shot queue + disk cache
  ui/               # floating icon, controls, queue panel, region overlay
data/captures/      # queued PNG cache
run.sh
```
