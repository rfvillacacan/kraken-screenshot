"""In-memory screenshot queue with optional disk cache."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from PyQt5.QtGui import QPixmap


@dataclass
class Shot:
    id: str
    pixmap: QPixmap
    created_at: datetime
    label: str
    path: Optional[Path] = None

    @property
    def title(self) -> str:
        ts = self.created_at.strftime("%H:%M:%S")
        return f"{ts} · {self.label}"


@dataclass
class ShotQueue:
    storage_dir: Path
    shots: List[Shot] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def add(self, pixmap: QPixmap, label: str) -> Shot:
        shot_id = uuid.uuid4().hex[:10]
        created = datetime.now()
        path = self.storage_dir / f"{created.strftime('%Y%m%d-%H%M%S')}_{shot_id}.png"
        pixmap.save(str(path), "PNG")
        shot = Shot(
            id=shot_id,
            pixmap=pixmap,
            created_at=created,
            label=label,
            path=path,
        )
        self.shots.insert(0, shot)  # newest first
        return shot

    def get(self, shot_id: str) -> Optional[Shot]:
        for shot in self.shots:
            if shot.id == shot_id:
                return shot
        return None

    def remove(self, shot_id: str) -> None:
        kept: List[Shot] = []
        for shot in self.shots:
            if shot.id == shot_id:
                if shot.path and shot.path.exists():
                    shot.path.unlink(missing_ok=True)
            else:
                kept.append(shot)
        self.shots = kept

    def clear(self) -> None:
        for shot in self.shots:
            if shot.path and shot.path.exists():
                shot.path.unlink(missing_ok=True)
        self.shots.clear()
