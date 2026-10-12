"""In-app activity log: pages record finished actions, the dashboard shows them."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, slots=True)
class Entry:
    ts: float
    level: str  # "ok" | "warn"
    title: str
    detail: str

    @property
    def time_text(self) -> str:
        dt = datetime.fromtimestamp(self.ts)
        if dt.date() == datetime.now().date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d.%m %H:%M")


class ActivityLog(QObject):
    changed = Signal()
    _instance: ActivityLog | None = None

    def __init__(self) -> None:
        super().__init__()
        self._items: deque[Entry] = deque(maxlen=30)
        self.health: tuple[int, str] | None = None  # (score, grade) of the last health scan
        self.gaming_active = False  # last known Gaming Mode state (set by the Gaming page)

    @classmethod
    def instance(cls) -> ActivityLog:
        if cls._instance is None:
            cls._instance = ActivityLog()
        return cls._instance

    def record(self, title: str, detail: str = "", level: str = "ok") -> None:
        import time

        self._items.append(Entry(time.time(), level, title, detail))
        self.changed.emit()

    def entries(self, level: str | None = None, limit: int = 4) -> list[Entry]:
        items = [e for e in reversed(self._items) if level is None or e.level == level]
        return items[:limit]

    def clear(self) -> None:
        self._items.clear()
        self.changed.emit()


def record(title: str, detail: str = "", level: str = "ok") -> None:
    ActivityLog.instance().record(title, detail, level)
