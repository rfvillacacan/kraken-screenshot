"""Custom fullscreen region selector overlay (fallback when flameshot GUI is skipped)."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap
from PyQt5.QtWidgets import QWidget


class RegionOverlay(QWidget):
    """Dimmed fullscreen overlay; drag to select a crop region."""

    region_selected = pyqtSignal(QPixmap)
    cancelled = pyqtSignal()

    def __init__(self, background: QPixmap) -> None:
        super().__init__(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        self._bg = background
        self._origin: Optional[QPoint] = None
        self._current: Optional[QPoint] = None
        self.setCursor(Qt.CrossCursor)
        self.setMouseTracking(True)

        # Cover the full virtual desktop
        virtual = QRect()
        for screen in QGuiApplication.screens():
            virtual = virtual.united(screen.geometry())
        self.setGeometry(virtual)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._bg)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 110))
        sel = self._selection_rect()
        if sel is not None and sel.width() > 2 and sel.height() > 2:
            painter.drawPixmap(sel, self._bg, sel)
            painter.setPen(QPen(QColor(46, 160, 176), 2))
            painter.drawRect(sel.adjusted(0, 0, -1, -1))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(
                sel.left() + 6,
                max(18, sel.top() - 6),
                f"{sel.width()} × {sel.height()}",
            )

    def _selection_rect(self) -> Optional[QRect]:
        if self._origin is None or self._current is None:
            return None
        return QRect(self._origin, self._current).normalized()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._origin = event.pos()
            self._current = event.pos()
            self.update()
        elif event.button() == Qt.RightButton:
            self.cancelled.emit()
            self.close()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._origin is not None:
            self._current = event.pos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() != Qt.LeftButton:
            return
        sel = self._selection_rect()
        self._origin = None
        self._current = None
        if sel is not None and sel.width() >= 4 and sel.height() >= 4:
            cropped = self._bg.copy(sel)
            self.region_selected.emit(cropped)
            self.close()
        else:
            self.update()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.cancelled.emit()
            self.close()
        else:
            super().keyPressEvent(event)
