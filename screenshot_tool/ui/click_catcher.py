"""Fullscreen transparent layer that catches outside clicks."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent
from PyQt5.QtWidgets import QWidget


class ClickCatcher(QWidget):
    """Covers all monitors; any click on it means 'outside' the floating UI."""

    clicked = pyqtSignal(QPoint)  # global position

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setCursor(Qt.ArrowCursor)
        self._cover_virtual_desktop()

    def _cover_virtual_desktop(self) -> None:
        bounds = None
        for screen in QGuiApplication.screens():
            g = screen.geometry()
            bounds = g if bounds is None else bounds.united(g)
        if bounds is not None:
            self.setGeometry(bounds)

    def showEvent(self, event) -> None:  # noqa: N802
        self._cover_virtual_desktop()
        super().showEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        # Fully transparent visually, but painted so input hits the window
        # (some compositors ignore completely empty translucent windows).
        del event
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.clicked.emit(QPoint(event.globalPos()))
            event.accept()
            return
        super().mousePressEvent(event)
