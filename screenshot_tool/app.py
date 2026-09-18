"""Application controller: wires floating icon, controls, queue, and capture."""

from __future__ import annotations

import sys
import tempfile
import zipfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QCursor, QGuiApplication, QIcon, QKeySequence, QPixmap
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QMessageBox,
    QShortcut,
    QSystemTrayIcon,
    QMenu,
    QAction,
)

from screenshot_tool.brand import APP_NAME, APP_TAGLINE
from screenshot_tool.capture import (
    capture_full,
    capture_monitor,
    capture_region_interactive,
    copy_pixmap_to_clipboard,
    copy_text_to_clipboard,
    list_monitors,
)
from screenshot_tool import insert as insert_ops
from screenshot_tool.queue import ShotQueue
from screenshot_tool.ui.floating_icon import FloatingIcon
from screenshot_tool.ui.main_shell import MainShell
from screenshot_tool.ui.region_overlay import RegionOverlay
from screenshot_tool.logging_setup import setup_logging, get_logger

log = get_logger("app")


class ScreenshotApp:
    def __init__(self, app: QApplication) -> None:
        self.app = app
        root = Path(__file__).resolve().parent.parent
        self.queue = ShotQueue(root / "data" / "captures")
        self.selected_id: Optional[str] = None
        self.expanded = False
        self.queue_visible = False  # hidden by default; Screenshot panel only
        self._overlay: Optional[RegionOverlay] = None
        self._suspend_outside_collapse = False
        self._last_external_window: Optional[str] = None
        self._last_target_click: Optional[tuple[int, int]] = None
        self._inserting = False
        self._insert_pixmaps: list = []
        self._insert_index = 0
        self._insert_target: Optional[str] = None
        self._insert_refocus: Optional[tuple[int, int]] = None
        self._insert_shown: Optional[dict] = None
        self._insert_timer = QTimer(self.app)
        self._insert_timer.setSingleShot(True)
        self._insert_timer.timeout.connect(self._insert_step)

        self.icon = FloatingIcon()
        self.shell = MainShell()
        self.panel = self.shell.controls
        self.queue_panel = self.shell.queue

        self.icon.toggled.connect(self.toggle_expanded)
        self.icon.moved_to.connect(self._on_icon_moved)

        self.panel.area_clicked.connect(self.capture_area)
        self.panel.fullscreen_clicked.connect(self.capture_fullscreen)
        self.panel.toggle_queue_clicked.connect(self.toggle_queue)
        self.panel.collapse_clicked.connect(self.collapse)
        self.panel.quit_clicked.connect(self.quit)
        self.shell.escape_pressed.connect(self._on_escape)

        self.queue_panel.copy_clicked.connect(self.copy_shot)
        self.queue_panel.copy_path_clicked.connect(self.copy_path_shot)
        self.queue_panel.insert_clicked.connect(self.insert_shot)
        self.queue_panel.insert_all_clicked.connect(self.insert_all)
        self.queue_panel.remove_clicked.connect(self.remove_shot)
        self.queue_panel.save_clicked.connect(self.save_shot)
        self.queue_panel.save_all_clicked.connect(self.save_all_zip)
        self.queue_panel.clear_clicked.connect(self.clear_queue)
        self.queue_panel.hide_clicked.connect(self.hide_queue)
        self.queue_panel.selection_changed.connect(self._on_selection)

        self._setup_tray()
        self._setup_shortcuts()
        self._setup_focus_tracker()
        self._place_initial()
        self.refresh_monitors()
        self.refresh_queue()

        self.icon.show()
        self.shell.hide()

    def _setup_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.tray = None
            return
        self.tray = QSystemTrayIcon(self.app)
        pix = QPixmap(64, 64)
        pix.fill(Qt.transparent)
        # Simple tray glyph via floating paint reuse: solid color icon
        from PyQt5.QtGui import QPainter, QColor

        p = QPainter(pix)
        p.setRenderHint(QPainter.Antialiasing)
        p.setBrush(QColor(31, 122, 140))
        p.setPen(Qt.NoPen)
        p.drawEllipse(4, 4, 56, 56)
        p.end()
        self.tray.setIcon(QIcon(pix))
        self.tray.setToolTip(f"{APP_NAME} — {APP_TAGLINE}")
        menu = QMenu()
        act_show = QAction("Show / Expand", menu)
        act_show.triggered.connect(self.expand)
        act_area = QAction("Select area", menu)
        act_area.triggered.connect(self.capture_area)
        act_unlock = QAction("Cancel insert / Reset UI", menu)
        act_unlock.triggered.connect(self._force_unlock_screen)
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(self.quit)
        menu.addAction(act_show)
        menu.addAction(act_area)
        menu.addAction(act_unlock)
        menu.addSeparator()
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.toggle_expanded()

    def _setup_shortcuts(self) -> None:
        QShortcut(QKeySequence("Ctrl+Shift+A"), self.shell, self.capture_area)
        QShortcut(QKeySequence("Ctrl+Shift+F"), self.shell, self.capture_fullscreen)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self.shell, self.copy_selected)
        QShortcut(QKeySequence("Ctrl+Shift+Q"), self.shell, self.toggle_queue)
        QShortcut(QKeySequence("Escape"), self.shell, self._on_escape)
        QShortcut(QKeySequence("Escape"), self.icon, self._on_escape)

    def _on_escape(self) -> None:
        if self._inserting:
            self._cancel_insert()
            return
        # 1st Esc closes drawer; 2nd Esc collapses to icon
        if self.expanded and self.shell.drawer_visible:
            self.hide_queue()
            return
        self.collapse()


    def _setup_focus_tracker(self) -> None:
        """Remember the last focused window that is not ours (for Insert paste)."""
        self._focus_timer = QTimer(self.app)
        self._focus_timer.setInterval(400)
        self._focus_timer.timeout.connect(self._poll_external_focus)
        self._focus_timer.start()
        QTimer.singleShot(0, self._poll_external_focus)
        self.app.applicationStateChanged.connect(self._on_app_state_changed)
        log.debug("Focus tracker started")

    def _our_window_ids(self) -> set[str]:
        widgets = [self.icon, self.shell]
        popup = getattr(self.queue_panel, "_zoom_popup", None)
        if popup is not None:
            widgets.append(popup)
        return insert_ops.window_ids_for_widgets(widgets)

    def _poll_external_focus(self) -> None:
        if self._inserting or self._suspend_outside_collapse:
            return
        if not insert_ops.xdotool_available():
            return
        wid = insert_ops.get_active_window_id()
        if not wid:
            return
        if wid in self._our_window_ids():
            return

        if wid != self._last_external_window:
            log.debug("Paste target window=%s", wid)
        self._last_external_window = wid

        # Only remember a click point if the cursor is inside that window.
        # Otherwise multi-monitor setups store a point on the wrong display
        # (e.g. over our queue) and the 2nd Insert All paste misses the field.
        pos = QCursor.pos()
        if insert_ops.point_in_window(wid, pos.x(), pos.y()):
            self._last_target_click = (pos.x(), pos.y())

    def _on_app_state_changed(self, state) -> None:
        if state != Qt.ApplicationActive:
            self._poll_external_focus()
            QTimer.singleShot(120, self._collapse_if_still_outside)
        else:
            self._poll_external_focus()

    def _collapse_if_still_outside(self) -> None:
        if not self.expanded or self._suspend_outside_collapse or self._inserting:
            return
        if QApplication.activeModalWidget() is not None:
            return
        if self._point_in_ui(QCursor.pos()):
            return
        log.info("Auto-collapse (app inactive)")
        self.collapse()

    def _point_in_ui(self, global_pos: QPoint) -> bool:
        for win in (self.icon, self.shell):
            if win.isVisible() and win.frameGeometry().contains(global_pos):
                return True
        popup = getattr(self.queue_panel, "_zoom_popup", None)
        if (
            popup is not None
            and popup.isVisible()
            and popup.frameGeometry().contains(global_pos)
        ):
            return True
        return False

    def _show_expanded_ui(self) -> None:
        """Show shell + icon — no fullscreen overlay."""
        self.queue_panel.hide_zoom()
        if not self.expanded:
            self.shell.hide()
            self.icon.show()
            self.icon.raise_()
            return
        self.shell.set_drawer_visible(self.queue_visible)
        self.shell.show()
        self.shell.raise_()
        self.icon.show()
        self.icon.raise_()
        log.debug(
            "UI shown expanded=%s drawer=%s",
            self.expanded,
            self.queue_visible,
        )

    def _force_unlock_screen(self) -> None:
        """Emergency reset if UI ever misbehaves."""
        log.warning("Force unlock / reset UI")
        self._insert_timer.stop()
        self._inserting = False
        self._suspend_outside_collapse = False
        self._insert_pixmaps = []
        self._insert_target = None
        self._insert_refocus = None
        self._insert_shown = None
        self.queue_panel.hide_zoom()
        self.shell.hide()
        self.expanded = False
        self.queue_visible = False
        self.icon.show()
        self.icon.raise_()
        QApplication.processEvents()

    def _place_initial(self) -> None:
        screen = QGuiApplication.primaryScreen()
        geo = screen.availableGeometry() if screen else None
        if geo:
            self.icon.move(geo.right() - 80, geo.center().y() - 28)
        else:
            self.icon.move(100, 100)
        self._reposition_shell()

    def _on_icon_moved(self, _pos: QPoint) -> None:
        if self.expanded:
            self._reposition_shell(force=False)

    def _reposition_shell(self, force: bool = True) -> None:
        icon_geo = self.icon.frameGeometry()
        self.shell.adjustSize()
        if force or not getattr(self.shell, "_user_placed", False):
            x = icon_geo.left() - self.shell.width() - 12
            y = icon_geo.top()
            if x < 8:
                x = icon_geo.right() + 12
            self.shell.move(x, y)
            self.shell._clamp_on_screen()

    def refresh_monitors(self) -> None:
        self.panel.set_monitors(list_monitors())
        self.shell.refresh_floor()

    def refresh_queue(self) -> None:
        self.queue_panel.refresh(self.queue, self.selected_id)
        sid = self.queue_panel.selected_id()
        self.selected_id = sid

    def toggle_expanded(self) -> None:
        if self.expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self) -> None:
        log.info("Expand")
        self.expanded = True
        self.refresh_monitors()
        self._reposition_shell(force=False)
        self._show_expanded_ui()

    def collapse(self) -> None:
        log.info("Collapse")
        if self._inserting:
            self._cancel_insert()
            return
        self.expanded = False
        self.queue_panel.hide_zoom()
        self.shell.hide()
        self.icon.show()
        self.icon.raise_()
        self._suspend_outside_collapse = False

    def toggle_queue(self) -> None:
        if not self.expanded:
            self.expand()
        self.queue_visible = not self.queue_visible
        self.shell.set_drawer_visible(self.queue_visible)
        self._reposition_shell(force=False)
        self._show_expanded_ui()

    def hide_queue(self) -> None:
        self.queue_visible = False
        self.shell.set_drawer_visible(False)
        self.shell.adjustSize()

    def _hide_ui_for_capture(self) -> None:
        self._suspend_outside_collapse = True
        self.shell.hide()
        self.icon.hide()
        QApplication.processEvents()

    def _restore_ui_after_capture(self) -> None:
        self.icon.show()
        if self.expanded:
            self._reposition_shell(force=False)
            self._show_expanded_ui()
        self.icon.raise_()
        QTimer.singleShot(250, self._resume_outside_collapse)

    def _resume_outside_collapse(self) -> None:
        self._suspend_outside_collapse = False

    @contextmanager
    def _dialog_mode(self) -> Iterator[None]:
        """Hide always-on-top UI so native dialogs are clickable."""
        self._suspend_outside_collapse = True
        self.queue_panel.hide_zoom()
        shown = {
            "icon": self.icon.isVisible(),
            "shell": self.shell.isVisible(),
        }
        self.icon.hide()
        self.shell.hide()
        QApplication.processEvents()
        try:
            yield
        finally:
            if shown["icon"] or not self.expanded:
                self.icon.show()
            if self.expanded and shown["shell"]:
                self._show_expanded_ui()
            self.icon.raise_()
            QTimer.singleShot(150, self._resume_outside_collapse)

    def _add_shot(self, pixmap: QPixmap, label: str) -> None:
        shot = self.queue.add(pixmap, label)
        self.selected_id = shot.id
        try:
            copy_pixmap_to_clipboard(pixmap)
        except Exception:
            pass
        self.refresh_queue()
        self.expanded = True
        # Keep queue visibility as the user left it (hidden by default)
        self._restore_ui_after_capture()

    def capture_area(self) -> None:
        self._hide_ui_for_capture()
        QTimer.singleShot(180, self._do_area_capture)

    def _do_area_capture(self) -> None:
        try:
            # Prefer flameshot interactive GUI (native, reliable on this host)
            pix = capture_region_interactive()
            if pix is not None:
                self._add_shot(pix, "Area")
                return
            # Fallback: custom overlay on a full capture
            full = capture_full()
            self._overlay = RegionOverlay(full)
            self._overlay.region_selected.connect(
                lambda p: self._add_shot(p, "Area")
            )
            self._overlay.cancelled.connect(self._restore_ui_after_capture)
            self._overlay.showFullScreen()
            self._overlay.raise_()
            self._overlay.activateWindow()
        except Exception as exc:
            self._restore_ui_after_capture()
            QMessageBox.warning(None, "Capture failed", str(exc))

    def capture_fullscreen(self) -> None:
        self._hide_ui_for_capture()
        QTimer.singleShot(180, self._do_fullscreen_capture)

    def _do_fullscreen_capture(self) -> None:
        try:
            mode, index = self.panel.selected_capture_target()
            if mode == "both":
                pix = capture_full()
                label = "Both monitors"
            else:
                assert index is not None
                pix = capture_monitor(index)
                monitors = list_monitors()
                name = monitors[index].name if index < len(monitors) else str(index)
                label = f"Monitor {name}"
            self._add_shot(pix, label)
        except Exception as exc:
            self._restore_ui_after_capture()
            QMessageBox.warning(None, "Capture failed", str(exc))

    def _on_selection(self, shot_id: Optional[str]) -> None:
        self.selected_id = shot_id

    def copy_selected(self) -> None:
        """Shortcut / tray helper: copy the currently selected shot."""
        sid = self.queue_panel.selected_id() or self.selected_id
        if not sid:
            log.warning("Copy: no selection")
            with self._dialog_mode():
                QMessageBox.information(
                    None, "Copy", "Select a screenshot in the queue first."
                )
            return
        self.copy_shot(sid)

    def copy_shot(self, shot_id: str) -> None:
        self.selected_id = shot_id
        shot = self.queue.get(shot_id)
        if shot is None:
            log.warning("Copy: missing shot id=%s", shot_id)
            return
        try:
            log.info("Copy shot id=%s", shot.id)
            copy_pixmap_to_clipboard(shot.pixmap)
            if self.tray is not None:
                self.tray.showMessage(
                    APP_NAME,
                    "Image copied to clipboard — Ctrl+V to paste",
                    QSystemTrayIcon.Information,
                    2000,
                )
        except Exception as exc:
            log.exception("Copy failed")
            with self._dialog_mode():
                QMessageBox.warning(None, "Copy failed", str(exc))

    def copy_path_selected(self) -> None:
        sid = self.queue_panel.selected_id() or self.selected_id
        if not sid:
            with self._dialog_mode():
                QMessageBox.information(
                    None, "Copy Path", "Select a screenshot in the queue first."
                )
            return
        self.copy_path_shot(sid)

    def copy_path_shot(self, shot_id: str) -> None:
        self.selected_id = shot_id
        shot = self.queue.get(shot_id)
        if shot is None:
            return
        path = shot.path
        if path is None or not path.exists():
            path = self.queue.storage_dir / (
                f"{shot.created_at.strftime('%Y%m%d-%H%M%S')}_{shot.id}.png"
            )
            if not shot.pixmap.save(str(path), "PNG"):
                with self._dialog_mode():
                    QMessageBox.warning(
                        None, "Copy Path failed", "Could not write cache file."
                    )
                return
            shot.path = path
        abs_path = str(path.resolve())
        if not path.exists():
            with self._dialog_mode():
                QMessageBox.warning(
                    None, "Copy Path failed", f"File missing:\n{abs_path}"
                )
            return
        try:
            log.info("Copy path id=%s → %s", shot.id, abs_path)
            copy_text_to_clipboard(abs_path)
            if self.tray is not None:
                self.tray.showMessage(
                    APP_NAME,
                    f"Path copied:\n{abs_path}",
                    QSystemTrayIcon.Information,
                    2500,
                )
        except Exception as exc:
            with self._dialog_mode():
                QMessageBox.warning(None, "Copy Path failed", str(exc))

    def insert_shot(self, shot_id: str) -> None:
        shot = self.queue.get(shot_id)
        if shot is None:
            return
        self._start_insert([QPixmap(shot.pixmap)])

    def insert_all(self) -> None:
        if not self.queue.shots:
            return
        pixmaps = [QPixmap(s.pixmap) for s in reversed(self.queue.shots)]
        self._start_insert(pixmaps)

    def _cancel_insert(self) -> None:
        self._insert_timer.stop()
        self._insert_pixmaps = []
        self._insert_index = 0
        self._restore_after_insert()
        if self.tray is not None:
            self.tray.showMessage(
                APP_NAME,
                "Insert cancelled",
                QSystemTrayIcon.Information,
                1500,
            )

    def _start_insert(self, pixmaps: list) -> None:
        log.info("Insert start count=%s target=%s", len(pixmaps), self._last_external_window)
        if self._inserting:
            return
        if not insert_ops.xdotool_available():
            with self._dialog_mode():
                QMessageBox.warning(
                    None,
                    "Insert unavailable",
                    "Insert needs xdotool.\nInstall: sudo apt install xdotool",
                )
            return
        target = self._last_external_window
        if not target:
            self._poll_external_focus()
            target = self._last_external_window
        if not target:
            with self._dialog_mode():
                QMessageBox.information(
                    None,
                    "Insert",
                    "No target window yet.\n"
                    "1) Click the target input field\n"
                    "2) Open Queue and use Insert / Insert All\n"
                    "(Tip: click the field once more after opening Queue so focus is remembered.)",
                )
            return

        # Freeze a safe in-window refocus point for multi-insert (or None)
        refocus = self._last_target_click
        if refocus is not None and not insert_ops.point_in_window(
            target, refocus[0], refocus[1]
        ):
            log.warning(
                "Discarding stale refocus %s (outside target %s)", refocus, target
            )
            refocus = None
        self._insert_refocus = refocus

        self._inserting = True
        self._suspend_outside_collapse = True
        self._insert_pixmaps = list(pixmaps)
        self._insert_index = 0
        self._insert_target = target
        self._insert_shown = {
            "icon": self.icon.isVisible(),
            "shell": self.shell.isVisible(),
            "expanded": self.expanded,
            "queue": self.queue_visible,
        }
        self.queue_panel.hide_zoom()
        self.icon.hide()
        self.shell.hide()
        QApplication.processEvents()

        if self.tray is not None:
            self.tray.showMessage(
                APP_NAME,
                f"Inserting {len(pixmaps)} image(s)… (Esc cancels)",
                QSystemTrayIcon.Information,
                2000,
            )
        QTimer.singleShot(80, self._insert_step)

    def _insert_step(self) -> None:
        if not self._inserting:
            return
        # Keep catcher down every step (safety)

        if self._insert_index >= len(self._insert_pixmaps):
            count = self._insert_index
            self._restore_after_insert()
            if self.tray is not None:
                self.tray.showMessage(
                    APP_NAME,
                    f"Inserted {count} image(s) (paste only, no Enter)",
                    QSystemTrayIcon.Information,
                    2500,
                )
            return

        pix = self._insert_pixmaps[self._insert_index]
        target = self._insert_target or ""
        try:
            log.debug("Insert step %s/%s", self._insert_index + 1, len(self._insert_pixmaps))
            # Refocus only with a validated in-window point (never cross-monitor)
            refocus = self._insert_refocus if self._insert_index > 0 else None
            insert_ops.paste_pixmap_into_window(pix, target, refocus=refocus)
        except Exception as exc:
            log.exception("Insert step failed")
            self._restore_after_insert()
            with self._dialog_mode():
                QMessageBox.warning(None, "Insert failed", str(exc))
            return

        self._insert_index += 1
        if self._insert_index >= len(self._insert_pixmaps):
            QTimer.singleShot(50, self._insert_step)
        else:
            self._insert_timer.start(insert_ops.PASTE_GAP_MS)

    def _restore_after_insert(self) -> None:
        log.info("Insert restore UI")
        self._insert_timer.stop()
        self._inserting = False
        self._insert_pixmaps = []
        self._insert_target = None
        self._insert_refocus = None
        shown = self._insert_shown or {
            "icon": True,
            "shell": False,
            "expanded": False,
            "queue": False,
        }
        self._insert_shown = None

        QApplication.processEvents()

        if shown.get("expanded"):
            self.expanded = True
            self.queue_visible = bool(shown.get("queue"))
            self._show_expanded_ui()
            self.icon.raise_()
        else:
            self.expanded = False
            self.shell.hide()
            self.icon.show()
            self.icon.raise_()
        QTimer.singleShot(150, self._resume_outside_collapse)

    def delete_selected(self) -> None:
        sid = self.queue_panel.selected_id() or self.selected_id
        if not sid:
            return
        self.remove_shot(sid)

    def remove_shot(self, shot_id: str) -> None:
        if not shot_id or self.queue.get(shot_id) is None:
            return
        log.info("Remove shot id=%s", shot_id)
        self.queue.remove(shot_id)
        if self.selected_id == shot_id:
            self.selected_id = None
        self.refresh_queue()

    def clear_queue(self) -> None:
        if not self.queue.shots:
            return
        with self._dialog_mode():
            reply = QMessageBox.question(
                None,
                "Clear queue",
                "Delete all queued screenshots?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
        if reply == QMessageBox.Yes:
            self.queue.clear()
            self.selected_id = None
            self.refresh_queue()

    def save_selected(self) -> None:
        sid = self.queue_panel.selected_id() or self.selected_id
        if not sid:
            with self._dialog_mode():
                QMessageBox.information(
                    None, "Save", "Select a screenshot in the queue first."
                )
            return
        self.save_shot(sid)

    def save_shot(self, shot_id: str) -> None:
        self.selected_id = shot_id
        shot = self.queue.get(shot_id)
        if shot is None:
            return
        with self._dialog_mode():
            path, _ = QFileDialog.getSaveFileName(
                None,
                "Save screenshot",
                str(Path.home() / f"screenshot-{shot.id}.png"),
                "PNG Image (*.png)",
            )
        if path:
            if not path.lower().endswith(".png"):
                path += ".png"
            if shot.pixmap.save(path, "PNG"):
                log.info("Saved shot id=%s → %s", shot.id, path)
            else:
                with self._dialog_mode():
                    QMessageBox.warning(None, "Save failed", "Could not write file.")

    def save_all_zip(self) -> None:
        if not self.queue.shots:
            with self._dialog_mode():
                QMessageBox.information(None, "Save All", "Queue is empty.")
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        with self._dialog_mode():
            path, _ = QFileDialog.getSaveFileName(
                None,
                "Save all screenshots as ZIP",
                str(Path.home() / f"screenshots-{stamp}.zip"),
                "ZIP archive (*.zip)",
            )
        if not path:
            return
        if not path.lower().endswith(".zip"):
            path += ".zip"
        try:
            with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for i, shot in enumerate(reversed(self.queue.shots), start=1):
                    safe_label = "".join(
                        c if c.isalnum() or c in "-_" else "_"
                        for c in shot.label.replace(" ", "_")
                    )
                    name = (
                        f"{i:03d}_{shot.created_at.strftime('%H%M%S')}"
                        f"_{safe_label}_{shot.id}.png"
                    )
                    if shot.path and shot.path.exists():
                        zf.write(shot.path, arcname=name)
                    else:
                        with tempfile.NamedTemporaryFile(
                            suffix=".png", delete=False
                        ) as tmp:
                            tmp_path = Path(tmp.name)
                        try:
                            shot.pixmap.save(str(tmp_path), "PNG")
                            zf.write(tmp_path, arcname=name)
                        finally:
                            tmp_path.unlink(missing_ok=True)
            with self._dialog_mode():
                QMessageBox.information(
                    None,
                    "Save All",
                    f"Saved {len(self.queue.shots)} screenshot(s) to:\n{path}",
                )
        except OSError as exc:
            with self._dialog_mode():
                QMessageBox.warning(None, "Save All failed", str(exc))

    def quit(self) -> None:
        log.info("Quit")
        self.app.quit()


def main(argv: Optional[list] = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    log_path = setup_logging()
    log.info("App starting (log=%s)", log_path)
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setQuitOnLastWindowClosed(False)
    controller = ScreenshotApp(app)
    log.info("UI ready")
    # Keep reference alive
    app._screenshot_controller = controller  # type: ignore[attr-defined]
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
