"""Collapsible side panel listing queued screenshots."""

from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QEvent, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from screenshot_tool.queue import Shot, ShotQueue
from screenshot_tool.ui.zoom_preview import EnlargedPreview


class ShotRow(QWidget):
    """One queue row: thumb + title + Insert / Copy / Save / Path."""

    insert_clicked = pyqtSignal(str)
    copy_clicked = pyqtSignal(str)
    copy_path_clicked = pyqtSignal(str)
    save_clicked = pyqtSignal(str)
    row_pressed = pyqtSignal(str)
    hover_entered = pyqtSignal(str)
    hover_left = pyqtSignal(str)

    def __init__(self, shot: Shot, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.shot_id = shot.id
        self.setAttribute(Qt.WA_Hover, True)
        self.setMouseTracking(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        thumb = QLabel()
        thumb.setFixedSize(48, 36)
        thumb.setAlignment(Qt.AlignCenter)
        thumb.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        pix = shot.pixmap.scaled(48, 36, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        thumb.setPixmap(pix)
        layout.addWidget(thumb)

        title = QLabel(shot.title)
        title.setWordWrap(True)
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        layout.addWidget(title, 1)

        btns = QHBoxLayout()
        btns.setContentsMargins(0, 0, 0, 0)
        btns.setSpacing(3)

        for text, width, tip, slot in (
            ("Insert", 54, "Paste this image into the last focused app (Ctrl+V only)", self._on_insert),
            ("Copy", 48, "Copy this image to the clipboard", self._on_copy),
            ("Save", 48, "Save this image to a file", self._on_save),
            ("Path", 44, "Copy this image’s cached file path", self._on_copy_path),
        ):
            btn = QPushButton(text)
            btn.setObjectName("rowAction")
            btn.setFixedWidth(width)
            btn.setToolTip(tip)
            btn.clicked.connect(slot)
            # Buttons still count as “over this row” for zoom
            btn.installEventFilter(self)
            btns.addWidget(btn)

        layout.addLayout(btns)

    def _on_insert(self) -> None:
        self.row_pressed.emit(self.shot_id)
        self.insert_clicked.emit(self.shot_id)

    def _on_copy(self) -> None:
        self.row_pressed.emit(self.shot_id)
        self.copy_clicked.emit(self.shot_id)

    def _on_save(self) -> None:
        self.row_pressed.emit(self.shot_id)
        self.save_clicked.emit(self.shot_id)

    def _on_copy_path(self) -> None:
        self.row_pressed.emit(self.shot_id)
        self.copy_path_clicked.emit(self.shot_id)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.hover_entered.emit(self.shot_id)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.hover_left.emit(self.shot_id)
        super().leaveEvent(event)

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        # Keep zoom alive while the pointer is over row action buttons
        et = event.type()
        if et == QEvent.Enter:
            self.hover_entered.emit(self.shot_id)
        elif et == QEvent.Leave:
            # Only signal leave if cursor left the whole row
            QTimer.singleShot(0, self._emit_leave_if_outside)
        return False

    def _emit_leave_if_outside(self) -> None:
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            self.hover_left.emit(self.shot_id)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.row_pressed.emit(self.shot_id)
        super().mousePressEvent(event)


class QueuePanel(QWidget):
    """Queue drawer content (embedded in MainShell)."""

    copy_clicked = pyqtSignal(str)
    copy_path_clicked = pyqtSignal(str)
    insert_clicked = pyqtSignal(str)
    insert_all_clicked = pyqtSignal()
    remove_clicked = pyqtSignal()
    save_clicked = pyqtSignal(str)
    save_all_clicked = pyqtSignal()
    clear_clicked = pyqtSignal()
    hide_clicked = pyqtSignal()
    selection_changed = pyqtSignal(object)  # Optional[str]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("queuePanel")
        self.setMinimumWidth(400)
        self.setMinimumHeight(420)
        self._queue_ref: Optional[ShotQueue] = None
        self._zoom_popup = EnlargedPreview()
        self._hover_shot_id: Optional[str] = None
        self._zoom_hide_timer = QTimer(self)
        self._zoom_hide_timer.setSingleShot(True)
        self._zoom_hide_timer.setInterval(120)
        self._zoom_hide_timer.timeout.connect(self._hide_zoom_if_idle)
        self._build()
        self.update_action_states(has_selection=False, has_shots=False)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        title = QLabel("Queue")
        title.setObjectName("panelTitle")
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(64)
        close_btn.setToolTip("Close queue drawer (Esc)")
        close_btn.clicked.connect(self.hide_clicked.emit)
        header_layout.addWidget(title)
        header_layout.addStretch(1)
        header_layout.addWidget(close_btn)
        root.addWidget(header)

        hint = QLabel(
            "Hover row to zoom · Per-row Insert/Copy/Save/Path · Click target before Insert"
        )
        hint.setObjectName("hint")
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.list = QListWidget()
        self.list.setMouseTracking(True)
        self.list.viewport().setMouseTracking(True)
        self.list.setSpacing(4)
        self.list.currentItemChanged.connect(self._on_current_changed)
        self.list.viewport().installEventFilter(self)
        root.addWidget(self.list, 1)

        self.insert_all_btn = QPushButton("Insert All")
        self.insert_all_btn.setObjectName("primaryBtn")
        self.insert_all_btn.setToolTip(
            "Paste every queued image into the last focused app (Ctrl+V only, no Enter)"
        )
        self.insert_all_btn.clicked.connect(self.insert_all_clicked.emit)
        root.addWidget(self.insert_all_btn)

        extras = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setToolTip("Remove selected screenshot from the queue")
        self.remove_btn.clicked.connect(self.remove_clicked.emit)
        extras.addWidget(self.remove_btn)
        root.addLayout(extras)

        batch = QHBoxLayout()
        self.save_all_btn = QPushButton("Save All")
        self.save_all_btn.setToolTip("Zip all queued screenshots and choose where to save")
        self.save_all_btn.clicked.connect(self.save_all_clicked.emit)
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setToolTip("Clear all queued screenshots")
        self.clear_btn.clicked.connect(self.clear_clicked.emit)
        batch.addWidget(self.save_all_btn)
        batch.addWidget(self.clear_btn)
        root.addLayout(batch)

        self.count_label = QLabel("0 shots")
        self.count_label.setObjectName("hint")
        root.addWidget(self.count_label)

        self.setStyleSheet(
            """
            #queuePanel {
                background: transparent;
                border: none;
            }
            #panelTitle {
                font-size: 16px;
                font-weight: 700;
                color: #17353a;
            }
            #hint { color: #6a7a7d; font-size: 11px; }
            QListWidget {
                background: #ffffff;
                border: 1px solid #d0d8d3;
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 2px;
                border-radius: 6px;
            }
            QListWidget::item:selected {
                background: #d5ebea;
                color: #17353a;
            }
            QListWidget::item:hover {
                background: #e7f2f1;
            }
            QPushButton {
                background: #e8eeeb;
                border: 1px solid #c5cfca;
                border-radius: 8px;
                padding: 8px 10px;
                color: #17353a;
            }
            QPushButton#rowAction {
                padding: 4px 4px;
                font-size: 11px;
                border-radius: 6px;
            }
            QPushButton:hover:!disabled { background: #dce6e1; }
            QPushButton:disabled {
                background: #eef1ef;
                color: #9aa6a8;
                border: 1px solid #d7deda;
            }
            #primaryBtn {
                background: #1f7a8c;
                color: #ffffff;
                border: none;
                font-weight: 600;
            }
            #primaryBtn:disabled {
                background: #a9c5cb;
                color: #eef6f7;
            }
            """
        )

    def eventFilter(self, obj, event) -> bool:  # noqa: N802
        if obj is self.list.viewport() and event.type() == QEvent.Leave:
            self._schedule_zoom_hide()
        return super().eventFilter(obj, event)

    def _on_row_hover_enter(self, shot_id: str) -> None:
        self._zoom_hide_timer.stop()
        self._hover_shot_id = shot_id
        self._show_zoom(shot_id)

    def _on_row_hover_leave(self, shot_id: str) -> None:
        if self._hover_shot_id == shot_id:
            self._schedule_zoom_hide()

    def _schedule_zoom_hide(self) -> None:
        self._zoom_hide_timer.start()

    def _hide_zoom_if_idle(self) -> None:
        # Still over the list? keep or switch — don’t flicker on brief leaves
        pos = self.list.viewport().mapFromGlobal(QCursor.pos())
        if self.list.viewport().rect().contains(pos):
            item = self.list.itemAt(pos)
            if item is not None:
                shot_id = item.data(Qt.UserRole)
                if shot_id:
                    self._hover_shot_id = shot_id
                    self._show_zoom(shot_id)
                    return
        self._hover_shot_id = None
        self._zoom_popup.hide()

    def _show_zoom(self, shot_id: str) -> None:
        if self._queue_ref is None:
            return
        shot = self._queue_ref.get(shot_id)
        if shot is None:
            self._zoom_popup.hide()
            return
        self._zoom_popup.show_for_anchor(shot.pixmap, self)

    def hide_zoom(self) -> None:
        self._zoom_hide_timer.stop()
        self._hover_shot_id = None
        self._zoom_popup.hide()

    def update_action_states(self, *, has_selection: bool, has_shots: bool) -> None:
        self.remove_btn.setEnabled(has_selection)
        self.save_all_btn.setEnabled(has_shots)
        self.clear_btn.setEnabled(has_shots)
        self.insert_all_btn.setEnabled(has_shots)

    def refresh(self, queue: ShotQueue, selected_id: Optional[str] = None) -> None:
        self._queue_ref = queue
        self.hide_zoom()
        self.list.clear()
        for shot in queue.shots:
            item = QListWidgetItem()
            item.setData(Qt.UserRole, shot.id)
            item.setSizeHint(QSize(0, 54))
            self.list.addItem(item)
            row = ShotRow(shot)
            row.insert_clicked.connect(self.insert_clicked.emit)
            row.copy_clicked.connect(self.copy_clicked.emit)
            row.copy_path_clicked.connect(self.copy_path_clicked.emit)
            row.save_clicked.connect(self.save_clicked.emit)
            row.row_pressed.connect(self._select_shot)
            row.hover_entered.connect(self._on_row_hover_enter)
            row.hover_left.connect(self._on_row_hover_leave)
            self.list.setItemWidget(item, row)
            if selected_id and shot.id == selected_id:
                self.list.setCurrentItem(item)
        if self.list.count() and self.list.currentItem() is None:
            self.list.setCurrentRow(0)
        self.count_label.setText(f"{len(queue.shots)} shot(s)")
        self.update_action_states(
            has_selection=self.selected_id() is not None,
            has_shots=len(queue.shots) > 0,
        )

    def selected_id(self) -> Optional[str]:
        item = self.list.currentItem()
        if item is None:
            return None
        return item.data(Qt.UserRole)

    def _select_shot(self, shot_id: str) -> None:
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item and item.data(Qt.UserRole) == shot_id:
                self.list.setCurrentItem(item)
                break

    def _on_current_changed(self, current: Optional[QListWidgetItem], _prev) -> None:
        shot_id = current.data(Qt.UserRole) if current else None
        self.update_action_states(
            has_selection=shot_id is not None,
            has_shots=self.list.count() > 0,
        )
        self.selection_changed.emit(shot_id)

    def hideEvent(self, event) -> None:  # noqa: N802
        self.hide_zoom()
        super().hideEvent(event)
