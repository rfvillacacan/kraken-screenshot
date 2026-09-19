"""Hover-to-enlarge popup for queued screenshots."""

from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QGuiApplication, QPixmap
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class EnlargedPreview(QFrame):
    """Larger box showing a screenshot while hovering a queue thumbnail."""

    def __init__(self) -> None:
        super().__init__(None)
        # Stay above the click-catcher; do NOT use TransparentForInput —
        # that routed hover to the catcher and broke zoom.
        self.setWindowFlags(
            Qt.Window
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.setObjectName("enlargedPreview")
        self._label = QLabel()
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self._label)
        self.setStyleSheet(
            """
            #enlargedPreview {
                background: #f6f7f5;
                border: 2px solid #1f7a8c;
                border-radius: 10px;
            }
            """
        )

    def show_for_anchor(self, pixmap: QPixmap, anchor: QWidget) -> None:
        """Show a large preview beside the queue (uses global coordinates)."""
        if pixmap.isNull():
            self.hide()
            return

        center_global = anchor.mapToGlobal(anchor.rect().center())
        screen = QGuiApplication.screenAt(center_global)
        screen = screen or QGuiApplication.primaryScreen()
        max_w, max_h = 720, 520
        if screen:
            sg = screen.availableGeometry()
            max_w = min(int(sg.width() * 0.5), max(pixmap.width(), 320))
            max_h = min(int(sg.height() * 0.65), max(pixmap.height(), 240))

        scaled = pixmap.scaled(
            max_w, max_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self._label.setPixmap(scaled)
        self.adjustSize()

        top_left = anchor.mapToGlobal(anchor.rect().topLeft())
        bottom_right = anchor.mapToGlobal(anchor.rect().bottomRight())
        x = top_left.x() - self.width() - 12
        y = top_left.y()
        if screen:
            sg = screen.availableGeometry()
            if x < sg.left() + 8:
                x = bottom_right.x() + 12
            if y + self.height() > sg.bottom() - 8:
                y = max(sg.top() + 8, sg.bottom() - self.height() - 8)
            if y < sg.top() + 8:
                y = sg.top() + 8

        self.move(x, y)
        self.show()
        self.raise_()
