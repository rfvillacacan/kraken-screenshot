"""Screenshot capture controls (embedded in MainShell)."""

from __future__ import annotations

from typing import List, Optional

from PyQt5.QtCore import Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices, QFont
from PyQt5.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from screenshot_tool.brand import (
    APP_ABOUT_LABEL,
    APP_ABOUT_URL,
    APP_NAME,
    APP_TAGLINE,
)
from screenshot_tool.capture import MonitorInfo


class ControlPanel(QWidget):
    """Capture actions: area / fullscreen / monitor pick / queue drawer / quit."""

    area_clicked = pyqtSignal()
    fullscreen_clicked = pyqtSignal()
    toggle_queue_clicked = pyqtSignal()
    collapse_clicked = pyqtSignal()
    quit_clicked = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("controlPanel")
        self.setMinimumWidth(288)
        self.setMaximumWidth(340)
        self._monitor_group = QButtonGroup(self)
        self._monitor_box = QVBoxLayout()
        self._drag_handles: list[QWidget] = []
        self._build()

    def drag_handles(self) -> list[QWidget]:
        return list(self._drag_handles)

    def set_queue_open(self, open_: bool) -> None:
        self.queue_btn.setText("Queue ▸" if open_ else "Queue")
        self.queue_btn.setToolTip(
            "Close queue drawer" if open_ else "Open queue side drawer"
        )

    def _open_about(self) -> None:
        QDesktopServices.openUrl(QUrl(APP_ABOUT_URL))

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(8)

        brand_col = QVBoxLayout()
        brand_col.setContentsMargins(0, 0, 0, 0)
        brand_col.setSpacing(0)
        title = QLabel(APP_NAME)
        title.setObjectName("brandTitle")
        title_font = QFont("Georgia", 13)
        title_font.setBold(True)
        title.setFont(title_font)
        tagline = QLabel(APP_TAGLINE)
        tagline.setObjectName("brandTagline")
        tagline.setWordWrap(True)
        brand_col.addWidget(title)
        brand_col.addWidget(tagline)

        drag_hint = QLabel("⠿")
        drag_hint.setObjectName("hint")
        drag_hint.setToolTip("Drag to move")
        collapse = QPushButton("–")
        collapse.setObjectName("iconBtn")
        collapse.setFixedSize(28, 28)
        collapse.setToolTip("Collapse to floating icon (Esc)")
        collapse.clicked.connect(self.collapse_clicked.emit)

        header_layout.addLayout(brand_col, 1)
        header_layout.addWidget(drag_hint, 0, Qt.AlignTop)
        header_layout.addWidget(collapse, 0, Qt.AlignTop)
        root.addWidget(header)
        self._drag_handles.extend([header, title, tagline, drag_hint])

        area_btn = QPushButton("Select area")
        area_btn.setObjectName("primaryBtn")
        area_btn.clicked.connect(self.area_clicked.emit)
        root.addWidget(area_btn)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setObjectName("divider")
        root.addWidget(divider)

        root.addWidget(QLabel("Full screen"))
        self._monitor_wrap = QWidget()
        self._monitor_wrap.setLayout(self._monitor_box)
        root.addWidget(self._monitor_wrap)

        full_btn = QPushButton("Capture fullscreen")
        full_btn.clicked.connect(self.fullscreen_clicked.emit)
        root.addWidget(full_btn)

        self.queue_btn = QPushButton("Queue")
        self.queue_btn.setToolTip("Open queue side drawer")
        self.queue_btn.clicked.connect(self.toggle_queue_clicked.emit)
        root.addWidget(self.queue_btn)

        quit_btn = QPushButton("Quit")
        quit_btn.setObjectName("dangerBtn")
        quit_btn.clicked.connect(self.quit_clicked.emit)
        root.addWidget(quit_btn)

        about = QPushButton(APP_ABOUT_LABEL)
        about.setObjectName("linkBtn")
        about.setCursor(Qt.PointingHandCursor)
        about.setToolTip(APP_ABOUT_URL)
        about.clicked.connect(self._open_about)
        root.addWidget(about)

        hint = QLabel("Drag header to move · Esc hides · Queue opens drawer")
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)
        root.addStretch(1)

        self.setStyleSheet(
            """
            #controlPanel {
                background: transparent;
                border: none;
                border-right: 1px solid #d5ddd9;
            }
            #brandTitle {
                font-size: 15px;
                font-weight: 700;
                color: #0f3d45;
                letter-spacing: 0.2px;
            }
            #brandTagline {
                color: #1f7a8c;
                font-size: 11px;
                margin-top: 2px;
            }
            QLabel { color: #2a3b3e; }
            #hint { color: #6a7a7d; font-size: 11px; }
            #divider { color: #d5ddd9; }
            QPushButton {
                background: #e8eeeb;
                border: 1px solid #c5cfca;
                border-radius: 8px;
                padding: 8px 10px;
                color: #17353a;
            }
            QPushButton:hover { background: #dce6e1; }
            QPushButton:pressed { background: #cfdad4; }
            #primaryBtn {
                background: #1f7a8c;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            #primaryBtn:hover { background: #186575; }
            #dangerBtn {
                background: #f3e8e6;
                border: 1px solid #dfc4bf;
                color: #7a3b32;
            }
            #linkBtn {
                background: transparent;
                border: none;
                color: #1f7a8c;
                text-align: left;
                padding: 4px 2px;
                font-size: 11px;
                text-decoration: underline;
            }
            #linkBtn:hover {
                color: #0f3d45;
                background: transparent;
            }
            #iconBtn {
                padding: 0;
                font-size: 16px;
                font-weight: 700;
            }
            QRadioButton { spacing: 8px; }
            """
        )

    def set_monitors(self, monitors: List[MonitorInfo]) -> None:
        while self._monitor_box.count():
            item = self._monitor_box.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        for btn in self._monitor_group.buttons():
            self._monitor_group.removeButton(btn)

        both = QRadioButton("Both monitors")
        both.setChecked(True)
        both.setProperty("monitor_mode", "both")
        self._monitor_group.addButton(both)
        self._monitor_box.addWidget(both)

        for m in monitors:
            rb = QRadioButton(m.label)
            rb.setProperty("monitor_mode", "single")
            rb.setProperty("monitor_index", m.index)
            self._monitor_group.addButton(rb)
            self._monitor_box.addWidget(rb)

    def selected_capture_target(self) -> tuple[str, Optional[int]]:
        btn = self._monitor_group.checkedButton()
        if btn is None:
            return "both", None
        mode = btn.property("monitor_mode")
        if mode == "single":
            return "single", int(btn.property("monitor_index"))
        return "both", None
