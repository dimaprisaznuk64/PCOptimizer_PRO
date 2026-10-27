from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.settings import data_root

log = logging.getLogger("pcoptimizer.history")

_DEFAULT_STORE = "performance_history.jsonl"
_SAMPLE_INTERVAL_S = 30.0


@dataclass(frozen=True, slots=True)
class HistorySample:
    """One recorded sensor snapshot at a point in time."""

    ts: float
    cpu: float | None = None
    ram: float | None = None
    gpu: float | None = None
    gpu_mem: float | None = None
    temp_cpu: float | None = None
    temp_gpu: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        out: dict[str, float | None] = {"ts": round(self.ts, 1)}
        for key in ("cpu", "ram", "gpu", "gpu_mem", "temp_cpu", "temp_gpu"):
            value = getattr(self, key)
            out[key] = round(value, 1) if value is not None else None
        return out

    @classmethod
    def from_dict(cls, d: dict) -> HistorySample | None:
        try:
            return cls(
                ts=float(d["ts"]),
                cpu=d.get("cpu"),
                ram=d.get("ram"),
                gpu=d.get("gpu"),
                gpu_mem=d.get("gpu_mem"),
                temp_cpu=d.get("temp_cpu"),
                temp_gpu=d.get("temp_gpu"),
            )
        except (KeyError, TypeError, ValueError):
            return None


class PerformanceHistory:
    """Append-only JSONL log of sensor samples for long-term trend charts.

    Records one line per sample, throttled to at most one write every
    ``SAMPLE_INTERVAL_S`` seconds.  Old entries are trimmed on read so the
    file never grows beyond ``max_age_hours``; a rewritten store is written
    back atomically when trimming/dropping corrupt lines.
    """

    SAMPLE_INTERVAL_S = _SAMPLE_INTERVAL_S

    def __init__(
        self,
        store: Path | str | None = None,
        max_age_hours: float = 24.0,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._store = Path(store) if store else data_root() / _DEFAULT_STORE
        self._max_age_s = max_age_hours * 3600.0
        self._now = now or time.time
        self._last_record = 0.0

    @property
    def store(self) -> Path:
        return self._store

    # ---------- recording ----------

    def record(self, snapshot) -> bool:
        """Extract a HistorySample from a Snapshot and append it.

        Throttled: returns False when called more often than SAMPLE_INTERVAL_S.
        """
        now = self._now()
        if now - self._last_record < self.SAMPLE_INTERVAL_S:
            return False
        self._last_record = now
        sample = self._from_snapshot(snapshot, now)
        self._append(sample)
        return True

    # ---------- reading ----------

    def query(self, minutes: float) -> list[HistorySample]:
        """Return samples from the last *minutes*, oldest first."""
        cutoff = self._now() - minutes * 60.0
        samples = [s for s in self._load() if s.ts >= cutoff]
        samples.sort(key=lambda s: s.ts)
        return samples

    def clear(self) -> None:
        """Delete the entire history file."""
        self._store.unlink(missing_ok=True)
        self._last_record = 0.0

    # ---------- internals ----------

    def _from_snapshot(self, snapshot, now: float) -> HistorySample:
        cpu = snapshot.cpu.percent if snapshot.cpu else None
        ram = snapshot.memory.percent if snapshot.memory else None
        gpu = gpu_mem = temp_gpu = None
        if snapshot.gpus:
            g = snapshot.gpus[0]
            gpu = g.utilization
            gpu_mem = (g.memory_used / g.memory_total * 100) if g.memory_total else None
            temp_gpu = g.temperature
        temp_cpu = None
        if snapshot.thermal and snapshot.thermal.temperatures:
            temp_cpu = max(v for _, v in snapshot.thermal.temperatures)
        return HistorySample(
            ts=now,
            cpu=cpu,
            ram=ram,
            gpu=gpu,
            gpu_mem=gpu_mem,
            temp_cpu=temp_cpu,
            temp_gpu=temp_gpu,
        )

    def _append(self, sample: HistorySample) -> None:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            with open(self._store, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample.to_dict()) + "\n")
        except OSError as exc:
            log.warning("history append failed: %s", exc)

    def _load(self) -> list[HistorySample]:
        if not self._store.exists():
            return []
        cutoff = self._now() - self._max_age_s
        samples: list[HistorySample] = []
        dropped = 0
        try:
            with open(self._store, encoding="utf-8") as f:
                lines = f.readlines()
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    dropped += 1
                    continue
                s = HistorySample.from_dict(d)
                if s is not None and s.ts >= cutoff:
                    samples.append(s)
                else:
                    dropped += 1

            # If any entries were trimmed or dropped, rewrite the store so it never grows infinitely
            if dropped > 0:
                tmp = self._store.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    for s in samples:
                        f.write(json.dumps(s.to_dict()) + "\n")
                tmp.replace(self._store)
        except OSError as exc:
            log.warning("history load failed: %s", exc)
        return samples


def downsample(samples: list[HistorySample], target: int = 120) -> list[HistorySample]:
    """Reduce *samples* to at most *target* points, keeping first and last."""
    n = len(samples)
    if n <= target or target < 2:
        return samples
    step = (n - 1) / (target - 1)
    return [samples[round(i * step)] for i in range(target)]


def stats(samples: list[HistorySample], field: str) -> tuple[float, float, float] | None:
    """Return (min, avg, max) for a numeric field across *samples*, or None."""
    values = [getattr(s, field) for s in samples if getattr(s, field) is not None]
    if not values:
        return None
    return min(values), sum(values) / len(values), max(values)
