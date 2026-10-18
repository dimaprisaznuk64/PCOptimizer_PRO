"""In-app activity log: pages record finished actions, the dashboard shows them."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, slots=True)
class Entry:
    ts: float
    level: str  # "ok" | "warn" (partial) | "error" (nothing worked)
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
        self._health: tuple[int, str] | None = self._load_health()  # (score, grade) of the last health scan
        self.gaming_active = False  # last known Gaming Mode state (set by the Gaming page)

    @staticmethod
    def _health_path():
        from app.settings.service import data_root

        return data_root() / "health_last.json"

    def _load_health(self) -> tuple[int, str] | None:
        import json

        try:
            data = json.loads(self._health_path().read_text(encoding="utf-8"))
            return int(data["score"]), str(data["grade"])
        except (OSError, ValueError, KeyError, TypeError):
            return None

    @property
    def health(self) -> tuple[int, str] | None:
        return self._health

    @health.setter
    def health(self, value: tuple[int, str] | None) -> None:
        import json

        changed = self._health != value
        self._health = value
        if value is None:
            if changed:
                self.changed.emit()
            return
        try:
            path = self._health_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps({"score": value[0], "grade": value[1]}), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass
        if changed:
            self.changed.emit()

    @classmethod
    def instance(cls) -> ActivityLog:
        if cls._instance is None:
            cls._instance = ActivityLog()
        return cls._instance

    def record(self, title: str, detail: str = "", level: str = "ok") -> None:
        import time

        self._items.append(Entry(time.time(), level, title, detail))
        self.changed.emit()

    def set_health(self, score: int, grade: str) -> None:
        """Update the cached health score (persists across restarts)."""
        self.health = (score, grade)

    def entries(self, level: str | None = None, limit: int = 4) -> list[Entry]:
        items = [e for e in reversed(self._items) if level is None or e.level == level]
        return items[:limit]

    def clear(self) -> None:
        self._items.clear()
        self.changed.emit()


def record(title: str, detail: str = "", level: str = "ok") -> None:
    ActivityLog.instance().record(title, detail, level)


def outcome_level(*, has_errors: bool, achieved: bool) -> str:
    """Map an operation outcome to an activity-log level.

    Nothing worked and there were errors -> "error"; something was still done
    despite errors -> "warn"; clean run -> "ok".
    """
    if not has_errors:
        return "ok"
    return "warn" if achieved else "error"
