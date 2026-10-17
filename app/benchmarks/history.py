from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from app.settings import data_root

from .service import BenchmarkResult

_HISTORY_LIMIT = 1000


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """A single metric value captured at a point in time."""

    when: str
    metric: str
    value: float
    unit: str
    detail: str = ""
    baseline: bool = False

    def to_dict(self) -> dict:
        return {
            "when": self.when,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "detail": self.detail,
            "baseline": self.baseline,
        }

    @classmethod
    def from_dict(cls, data: object) -> HistoryEntry | None:
        if not isinstance(data, dict) or not {"when", "metric", "value", "unit"} <= set(data):
            return None
        try:
            value = float(data["value"])
        except (TypeError, ValueError):
            return None
        return cls(
            when=str(data["when"]),
            metric=str(data["metric"]),
            value=value,
            unit=str(data["unit"]),
            detail=str(data.get("detail", "")),
            baseline=bool(data.get("baseline", False)),
        )


class BenchmarkHistory:
    """Persistent log of benchmark results, for before/after comparison.

    Every run is stored as one entry per metric, stamped with the completion
    time. A *baseline* can be pinned per metric (usually right before an
    optimisation) so later runs report a percentage change against it. When no
    explicit baseline exists, the oldest recorded value of a metric acts as the
    implicit baseline.
    """

    def __init__(
        self,
        *,
        store: str | Path | None = None,
        now: Callable[[], float] | None = None,
    ) -> None:
        self.store = Path(store) if store else data_root() / "benchmark_history.json"
        self._now = now or time.time

    # ---------- read ----------

    def all(self) -> list[HistoryEntry]:
        """Every entry, oldest first."""
        entries: list[HistoryEntry] = []
        for raw in self._read():
            entry = HistoryEntry.from_dict(raw)
            if entry is not None:
                entries.append(entry)
        return entries

    def entries(self, limit: int = 100) -> list[HistoryEntry]:
        """The most recent entries, newest first."""
        items = self.all()
        items.reverse()
        return items[:limit] if limit else items

    def latest_of(self, metric: str) -> HistoryEntry | None:
        for entry in self.entries(limit=0):
            if entry.metric == metric:
                return entry
        return None

    def baseline_of(self, metric: str) -> HistoryEntry | None:
        """The newest pinned baseline for *metric*, else its oldest entry."""
        matching = [entry for entry in self.all() if entry.metric == metric]
        if not matching:
            return None
        pinned = [entry for entry in matching if entry.baseline]
        return pinned[-1] if pinned else matching[0]

    def has_baseline(self) -> bool:
        return any(entry.baseline for entry in self.all())

    def delta_pct(self, metric: str, value: float) -> float | None:
        """Percentage change of *value* against the baseline for *metric*."""
        baseline = self.baseline_of(metric)
        if baseline is None or baseline.value == 0:
            return None
        return (value - baseline.value) / baseline.value * 100.0

    # ---------- write ----------

    def record(self, results: Iterable[BenchmarkResult], *, baseline: bool = False) -> list[HistoryEntry]:
        when = datetime.fromtimestamp(self._now()).isoformat(timespec="seconds")
        fresh = [
            HistoryEntry(
                when=when,
                metric=result.metric,
                value=float(result.value),
                unit=result.unit,
                detail=result.detail,
                baseline=baseline,
            )
            for result in results
        ]
        if not fresh:
            return []
        data = self.all() + fresh
        self._write([entry.to_dict() for entry in data[-_HISTORY_LIMIT:]])
        return fresh

    def set_baseline(self) -> int:
        """Pin the newest entry of every metric as its baseline."""
        data = self.all()
        newest: dict[str, int] = {}
        for index, entry in enumerate(data):
            newest[entry.metric] = index
        updated: list[HistoryEntry] = []
        marked = 0
        for index, entry in enumerate(data):
            is_base = newest.get(entry.metric) == index
            if is_base:
                marked += 1
            updated.append(entry if entry.baseline == is_base else replace(entry, baseline=is_base))
        self._write([entry.to_dict() for entry in updated])
        return marked

    def clear_baseline(self) -> None:
        self._write([replace(e, baseline=False).to_dict() for e in self.all()])

    def clear(self) -> None:
        self._write([])

    # ---------- storage ----------

    def _read(self) -> list:
        if not self.store.exists():
            return []
        try:
            data = json.loads(self.store.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._quarantine()
            return []
        if not isinstance(data, list):
            self._quarantine()
            return []
        return data

    def _quarantine(self) -> None:
        try:
            stamp = time.strftime("%Y%m%d_%H%M%S")
            self.store.rename(self.store.with_name(f"{self.store.name}.corrupt-{stamp}"))
        except OSError:
            pass

    def _write(self, data: list) -> None:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store.with_suffix(self.store.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.store)
