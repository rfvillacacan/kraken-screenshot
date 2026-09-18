#!/usr/bin/env python3
"""Minimal paste target that counts image Ctrl+V pastes."""
from __future__ import annotations

import sys

from PyQt5.QtGui import QImage
from PyQt5.QtWidgets import QApplication, QLabel, QTextEdit, QVBoxLayout, QWidget


class ImageEdit(QTextEdit):
    def __init__(self, on_image, parent=None) -> None:
        super().__init__(parent)
        self._on_image = on_image
        self.setAcceptRichText(True)

    def canInsertFromMimeData(self, source) -> bool:  # noqa: N802
        if source.hasImage() or "image/png" in source.formats():
            return True
        return super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:  # noqa: N802
        if source.hasImage() or "image/png" in source.formats():
            self._on_image()
            # Still insert so UI shows something
            if source.hasImage():
                img = source.imageData()
                if isinstance(img, QImage) and not img.isNull():
                    self.textCursor().insertImage(img)
                    return
            if "image/png" in source.formats():
                data = source.data("image/png")
                img = QImage.fromData(bytes(data), "PNG")
                if not img.isNull():
                    self.textCursor().insertImage(img)
                    return
        super().insertFromMimeData(source)


class PasteTarget(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PASTE-TARGET-COUNTER")
        self.count = 0
        self.label = QLabel("pastes: 0")
        self.edit = ImageEdit(self._bump)
        lay = QVBoxLayout(self)
        lay.addWidget(self.label)
        lay.addWidget(self.edit)
        self.resize(500, 400)

    def _bump(self) -> None:
        self.count += 1
        self.label.setText(f"pastes: {self.count}")
        print(f"PASTE_COUNT={self.count}", flush=True)


def main() -> int:
    app = QApplication(sys.argv)
    w = PasteTarget()
    w.show()
    w.raise_()
    w.activateWindow()
    w.edit.setFocus()
    print("READY", flush=True)
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
