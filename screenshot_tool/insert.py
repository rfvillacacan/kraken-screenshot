"""Paste queued screenshots into the last focused external window (no Enter)."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Set, Tuple

from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QApplication, QWidget

from screenshot_tool.capture import copy_pixmap_to_clipboard
from screenshot_tool.logging_setup import get_logger

log = get_logger("insert")

CLIPBOARD_SETTLE_SEC = 0.45
PASTE_GAP_MS = 2000
ACTIVATE_SETTLE_SEC = 0.12
XDOTOOL_TIMEOUT = 1.0


@dataclass(frozen=True)
class WindowGeom:
    x: int
    y: int
    width: int
    height: int

    def contains(self, px: int, py: int, *, margin: int = 2) -> bool:
        return (
            self.x - margin <= px <= self.x + self.width + margin
            and self.y - margin <= py <= self.y + self.height + margin
        )


def xdotool_available() -> bool:
    return shutil.which("xdotool") is not None


def _run_xdotool(
    args: List[str], *, timeout: float = XDOTOOL_TIMEOUT
) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["xdotool", *args],
        check=False,
        timeout=timeout,
        capture_output=True,
        text=True,
    )


def get_active_window_id() -> Optional[str]:
    if not xdotool_available():
        return None
    try:
        result = _run_xdotool(["getactivewindow"], timeout=1.0)
        out = (result.stdout or "").strip()
        return out or None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def window_geometry(window_id: str) -> Optional[WindowGeom]:
    """Parse ``xdotool getwindowgeometry`` for hit-testing click points."""
    if not window_id or not xdotool_available():
        return None
    try:
        result = _run_xdotool(
            ["getwindowgeometry", "--shell", str(window_id)], timeout=1.0
        )
    except subprocess.TimeoutExpired:
        return None
    if result.returncode != 0:
        return None
    vals: dict[str, int] = {}
    for line in (result.stdout or "").splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        try:
            vals[key.strip()] = int(raw.strip())
        except ValueError:
            continue
    try:
        return WindowGeom(vals["X"], vals["Y"], vals["WIDTH"], vals["HEIGHT"])
    except KeyError:
        return None


def point_in_window(window_id: str, px: int, py: int) -> bool:
    geom = window_geometry(window_id)
    return bool(geom and geom.contains(px, py))


def window_ids_for_widgets(widgets: Iterable[QWidget]) -> Set[str]:
    ids: Set[str] = set()
    for w in widgets:
        try:
            handle = w.windowHandle()
            if handle is not None:
                ids.add(str(int(handle.winId())))
            wid = int(w.winId())
            if wid:
                ids.add(str(wid))
        except Exception:
            continue
    return ids


def activate_window(window_id: str) -> None:
    try:
        _run_xdotool(["windowactivate", "--sync", str(window_id)], timeout=1.0)
    except subprocess.TimeoutExpired:
        try:
            _run_xdotool(["windowactivate", str(window_id)], timeout=0.8)
        except subprocess.TimeoutExpired:
            return
    time.sleep(ACTIVATE_SETTLE_SEC)


def send_paste_key() -> None:
    """Send Ctrl+V only — never Return/Enter."""
    try:
        _run_xdotool(["key", "--clearmodifiers", "ctrl+v"], timeout=1.0)
        log.debug("sent ctrl+v")
    except subprocess.TimeoutExpired:
        log.warning("ctrl+v timed out")


def click_point(global_x: int, global_y: int) -> None:
    """Click a screen point (used only when known to be inside the target)."""
    if not xdotool_available():
        return
    try:
        _run_xdotool(
            ["mousemove", "--sync", str(int(global_x)), str(int(global_y))],
            timeout=0.8,
        )
    except subprocess.TimeoutExpired:
        try:
            _run_xdotool(
                ["mousemove", str(int(global_x)), str(int(global_y))], timeout=0.5
            )
        except subprocess.TimeoutExpired:
            return
    time.sleep(0.03)
    try:
        _run_xdotool(["click", "1"], timeout=0.6)
    except subprocess.TimeoutExpired:
        log.debug("click timed out")
    time.sleep(0.06)


def paste_pixmap_into_window(
    pixmap: QPixmap,
    window_id: str,
    *,
    refocus: Optional[Tuple[int, int]] = None,
) -> None:
    """One paste cycle: activate → optional safe click → copy → Ctrl+V."""
    if pixmap.isNull():
        raise RuntimeError("Nothing to insert")
    if not window_id:
        raise RuntimeError("No target window to paste into")

    safe_refocus: Optional[Tuple[int, int]] = None
    if refocus is not None and point_in_window(window_id, refocus[0], refocus[1]):
        safe_refocus = refocus
    elif refocus is not None:
        log.warning(
            "Ignoring refocus %s — outside target window %s", refocus, window_id
        )

    log.info(
        "paste_pixmap window=%s size=%sx%s refocus=%s",
        window_id,
        pixmap.width(),
        pixmap.height(),
        safe_refocus,
    )

    pix = QPixmap(pixmap)
    activate_window(window_id)
    if safe_refocus is not None:
        click_point(safe_refocus[0], safe_refocus[1])
        activate_window(window_id)

    copy_pixmap_to_clipboard(pix)
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    time.sleep(CLIPBOARD_SETTLE_SEC)
    if app is not None:
        app.processEvents()

    activate_window(window_id)
    send_paste_key()
    if app is not None:
        app.processEvents()
    log.info("paste_pixmap done")
