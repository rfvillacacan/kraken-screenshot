# Kraken Screenshot

**Snap · queue · paste into any app** — floating desktop capture for Linux (Wayland/X11).

**About the maker:** [Rolly Falco Villacacan](https://www.linkedin.com/in/rollyfalcovillacacan/)

## Features

- Floating always-on-top icon (drag to move, double-click to expand)
- Area select + fullscreen / per-monitor capture
- Side **queue drawer** with per-shot Insert / Copy / Save / Path
- Insert / Insert All via Ctrl+V into the last focused app
- Hover zoom, height resize grip, Esc to collapse
- Tray menu + keyboard shortcuts

## Requirements (Ubuntu/Debian)

```bash
sudo apt install python3-pyqt5 flameshot scrot wl-clipboard xdotool
```

Optional: `scrot` is a fallback if flameshot is missing.

## Run

```bash
./run.sh
```

Or:

```bash
PYTHONPATH=. QT_QPA_PLATFORM=xcb python3 -m screenshot_tool
```

## Layout

```
screenshot_tool/   # application
tools/             # local wl-copy / xclip helpers + utilities
data/captures/     # runtime queue cache (empty in repo)
data/logs/         # runtime logs (empty in repo)
run.sh
```

## License

Private repository — all rights reserved unless otherwise stated by the author.
