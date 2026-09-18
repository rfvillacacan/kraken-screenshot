"""File logging for screenshot tool diagnostics."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

_LOG = logging.getLogger("screenshot_tool")
_INITIALIZED = False


def setup_logging(log_dir: Path | None = None) -> Path:
    """Configure app-wide file + stderr logging. Returns log file path."""
    global _INITIALIZED
    if log_dir is None:
        log_dir = Path(__file__).resolve().parent.parent / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"app-{datetime.now().strftime('%Y%m%d')}.log"

    if _INITIALIZED:
        return log_path

    _LOG.setLevel(logging.DEBUG)
    _LOG.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    _LOG.addHandler(fh)

    sh = logging.StreamHandler(sys.stderr)
    sh.setLevel(logging.INFO)
    sh.setFormatter(fmt)
    _LOG.addHandler(sh)

    # Capture uncaught exceptions
    def _excepthook(exc_type, exc, tb):
        _LOG.error("Uncaught exception", exc_info=(exc_type, exc, tb))
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = _excepthook

    _INITIALIZED = True
    _LOG.info("Logging started → %s", log_path)
    return log_path


def get_logger(name: str = "screenshot_tool") -> logging.Logger:
    if name == "screenshot_tool":
        return _LOG
    return _LOG.getChild(name.removeprefix("screenshot_tool.").removeprefix("screenshot_tool"))
