#!/usr/bin/env python3
"""Regression checks: Copy=image, Path=text, button wiring, clipboard clear."""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PyQt5.QtGui import QPixmap  # noqa: E402
from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

from screenshot_tool.capture import (  # noqa: E402
    _iter_our_clipboard_pids,
    _tool,
    copy_pixmap_to_clipboard,
    copy_text_to_clipboard,
)
from screenshot_tool.logging_setup import setup_logging  # noqa: E402
from screenshot_tool.queue import Shot  # noqa: E402
from screenshot_tool.ui.queue_panel import ShotRow  # noqa: E402
from screenshot_tool import insert as insert_ops  # noqa: E402


def _types() -> str:
    wl = _tool("wl-paste")
    assert wl
    return subprocess.check_output([wl, "--list-types"], text=True)


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    caps = sorted((ROOT / "data" / "captures").glob("*.png"))
    assert len(caps) >= 1, "Need captures"
    pix = QPixmap(str(caps[-1]))
    path = str(caps[-1].resolve())
    assert caps[-1].exists()

    print("xdotool:", insert_ops.xdotool_available())

    # Path then Copy must leave ONLY image (no leftover path text)
    copy_text_to_clipboard(path)
    time.sleep(0.15)
    assert "text/plain" in _types()
    copy_pixmap_to_clipboard(pix)
    time.sleep(0.25)
    types = _types()
    assert "image/png" in types, types
    assert "text/plain" not in types, f"path text leaked after Copy:\n{types}"
    raw = subprocess.check_output([_tool("wl-paste"), "--type", "image/png"])
    assert len(raw) > 100
    print("COPY IMAGE OK (clears prior path)")

    # Path must be text only, existing file
    copy_pixmap_to_clipboard(pix)
    time.sleep(0.15)
    copy_text_to_clipboard(path)
    time.sleep(0.2)
    types = _types()
    assert "text/plain" in types, types
    txt = subprocess.check_output(
        [_tool("wl-paste"), "--type", "text/plain"], text=True
    ).strip()
    assert txt == path, (txt, path)
    assert Path(txt).exists()
    print("COPY PATH OK", txt)

    # Repeated Path must not stack wl-copy/xclip servers
    for _ in range(5):
        copy_text_to_clipboard(path)
        time.sleep(0.05)
    helpers = _iter_our_clipboard_pids()
    assert len(helpers) <= 1, f"clipboard helpers stacked: {helpers}"
    print("NO STACKED HELPERS OK", helpers)

    # Row button mapping
    shot = Shot(
        id="regtest01",
        pixmap=pix,
        created_at=datetime.now(),
        label="reg",
        path=caps[-1],
    )
    row = ShotRow(shot)
    got: list[str] = []
    row.insert_clicked.connect(lambda _s: got.append("insert"))
    row.copy_clicked.connect(lambda _s: got.append("copy"))
    row.save_clicked.connect(lambda _s: got.append("save"))
    row.copy_path_clicked.connect(lambda _s: got.append("path"))
    row.remove_clicked.connect(lambda _s: got.append("remove"))
    labels = [b.text() for b in row.findChildren(QPushButton)]
    assert labels == ["Insert", "Copy", "Save", "Path", "Remove"], labels
    for b in row.findChildren(QPushButton):
        b.click()
    assert got == ["insert", "copy", "save", "path", "remove"], got
    print("ROW BUTTONS OK", labels)

    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
