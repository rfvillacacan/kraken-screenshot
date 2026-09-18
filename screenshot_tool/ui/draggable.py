"""Shared drag behavior for frameless always-on-top panels (X11 + Wayland)."""

from __future__ import annotations

from PyQt5.QtCore import QPoint, Qt
from PyQt5.QtGui import QMouseEvent
from PyQt5.QtWidgets import QWidget


class DraggableWindowMixin:
    """Mixin: drag by a handle; always moves the top-level window()."""

    def _init_draggable(self) -> None:
        self._drag_handles: list[QWidget] = []
        self._press_global: QPoint | None = None
        self._drag_offset = QPoint()
        self._system_move = False
        self._user_placed = False

    def _drag_top(self) -> QWidget:
        """Top-level window to move (works when mixin is on a child too)."""
        return self.window()  # type: ignore[return-value]

    def register_drag_handle(self, widget: QWidget) -> None:
        widget.setProperty("dragHandle", True)
        widget.setCursor(Qt.OpenHandCursor)
        self._drag_handles.append(widget)
        widget.installEventFilter(self)  # type: ignore[arg-type]

    def _is_drag_source(self, widget: QWidget | None) -> bool:
        while widget is not None:
            if widget.property("dragHandle"):
                return True
            if widget is self:  # type: ignore[comparison-overlap]
                break
            widget = widget.parentWidget()
        return False

    def eventFilter(self, obj, event):  # noqa: N802
        if obj in self._drag_handles or (
            isinstance(obj, QWidget) and obj.property("dragHandle")
        ):
            et = event.type()
            if et == event.MouseButtonPress and isinstance(event, QMouseEvent):
                return self._handle_drag_press(event)
            if et == event.MouseMove and isinstance(event, QMouseEvent):
                return self._handle_drag_move(event)
            if et == event.MouseButtonRelease and isinstance(event, QMouseEvent):
                return self._handle_drag_release(event)
        return super().eventFilter(obj, event)  # type: ignore[misc]

    def _handle_drag_press(self, event: QMouseEvent) -> bool:
        if event.button() != Qt.LeftButton:
            return False
        top = self._drag_top()
        self._press_global = QPoint(event.globalPos())
        self._drag_offset = event.globalPos() - top.frameGeometry().topLeft()
        self._system_move = False
        for h in self._drag_handles:
            h.setCursor(Qt.ClosedHandCursor)

        handle = top.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            self._system_move = bool(handle.startSystemMove())
            if self._system_move:
                top_mixin = top
                if hasattr(top_mixin, "_user_placed"):
                    setattr(top_mixin, "_user_placed", True)
        return True

    def _handle_drag_move(self, event: QMouseEvent) -> bool:
        if not (event.buttons() & Qt.LeftButton) or self._press_global is None:
            return False
        if self._system_move:
            return True
        top = self._drag_top()
        top.move(event.globalPos() - self._drag_offset)
        if hasattr(top, "_user_placed"):
            setattr(top, "_user_placed", True)
        self._user_placed = True
        return True

    def _handle_drag_release(self, event: QMouseEvent) -> bool:
        for h in self._drag_handles:
            h.setCursor(Qt.OpenHandCursor)
        if event.button() == Qt.LeftButton:
            if self._press_global is not None:
                self._user_placed = True
                top = self._drag_top()
                if hasattr(top, "_user_placed"):
                    setattr(top, "_user_placed", True)
            self._press_global = None
            self._system_move = False
            return True
        return False
