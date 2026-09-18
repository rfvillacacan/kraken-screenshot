#!/usr/bin/env bash
# Launch the floating screenshot utility.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:$PYTHONPATH}"

# GNOME Wayland ignores QWidget.move() for frameless windows.
# Prefer XWayland (xcb) when DISPLAY is available so drag works reliably.
# Override with: QT_QPA_PLATFORM=wayland ./run.sh
if [[ -z "${QT_QPA_PLATFORM:-}" && -n "${DISPLAY:-}" ]]; then
  export QT_QPA_PLATFORM=xcb
fi

exec python3 -m screenshot_tool "$@"
