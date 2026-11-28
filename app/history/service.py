from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.sensors.temperature_names import KIND_CPU, raw_temperature_kind
from app.settings import data_root

log = logging.getLogger("pcoptimizer.history")

_DEFAULT_STORE = "performance_history.jsonl"
_SAMPLE_INTERVAL_S = 30.0
_DEFAULT_MAX_AGE_HOURS = 24.0 * 7.0
_COMPACT_EVERY = 120


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
    gpu_hotspot: float | None = None
    gpu_mem_clock: float | None = None
    gpu_power: float | None = None
    gpu_throttling: bool | None = None
    commit_percent: float | None = None
    top_processes: tuple[tuple[str, float], ...] = ()

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"ts": round(self.ts, 1)}
        for key in (
            "cpu",
            "ram",
            "gpu",
            "gpu_mem",
            "temp_cpu",
            "temp_gpu",
            "gpu_hotspot",
            "gpu_mem_clock",
            "gpu_power",
            "commit_percent",
        ):
            value = getattr(self, key)
            out[key] = round(value, 1) if value is not None else None
        out["gpu_throttling"] = self.gpu_throttling
        out["top_processes"] = [[name, round(mb, 1)] for name, mb in self.top_processes]
        return out

    @classmethod
    def from_dict(cls, d: dict) -> HistorySample | None:
        top_processes: list[tuple[str, float]] = []
        raw_top = d.get("top_processes") or []
        if isinstance(raw_top, list):
            for item in raw_top[:8]:
                if not isinstance(item, (list, tuple)) or len(item) != 2:
                    continue
                try:
                    name = str(item[0])
                    mb = float(item[1])
                except (TypeError, ValueError):
                    continue
                if mb >= 0:
                    top_processes.append((name, mb))
        try:
            return cls(
                ts=float(d["ts"]),
                cpu=d.get("cpu"),
                ram=d.get("ram"),
                gpu=d.get("gpu"),
                gpu_mem=d.get("gpu_mem"),
                temp_cpu=d.get("temp_cpu"),
                temp_gpu=d.get("temp_gpu"),
                gpu_hotspot=d.get("gpu_hotspot"),
                gpu_mem_clock=d.get("gpu_mem_clock"),
                gpu_power=d.get("gpu_power"),
                gpu_throttling=d.get("gpu_throttling"),
                commit_percent=d.get("commit_percent"),
                top_processes=tuple(top_processes),
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
        max_age_hours: float = _DEFAULT_MAX_AGE_HOURS,
        now: Callable[[], float] | None = None,
        process_top: Callable[[], Sequence[object]] | None = None,
        interval_s: float = _SAMPLE_INTERVAL_S,
    ) -> None:
        self._store = Path(store) if store else data_root() / _DEFAULT_STORE
        self._max_age_s = max_age_hours * 3600.0
        self._now = now or time.time
        self._process_top = process_top
        self._interval_s = max(0.0, float(interval_s))
        self._last_record = 0.0
        self._append_count = 0

    @property
    def store(self) -> Path:
        return self._store

    @property
    def interval_s(self) -> float:
        return self._interval_s

    def set_interval_s(self, interval_s: float) -> None:
        """Change the record throttle at runtime (used by monitoring profiles)."""
        self._interval_s = max(0.0, float(interval_s))

    # ---------- recording ----------

    def record(self, snapshot) -> bool:
        """Extract a HistorySample from a Snapshot and append it.

        Throttled: returns False when called more often than ``interval_s``.
        """
        now = self._now()
        if now - self._last_record < self._interval_s:
            return False
        top_processes: tuple[tuple[str, float], ...] = ()
        if self._process_top is not None:
            try:
                rows = list(self._process_top() or [])[:8]
                top_processes = tuple(
                    (str(getattr(row, "name", "")), round(getattr(row, "memory_bytes", 0) / 1048576.0, 1))
                    for row in rows
                )
            except Exception as exc:
                log.warning("history process scan failed: %s", exc)
        sample = self._from_snapshot(snapshot, now, top_processes)
        if not self._append(sample):
            return False
        self._last_record = now
        self._compact_if_due()
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
        self._append_count = 0

    # ---------- internals ----------

    def _from_snapshot(
        self,
        snapshot,
        now: float,
        top_processes: tuple[tuple[str, float], ...] = (),
    ) -> HistorySample:
        cpu = snapshot.cpu.percent if snapshot.cpu else None
        ram = snapshot.memory.percent if snapshot.memory else None
        gpu = gpu_mem = temp_gpu = gpu_hotspot = gpu_mem_clock = gpu_power = None
        gpu_throttling = None
        if snapshot.gpus:
            g = snapshot.gpus[0]
            gpu = g.utilization
            gpu_mem = (g.memory_used / g.memory_total * 100) if g.memory_total else None
            temp_gpu = g.temperature
            gpu_hotspot = getattr(g, "temperature_hotspot", None)
            gpu_mem_clock = getattr(g, "memory_clock_mhz", None)
            gpu_power = getattr(g, "power_w", None)
            throttling = getattr(g, "throttling", None)
            gpu_throttling = bool(throttling) if throttling is not None else None
        temp_cpu = None
        if snapshot.thermal and snapshot.thermal.temperatures:
            cpu_temps: list[float] = []
            for name, value in snapshot.thermal.temperatures:
                try:
                    kind = raw_temperature_kind(str(name))
                    temp = float(value)
                except (TypeError, ValueError):
                    continue
                if kind == KIND_CPU and temp > 0:
                    cpu_temps.append(temp)
            if cpu_temps:
                temp_cpu = max(cpu_temps)
        commit_percent = None
        if (
            snapshot.memory
            and getattr(snapshot.memory, "commit_limit", None)
            and getattr(snapshot.memory, "commit_used", None) is not None
        ):
            commit_percent = snapshot.memory.commit_used / snapshot.memory.commit_limit * 100.0
        return HistorySample(
            ts=now,
            cpu=cpu,
            ram=ram,
            gpu=gpu,
            gpu_mem=gpu_mem,
            temp_cpu=temp_cpu,
            temp_gpu=temp_gpu,
            gpu_hotspot=gpu_hotspot,
            gpu_mem_clock=gpu_mem_clock,
            gpu_power=gpu_power,
            gpu_throttling=gpu_throttling,
            commit_percent=commit_percent,
            top_processes=top_processes,
        )

    def _append(self, sample: HistorySample) -> bool:
        try:
            self._store.parent.mkdir(parents=True, exist_ok=True)
            with open(self._store, "a", encoding="utf-8") as f:
                f.write(json.dumps(sample.to_dict()) + "\n")
            self._append_count += 1
            return True
        except OSError as exc:
            log.warning("history append failed: %s", exc)
            return False

    def _compact_if_due(self) -> None:
        if self._append_count < _COMPACT_EVERY:
            return
        self._append_count = 0
        self._load()

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
    lo = min(values)
    hi = max(values)
    return lo, sum(values) / len(values), hi


def top_process_summary(
    samples: list[HistorySample], limit: int = 8
) -> list[tuple[str, float | None, float, int]]:
    if not samples:
        return []
    latest = dict(samples[-1].top_processes)
    peaks: dict[str, float] = {}
    counts: dict[str, int] = {}
    for sample in samples:
        for name, mb in sample.top_processes:
            peaks[name] = max(peaks.get(name, 0.0), mb)
            counts[name] = counts.get(name, 0) + 1
    names = [name for name, _ in samples[-1].top_processes]
    names.extend(name for name in peaks if name not in latest)
    rows: list[tuple[str, float | None, float, int]] = []
    for name in names[:limit]:
        rows.append((name, latest.get(name), peaks.get(name, 0.0), counts.get(name, 0)))
    return rows
