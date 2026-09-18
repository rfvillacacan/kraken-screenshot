"""Single frameless shell: Screenshot controls + optional queue side drawer."""

from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QGuiApplication, QMouseEvent, QPainter, QPaintEvent
from PyQt5.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from screenshot_tool.ui.control_panel import ControlPanel
from screenshot_tool.ui.draggable import DraggableWindowMixin
from screenshot_tool.ui.queue_panel import QueuePanel

_GRIP_SIZE = 18
_SAFE_MIN = 200  # absolute fallback only; real floor is natural content height


class _HeightGrip(QWidget):
    """Bottom-right grip tip: drag vertically to extend shell height."""

    def __init__(self, shell: "MainShell") -> None:
        super().__init__(shell)
        self._shell = shell
        self.setObjectName("heightGrip")
        self.setFixedSize(_GRIP_SIZE, _GRIP_SIZE)
        self.setCursor(Qt.SizeVerCursor)
        self.setToolTip("Drag to extend height (cannot shrink below default)")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._press_y: int | None = None
        self._start_h = 0

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(31, 122, 140, 28))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 4, 4)
        p.setBrush(QColor(31, 122, 140, 160))
        for x, y in ((4, 12), (8, 8), (8, 12), (12, 4), (12, 8), (12, 12)):
            p.drawEllipse(x, y, 2, 2)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._press_y = event.globalY()
            self._start_h = self._shell.height()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._press_y is None or not (event.buttons() & Qt.LeftButton):
            return
        dy = event.globalY() - self._press_y
        self._shell.apply_height(self._start_h + dy)
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._press_y = None
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._shell.reset_height()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)


