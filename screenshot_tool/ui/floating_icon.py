"""Floating draggable icon that expands the control panel on double-click."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent
from PyQt5.QtWidgets import QApplication, QWidget


class FloatingIcon(QWidget):
    """Small always-on-top bubble: drag to move, double-click to expand.

    On Wayland, QWidget.move() is ignored. Interactive relocation must go
    through QWindow.startSystemMove(), ideally from the mouse-press handler.
    """

    toggled = pyqtSignal()
    moved_to = pyqtSignal(QPoint)

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(56, 56)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Kraken Screenshot — double-click to expand")

        self._press_global: QPoint | None = None
        self._drag_offset = QPoint()
        self._system_move = False

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        # Slightly opaque hit target so Wayland still receives clicks
        # on the full widget bounds (fully transparent pixels are often ignored).
        painter.setBrush(QColor(0, 0, 0, 1))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawEllipse(4, 6, 48, 48)
        painter.setBrush(QColor(24, 104, 120))
        painter.drawEllipse(2, 2, 48, 48)
        painter.setBrush(QColor(46, 160, 176))
        painter.drawEllipse(8, 8, 36, 36)
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(QFont("Sans Serif", 14, QFont.Bold))
        painter.drawText(self.rect().adjusted(0, -2, 0, 0), Qt.AlignCenter, "▣")

    def moveEvent(self, event) -> None:  # noqa: N802
        super().moveEvent(event)
        self.moved_to.emit(self.pos())

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            super().mousePressEvent(event)
            return

        self._press_global = QPoint(event.globalPos())
        self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        self._system_move = False
        self.setCursor(Qt.ClosedHandCursor)

        # Wayland requires startSystemMove during the press/serial.
        handle = self.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            self._system_move = bool(handle.startSystemMove())

        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not (event.buttons() & Qt.LeftButton) or self._press_global is None:
            return
        if self._system_move:
            event.accept()
            return
        # X11 / fallback when compositor rejected system move
        self.move(event.globalPos() - self._drag_offset)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.setCursor(Qt.OpenHandCursor)
        if event.button() == Qt.LeftButton:
            self.moved_to.emit(self.pos())
            self._press_global = None
            self._system_move = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self.toggled.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)
