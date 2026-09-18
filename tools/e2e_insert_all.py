#!/usr/bin/env python3
"""Simulate Insert All of last 2 captures into PASTE-TARGET-COUNTER."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtGui import QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from screenshot_tool import insert as insert_ops  # noqa: E402
from screenshot_tool.logging_setup import setup_logging  # noqa: E402


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    ids = subprocess.check_output(
        ["xdotool", "search", "--name", "PASTE-TARGET-COUNTER"], text=True
    ).strip().splitlines()
    for wid in ids:
        subprocess.run(["xdotool", "windowactivate", wid], check=False)
        time.sleep(0.05)
    time.sleep(0.15)
    wid = subprocess.check_output(["xdotool", "getactivewindow"], text=True).strip()
    geom = insert_ops.window_geometry(wid)
    assert geom, f"no geometry for {wid}"
    cx, cy = geom.x + geom.width // 2, geom.y + geom.height // 2
    insert_ops.click_point(cx, cy)
    time.sleep(0.1)

    caps = sorted((ROOT / "data" / "captures").glob("*.png"))[-2:]
    assert len(caps) == 2, caps
    pix = [QPixmap(str(p)) for p in caps]
    print("target", wid, "center", (cx, cy), "images", len(pix), flush=True)
    for i, p in enumerate(pix):
        ref = (cx, cy) if i else None
        insert_ops.paste_pixmap_into_window(p, wid, refocus=ref)
        print(f"sent {i + 1}/{len(pix)}", flush=True)
        app.processEvents()
        time.sleep(2.0)
    print("DONE", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