class MainShell(DraggableWindowMixin, QWidget):
    """One window: controls on one side, queue drawer on the other."""

    escape_pressed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setObjectName("mainShell")
        self._init_draggable()
        self._drawer_visible = False
        self._drawer_on_right = True
        self._user_height: int | None = None
        self._floor_closed: int | None = None
        self._floor_open: int | None = None

        self.controls = ControlPanel(self)
        self.queue = QueuePanel(self)
        self.queue.hide()
        self.queue.setMinimumHeight(0)
        self.queue.setMinimumWidth(0)
        self.queue.setMaximumWidth(0)
        self.queue.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.controls.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        for handle in self.controls.drag_handles():
            self.register_drag_handle(handle)

        body = QWidget(self)
        self._row = QHBoxLayout(body)
        self._row.setContentsMargins(0, 0, 0, 0)
        self._row.setSpacing(0)
        self._row.addWidget(self.controls, 0)
        self._row.addWidget(self.queue, 1)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(body, 1)

        self._grip = _HeightGrip(self)
        self._grip.raise_()

        self.setMinimumHeight(_SAFE_MIN)
        self.setStyleSheet(
            """
            #mainShell {
                background: #f6f7f5;
                border: 1px solid #c9d0cc;
                border-radius: 14px;
            }
            """
        )
        self.controls.set_queue_open(False)

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._place_grip()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        # Capture natural default size the first time we appear (controls only)
        if self._floor_closed is None and not self._drawer_visible:
            self.adjustSize()
            self._remember_floor_from_current()
            self._apply_height_constraints()
            self.resize(self._natural_width(), self._current_floor())
        self._place_grip()

    def _place_grip(self) -> None:
        m = 4
        self._grip.move(
            self.width() - self._grip.width() - m,
            self.height() - self._grip.height() - m,
        )
        self._grip.raise_()

    def _natural_width(self) -> int:
        """Content-fitted width for the current drawer mode."""
        self.controls.ensurePolished()
        cw = max(
            self.controls.sizeHint().width(),
            self.controls.minimumWidth(),
            288,
        )
        if not self._drawer_visible:
            return cw
        self.queue.ensurePolished()
        qw = max(
            self.queue.sizeHint().width(),
            self.queue.minimumWidth(),
            400,
        )
        return cw + qw

    def _measure_natural_height(self) -> int:
        """Content-fitted height for the current drawer mode (no cropping)."""
        self.controls.ensurePolished()
        self.queue.ensurePolished()
        h = max(
            self.sizeHint().height(),
            self.controls.sizeHint().height(),
            self.controls.minimumSizeHint().height(),
        )
        if self._drawer_visible:
            h = max(
                h,
                self.queue.sizeHint().height(),
                self.queue.minimumSizeHint().height(),
                420,
            )
        return max(_SAFE_MIN, h)

    def _remember_floor_from_current(self) -> None:
        """Store default floor from natural layout for the current drawer mode."""
        natural = self._measure_natural_height()
        fitted = max(natural, self.height()) if self.isVisible() else natural
        if self._drawer_visible:
            self._floor_open = fitted
        else:
            self._floor_closed = fitted

    def refresh_floor(self) -> None:
        """Bump default floor after content changes (e.g. more monitors)."""
        natural = self._measure_natural_height()
        if self._drawer_visible:
            self._floor_open = max(self._floor_open or 0, natural)
        else:
            self._floor_closed = max(self._floor_closed or 0, natural)
        self._apply_height_constraints()
        if self._user_height is None and self.isVisible():
            self.resize(self._natural_width(), self._current_floor())
            self._place_grip()

    def _current_floor(self) -> int:
        if self._drawer_visible:
            return self._floor_open or self._floor_closed or self._measure_natural_height()
        return self._floor_closed or self._measure_natural_height()

    def _apply_height_constraints(self) -> None:
        floor = self._current_floor()
        self.setMinimumHeight(floor)
        if self._user_height is not None and self._user_height < floor:
            self._user_height = floor
        if self.height() < floor:
            self.resize(self.width(), floor)

    def _max_height(self) -> int:
        screen = (
            QGuiApplication.screenAt(self.frameGeometry().center())
            or QGuiApplication.primaryScreen()
        )
        floor = self._current_floor()
        if screen is None:
            return max(floor, 1200)
        return max(floor, int(screen.availableGeometry().height() * 0.92))

    def apply_height(self, height: int) -> None:
        floor = self._current_floor()
        h = max(floor, min(int(height), self._max_height()))
        self._user_height = h if h > floor else None
        self.resize(self.width(), h)
        self._clamp_on_screen()
        self._place_grip()

    def reset_height(self) -> None:
        """Double-click grip: back to default (natural) height."""
        self._user_height = None
        self.adjustSize()
        self._remember_floor_from_current()
        w = self._natural_width()
        h = self._current_floor()
        self.setMinimumHeight(h)
        self.resize(w, h)
        self._clamp_on_screen()
        self._place_grip()

    @property
    def drawer_visible(self) -> bool:
        return self._drawer_visible

    def set_drawer_visible(self, visible: bool) -> None:
        self._drawer_visible = bool(visible)
        self.queue.setVisible(self._drawer_visible)
        if not self._drawer_visible:
            self.queue.hide_zoom()
            # Prevent hidden drawer from holding stretch width in the layout
            self.queue.setMinimumWidth(0)
            self.queue.setMaximumWidth(0)
        else:
            self.queue.setMaximumWidth(16777215)
            self.queue.setMinimumWidth(400)
        self.controls.set_queue_open(self._drawer_visible)
        self._apply_drawer_side()

        saved_user = self._user_height
        self.adjustSize()
        self._remember_floor_from_current()
        floor = self._current_floor()
        self.setMinimumHeight(floor)

        # Always use natural width for this mode — never keep the previous wider size
        w = self._natural_width()
        if self._drawer_visible:
            self.setMaximumWidth(16777215)
        else:
            self.setMaximumWidth(w)

        if saved_user is not None and saved_user > floor:
            h = min(saved_user, self._max_height())
            self._user_height = h
        else:
            h = floor
            self._user_height = None
        self.resize(w, h)
        self._clamp_on_screen()
        self._place_grip()

    def toggle_drawer(self) -> None:
        self.set_drawer_visible(not self._drawer_visible)

    def _apply_drawer_side(self) -> None:
        """Prefer drawer to the right; flip left if it would fall off-screen."""
        self._row.removeWidget(self.controls)
        self._row.removeWidget(self.queue)

        on_right = True
        if self._drawer_visible:
            screen = (
                QGuiApplication.screenAt(self.frameGeometry().center())
                or QGuiApplication.primaryScreen()
            )
            if screen is not None:
                sg = screen.availableGeometry()
                need = self.controls.sizeHint().width() + 420 + 8
                if self.x() + need > sg.right() - 8 and self.x() - 420 > sg.left() + 8:
                    on_right = False

        self._drawer_on_right = on_right
        if on_right:
            self._row.addWidget(self.controls, 0)
            self._row.addWidget(self.queue, 1 if self._drawer_visible else 0)
        else:
            self._row.addWidget(self.queue, 1 if self._drawer_visible else 0)
            self._row.addWidget(self.controls, 0)

    def _clamp_on_screen(self) -> None:
        screen = (
            QGuiApplication.screenAt(self.frameGeometry().center())
            or QGuiApplication.primaryScreen()
        )
        if screen is None:
            return
        sg = screen.availableGeometry()
        g = self.frameGeometry()
        floor = self._current_floor()
        if g.height() > sg.height() - 8:
            self.resize(g.width(), max(floor, sg.height() - 8))
            g = self.frameGeometry()
        x = min(max(g.x(), sg.left() + 4), max(sg.left() + 4, sg.right() - g.width() - 4))
        y = min(max(g.y(), sg.top() + 4), max(sg.top() + 4, sg.bottom() - g.height() - 4))
        if (x, y) != (g.x(), g.y()):
            self.move(x, y)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Escape:
            self.escape_pressed.emit()
            event.accept()
            return
        super().keyPressEvent(event)
