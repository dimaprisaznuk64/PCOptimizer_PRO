"""In-app activity log: pages record finished actions, the dashboard shows them."""

from __future__ import annotations

import json
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

_HISTORY_LIMIT = 200  # entries kept in memory (and reloaded at startup)
_COMPACT_AT = 500  # rewrite the file when it grows beyond this many lines
_KEEP_ON_COMPACT = 200  # newest lines kept when compacting
_READ_KEEP = 200  # read timestamps persisted for the notification center


@dataclass(frozen=True, slots=True)
class Entry:
    ts: float
    level: str  # "ok" | "warn" (partial) | "error" (nothing worked)
    title: str
    detail: str
    source: str = ""  # navigation key of the page that recorded the action

    @property
    def time_text(self) -> str:
        dt = datetime.fromtimestamp(self.ts)
        if dt.date() == datetime.now().date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d.%m %H:%M")

    def to_json(self) -> str:
        return json.dumps(
            {
                "ts": self.ts,
                "level": self.level,
                "title": self.title,
                "detail": self.detail,
                "source": self.source,
            }
        )

    @classmethod
    def from_json(cls, line: str) -> Entry | None:
        try:
            data = json.loads(line)
            return cls(
                float(data["ts"]),
                str(data["level"]),
                str(data["title"]),
                str(data.get("detail", "")),
                str(data.get("source", "")),
            )
        except (ValueError, KeyError, TypeError):
            return None


class ActivityLog(QObject):
    changed = Signal()
    _instance: ActivityLog | None = None

    def __init__(self) -> None:
        super().__init__()
        self._items: deque[Entry] = deque(maxlen=_HISTORY_LIMIT)
        self._health: tuple[int, str] | None = self._load_health()  # (score, grade) of the last health scan
        self.gaming_active = False  # last known Gaming Mode state (set by the Gaming page)
        self._read: set[float] = self._load_read()
        self._load_history()

    @staticmethod
    def _history_path() -> Path:
        from app.settings.service import data_root

        return data_root() / "activity.jsonl"

    def _load_history(self) -> None:
        """Restore the last N entries from activity.jsonl (newest first)."""
        try:
            lines = self._history_path().read_text(encoding="utf-8").splitlines()[-_HISTORY_LIMIT:]
        except OSError:
            return
        entries = [e for line in lines if (e := Entry.from_json(line)) is not None]
        self._items.extend(entries)

    def _append_history(self, entry: Entry) -> None:
        """Append one line; compact the file when it grows too long."""
        try:
            path = self._history_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as fh:
                fh.write(entry.to_json() + "\n")
            # Compact: keep only the newest lines so the file stays small.
            try:
                if path.stat().st_size > _COMPACT_AT * 80:  # rough line-count proxy
                    lines = path.read_text(encoding="utf-8").splitlines()
                    if len(lines) > _COMPACT_AT:
                        tmp = path.with_suffix(".tmp")
                        tmp.write_text("\n".join(lines[-_KEEP_ON_COMPACT:]) + "\n", encoding="utf-8")
                        tmp.replace(path)
            except OSError:
                pass
        except OSError:
            pass

    @staticmethod
    def _read_path() -> Path:
        from app.settings.service import data_root

        return data_root() / "activity_read.json"

    def _load_read(self) -> set[float]:
        try:
            values = json.loads(self._read_path().read_text(encoding="utf-8"))
            return {float(v) for v in values} if isinstance(values, list) else set()
        except (OSError, ValueError, TypeError):
            return set()

    def _write_read(self) -> None:
        oldest = self._items[0].ts if self._items else 0.0
        values = sorted(ts for ts in self._read if ts >= oldest)[-_READ_KEEP:]
        try:
            path = self._read_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(values), encoding="utf-8")
            tmp.replace(path)
        except OSError:
            pass

    def is_read(self, ts: float) -> bool:
        return ts in self._read

    def unread_count(self) -> int:
        return sum(1 for entry in self._items if entry.ts not in self._read)

    def mark_read(self, ts: float) -> None:
        if ts in self._read:
            return
        self._read.add(ts)
        self._write_read()
        self.changed.emit()

    def mark_all_read(self) -> None:
        if not self._items or all(entry.ts in self._read for entry in self._items):
            return
        self._read.update(entry.ts for entry in self._items)
        self._write_read()
        self.changed.emit()

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

    def record(
        self, title: str, detail: str = "", level: str = "ok", source: str = ""
    ) -> None:
        entry = Entry(time.time(), level, title, detail, source)
        self._items.append(entry)
        self._append_history(entry)
        self.changed.emit()

    def set_health(self, score: int, grade: str) -> None:
        """Update the cached health score (persists across restarts)."""
        self.health = (score, grade)

    def entries(self, level: str | None = None, limit: int | None = 4) -> list[Entry]:
        items = [e for e in reversed(self._items) if level is None or e.level == level]
        return items if limit is None else items[:limit]

    def clear(self) -> None:
        self._items.clear()
        self._read.clear()
        for path in (self._history_path(), self._read_path()):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self.changed.emit()


def record(title: str, detail: str = "", level: str = "ok", source: str = "") -> None:
    ActivityLog.instance().record(title, detail, level, source)


def outcome_level(*, has_errors: bool, achieved: bool) -> str:
    """Map an operation outcome to an activity-log level.

    Nothing worked and there were errors -> "error"; something was still done
    despite errors -> "warn"; clean run -> "ok".
    """
    if not has_errors:
        return "ok"
    return "warn" if achieved else "error"
