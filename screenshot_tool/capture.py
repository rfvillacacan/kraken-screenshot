"""Screenshot capture backends for Linux (Wayland/X11)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from PyQt5.QtCore import QByteArray, QMimeData
from PyQt5.QtGui import QGuiApplication, QPixmap
from PyQt5.QtWidgets import QApplication

from screenshot_tool.logging_setup import get_logger

log = get_logger("capture")

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def _tool(name: str) -> Optional[str]:
    """Prefer project-local tools/ then PATH."""
    local = _TOOLS_DIR / name
    if local.is_file() and os.access(local, os.X_OK):
        return str(local)
    return shutil.which(name)


@dataclass(frozen=True)
class MonitorInfo:
    index: int
    name: str
    x: int
    y: int
    width: int
    height: int
    is_primary: bool = False

    @property
    def label(self) -> str:
        primary = " (primary)" if self.is_primary else ""
        return f"{self.index}: {self.name}{primary} — {self.width}×{self.height}"


def list_monitors() -> List[MonitorInfo]:
    screens = QGuiApplication.screens()
    primary = QGuiApplication.primaryScreen()
    monitors: List[MonitorInfo] = []
    for i, screen in enumerate(screens):
        g = screen.geometry()
        monitors.append(
            MonitorInfo(
                index=i,
                name=screen.name() or f"Monitor-{i}",
                x=g.x(),
                y=g.y(),
                width=g.width(),
                height=g.height(),
                is_primary=screen is primary,
            )
        )
    if monitors:
        return monitors
    return _monitors_from_xrandr()


def _monitors_from_xrandr() -> List[MonitorInfo]:
    if not shutil.which("xrandr"):
        return []
    try:
        out = subprocess.check_output(["xrandr", "--listmonitors"], text=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    monitors: List[MonitorInfo] = []
    for line in out.splitlines()[1:]:
        line = line.strip()
        if not line:
            continue
        # e.g. 0: +*DP-3 1920/480x1080/270+1920+0  DP-3
        parts = line.split()
        if len(parts) < 3:
            continue
        idx = int(parts[0].rstrip(":"))
        is_primary = "*" in parts[1]
        geom = parts[1].lstrip("+*")
        # 1920/480x1080/270+1920+0
        try:
            size, pos = geom.split("+", 1)
            wh = size.split("x")
            w = int(wh[0].split("/")[0])
            h = int(wh[1].split("/")[0])
            pos_parts = pos.split("+")
            x = int(pos_parts[0])
            y = int(pos_parts[1]) if len(pos_parts) > 1 else 0
        except (ValueError, IndexError):
            continue
        name = parts[-1]
        monitors.append(
            MonitorInfo(idx, name, x, y, w, h, is_primary=is_primary)
        )
    return monitors


def _run(cmd: List[str], timeout: float = 60) -> None:
    subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)


def _load_png(path: Path) -> QPixmap:
    pix = QPixmap(str(path))
    if pix.isNull():
        raise RuntimeError(f"Failed to load capture: {path}")
    return pix


def capture_full() -> QPixmap:
    """Capture the entire virtual desktop (all monitors)."""
    with tempfile.TemporaryDirectory(prefix="ss-full-") as tmp:
        out = Path(tmp) / "full.png"
        if shutil.which("flameshot"):
            _run(["flameshot", "full", "-p", str(out)])
            if out.exists():
                return _load_png(out)
        if shutil.which("scrot"):
            _run(["scrot", str(out)])
            return _load_png(out)
        if shutil.which("grim"):
            _run(["grim", str(out)])
            return _load_png(out)
        raise RuntimeError(
            "No screenshot backend found. Install flameshot, scrot, or grim."
        )


def capture_monitor(index: int) -> QPixmap:
    """Capture a single monitor by Qt/flameshot screen index."""
    with tempfile.TemporaryDirectory(prefix="ss-mon-") as tmp:
        out = Path(tmp) / f"mon{index}.png"
        if shutil.which("flameshot"):
            _run(["flameshot", "screen", "-n", str(index), "-p", str(out)])
            if out.exists():
                return _load_png(out)
        # Fallback: full capture + crop
        monitors = list_monitors()
        if index < 0 or index >= len(monitors):
            raise RuntimeError(f"Monitor index out of range: {index}")
        full = capture_full()
        m = monitors[index]
        return full.copy(m.x, m.y, m.width, m.height)


def capture_region_interactive() -> Optional[QPixmap]:
    """
    Interactive region select via flameshot GUI.
    Returns None if the user cancels.
    """
    if not shutil.which("flameshot"):
        raise RuntimeError("Area select requires flameshot.")
    with tempfile.TemporaryDirectory(prefix="ss-area-") as tmp:
        out = Path(tmp) / "area.png"
        try:
            result = subprocess.run(
                [
                    "flameshot",
                    "gui",
                    "-p",
                    str(out),
                    "-s",  # accept on select
                ],
                timeout=300,
                capture_output=True,
            )
        except subprocess.TimeoutExpired:
            return None
        if result.returncode != 0 or not out.exists() or out.stat().st_size == 0:
            return None
        return _load_png(out)


def _pipe_to_clipboard_cmd(cmd: List[str], data: bytes, *, timeout: float = 1.0) -> bool:
    """Feed stdin to a clipboard helper.

    Never use capture_output=True: wl-copy/xclip may keep child FDs open and
    hang ``communicate()`` forever even after they daemonize.
    """
    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        assert proc.stdin is not None
        proc.stdin.write(data)
        proc.stdin.close()
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            # Still serving clipboard data — treat as success
            log.debug("%s still running (clipboard server)", cmd[0])
            return True
        return proc.returncode == 0
    except Exception as exc:
        log.debug("clipboard cmd failed %s: %s", cmd, exc)
        return False


def copy_pixmap_to_clipboard(pixmap: QPixmap) -> None:
    """Copy image for Wayland (wl-copy) and/or X11 (xclip), plus Qt mime."""
    if pixmap.isNull():
        raise RuntimeError("Nothing to copy")

    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication required for clipboard")

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        png_path = Path(f.name)
    try:
        if not pixmap.save(str(png_path), "PNG"):
            raise RuntimeError("Failed to encode PNG for clipboard")
        png_bytes = png_path.read_bytes()
        log.info(
            "Copy image %sx%s (%s bytes)",
            pixmap.width(),
            pixmap.height(),
            len(png_bytes),
        )

        wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
        ok = False

        # Wayland: wl-copy is authoritative. Skip Qt/xclip ownership fights.
        wl_copy = _tool("wl-copy")
        if wayland and wl_copy:
            if _pipe_to_clipboard_cmd(
                [wl_copy, "--type", "image/png"], png_bytes, timeout=0.4
            ):
                log.debug("wl-copy OK")
                ok = True

        # Qt mime (helps some X11 / in-process consumers)
        if not (wayland and ok):
            mime = QMimeData()
            mime.setData("image/png", QByteArray(png_bytes))
            mime.setImageData(pixmap.toImage())
            QApplication.clipboard().setMimeData(mime)
            app.processEvents()

        # X11 / XWayland: xclip when not already served by wl-copy
        if not ok:
            xclip = _tool("xclip")
            if xclip and _pipe_to_clipboard_cmd(
                [xclip, "-selection", "clipboard", "-t", "image/png"],
                png_bytes,
                timeout=0.4,
            ):
                log.debug("xclip OK")
                ok = True
            if not ok and wl_copy and _pipe_to_clipboard_cmd(
                [wl_copy, "--type", "image/png"], png_bytes, timeout=0.4
            ):
                log.debug("wl-copy OK (fallback)")
                ok = True

        if not ok:
            # Last resort: GTK helper
            try:
                helper = (
                    Path(__file__).resolve().parent.parent
                    / "tools"
                    / "gtk_clip_image.py"
                )
                r = subprocess.run(
                    ["python3", str(helper), str(png_path)],
                    check=False,
                    timeout=2,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                ok = r.returncode == 0
                log.debug("gtk-subprocess rc=%s", r.returncode)
            except Exception as exc:
                log.debug("gtk-subprocess skipped: %s", exc)

        if not ok:
            log.warning("Native clipboard helpers failed; Qt mime only")
        else:
            log.info("Copy image OK")
    finally:
        png_path.unlink(missing_ok=True)


def copy_text_to_clipboard(text: str) -> None:
    """Copy plain text for Wayland + X11 paste targets."""
    if not text:
        raise RuntimeError("Nothing to copy")

    app = QApplication.instance()
    if app is None:
        raise RuntimeError("QApplication required for clipboard")

    log.info("Copy text (%s chars)", len(text))
    wayland = bool(os.environ.get("WAYLAND_DISPLAY"))
    data = text.encode()

    wl_copy = _tool("wl-copy")
    if wayland and wl_copy:
        _pipe_to_clipboard_cmd([wl_copy, "--type", "text/plain"], data)
    else:
        QApplication.clipboard().setText(text)
        app.processEvents()
        if wl_copy:
            _pipe_to_clipboard_cmd([wl_copy, "--type", "text/plain"], data)
        xclip = _tool("xclip")
        if xclip:
            _pipe_to_clipboard_cmd(
                [xclip, "-selection", "clipboard", "-t", "text/plain"], data
            )
    log.info("Copy text OK")
