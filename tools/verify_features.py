#!/usr/bin/env python3
"""Verify copy + multi-insert clipboard plumbing (no GUI clicks)."""
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
from screenshot_tool.capture import _tool, copy_pixmap_to_clipboard, copy_text_to_clipboard  # noqa: E402
from screenshot_tool.logging_setup import setup_logging  # noqa: E402


def _wl_png_len() -> int:
    wl = _tool("wl-paste")
    assert wl, "wl-paste missing"
    types = subprocess.check_output([wl, "--list-types"], text=True)
    assert "image/png" in types, f"clipboard types missing image/png:\n{types}"
    return len(subprocess.check_output([wl, "--type", "image/png"]))


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)

    caps = sorted((ROOT / "data" / "captures").glob("*.png"))
    assert len(caps) >= 2, "Need ≥2 captures in data/captures/"
    pixmaps = [QPixmap(str(p)) for p in caps[-2:]]
    assert all(not p.isNull() for p in pixmaps)

    print("tools wl-copy:", _tool("wl-copy"))
    print("tools xclip:", _tool("xclip"))
    print("xdotool:", insert_ops.xdotool_available())

    # --- Copy image ---
    t0 = time.time()
    copy_pixmap_to_clipboard(pixmaps[-1])
    elapsed = time.time() - t0
    assert elapsed < 2.0, f"copy_pixmap too slow ({elapsed:.2f}s) — likely hung"
    n = _wl_png_len()
    print(f"COPY OK ({n} bytes, {elapsed:.3f}s)")

    # --- Copy text ---
    t0 = time.time()
    copy_text_to_clipboard("/tmp/verify-path-test.png")
    assert time.time() - t0 < 2.0
    wl = _tool("wl-paste")
    txt = subprocess.check_output([wl, "--type", "text/plain"], text=True).strip()
    assert "verify-path-test.png" in txt, txt
    print("COPY PATH OK")

    # --- Multi-copy sequence (Insert All clipboard half) ---
    sizes: list[int] = []
    for i, pix in enumerate(pixmaps):
        t0 = time.time()
        copy_pixmap_to_clipboard(pix)
        assert time.time() - t0 < 2.0, f"multi-copy {i} hung"
        time.sleep(0.15)
        sizes.append(_wl_png_len())
        print(f"  multi-copy {i + 1}/{len(pixmaps)}: {sizes[-1]} bytes")
    assert all(s > 100 for s in sizes), sizes
    print("MULTI-COPY OK (Insert All clipboard path)")

    print("INSERT PLUMBING: xdotool=", insert_ops.xdotool_available(),
          "PASTE_GAP_MS=", insert_ops.PASTE_GAP_MS)
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
