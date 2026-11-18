from __future__ import annotations

import json
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from app.settings import data_root

CADENCE_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
DEFAULT_CADENCE = "weekly"
_DAY_SECONDS = 86400


def _cadence_days(value: object) -> int:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(1, int(value))
    text = str(value or DEFAULT_CADENCE).strip().lower()
    if text in CADENCE_DAYS:
        return CADENCE_DAYS[text]
    try:
        return max(1, int(text))
    except ValueError:
        return CADENCE_DAYS[DEFAULT_CADENCE]


@dataclass(frozen=True, slots=True)
class CleanerSchedule:
    enabled: bool = False
    cadence: str = DEFAULT_CADENCE
    target_ids: tuple[str, ...] = ()
    last_run: float = 0.0

    @property
    def cadence_days(self) -> int:
        return _cadence_days(self.cadence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "cadence": self.cadence,
            "cadence_days": self.cadence_days,
            "target_ids": list(self.target_ids),
            "last_run": self.last_run,
        }

    @classmethod
    def from_dict(cls, data: object) -> CleanerSchedule:
        if not isinstance(data, dict):
            return cls()
        cadence = data.get("cadence")
        if cadence in (None, ""):
            days = data.get("cadence_days")
            cadence = str(days) if days is not None else DEFAULT_CADENCE
        raw_ids = data.get("target_ids")
        ids = tuple(dict.fromkeys(str(item) for item in raw_ids)) if isinstance(raw_ids, list) else ()
        try:
            last_run = float(data.get("last_run", 0.0) or 0.0)
        except (TypeError, ValueError):
            last_run = 0.0
        return cls(
            enabled=bool(data.get("enabled", False)),
            cadence=str(cadence),
            target_ids=ids,
            last_run=last_run,
        )


class CleanerScheduler:
    def __init__(
        self,
        store: str | os.PathLike[str] | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.store = Path(store) if store is not None else data_root() / "cleaner_schedule.json"
        self._now = now or time.time
        self._schedule = self.load()

    @property
    def schedule(self) -> CleanerSchedule:
        return self._schedule

    @property
    def enabled(self) -> bool:
        return self._schedule.enabled

    @property
    def cadence(self) -> str:
        return self._schedule.cadence

    @property
    def cadence_days(self) -> int:
        return self._schedule.cadence_days

    @property
    def target_ids(self) -> tuple[str, ...]:
        return self._schedule.target_ids

    @property
    def last_run(self) -> float:
        return self._schedule.last_run

    def load(self) -> CleanerSchedule:
        try:
            with self.store.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            data = None
        self._schedule = CleanerSchedule.from_dict(data)
        return self._schedule

    def save(self, schedule: CleanerSchedule | None = None) -> CleanerSchedule:
        if schedule is not None:
            self._schedule = schedule
        self.store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store.with_name(self.store.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(self._schedule.to_dict(), handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.store)
        return self._schedule

    def set_enabled(self, enabled: bool) -> CleanerSchedule:
        return self.save(replace(self._schedule, enabled=bool(enabled)))

    def set_cadence(self, cadence: str) -> CleanerSchedule:
        return self.save(replace(self._schedule, cadence=str(cadence)))

    def set_target_ids(self, target_ids: Sequence[str]) -> CleanerSchedule:
        ids = tuple(dict.fromkeys(str(item) for item in target_ids))
        return self.save(replace(self._schedule, target_ids=ids))

    def mark_run(self) -> CleanerSchedule:
        return self.save(replace(self._schedule, last_run=self._now()))

    def is_due(self, schedule: CleanerSchedule | None = None, *, now: float | None = None) -> bool:
        current = schedule if schedule is not None else self._schedule
        if not current.enabled or not current.target_ids:
            return False
        current_time = self._now() if now is None else now
        return current_time - current.last_run >= current.cadence_days * _DAY_SECONDS
