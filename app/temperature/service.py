from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from time import time
from typing import Protocol

from app.alerts.service import TEMP_CPU_C, TEMP_GPU_C, max_cpu_thermal, max_gpu_thermal
from app.history.service import HistorySample
from app.sensors.temperature_names import (
    KIND_BOARD,
    KIND_CPU,
    KIND_GPU,
    KIND_HOTSPOT,
    KIND_SYSTEM,
    temperature_kind,
)
from app.sensors.types import Snapshot

SYSTEM_WARN_C = 85.0
GPU_WARN_C = 80.0
STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_DANGER = "DANGER"
TARGET_KINDS = (KIND_CPU, KIND_BOARD, KIND_GPU)

_LiveStats = tuple[int, float, float, float]


class _HistoryLike(Protocol):
    def query(self, minutes: float) -> Sequence[HistorySample]: ...


Selector = Callable[[Snapshot], tuple[float, str] | None]


@dataclass(frozen=True, slots=True)
class TemperatureReading:
    source: str
    current: float | None
    peak: float | None
    avg: float | None
    min: float | None
    max: float | None
    status: str
    available: bool
    kind: str


@dataclass(frozen=True, slots=True)
class TemperatureReport:
    readings: tuple[TemperatureReading, ...]
    errors: tuple[str, ...]
    generated: float


def thresholds() -> dict[str, tuple[float, float]]:
    return {
        "system": (SYSTEM_WARN_C, float(TEMP_CPU_C)),
        "cpu": (SYSTEM_WARN_C, float(TEMP_CPU_C)),
        "board": (SYSTEM_WARN_C, float(TEMP_CPU_C)),
        "gpu": (GPU_WARN_C, float(TEMP_GPU_C)),
        "hotspot": (GPU_WARN_C, float(TEMP_GPU_C)),
    }


def classify(value: float | None, warn: float, danger: float) -> str:
    if value is None:
        return STATUS_OK
    if value >= danger:
        return STATUS_DANGER
    if value >= warn:
        return STATUS_WARN
    return STATUS_OK


def _zone_text(name: str) -> str:
    from app.ui.format import zone_label

    return zone_label(name)


def target_temperatures(snapshot: Snapshot) -> dict[str, tuple[float | None, str]]:
    targets: dict[str, tuple[float | None, str]] = {kind: (None, "") for kind in TARGET_KINDS}
    thermal = getattr(snapshot, "thermal", None)
    if thermal is not None:
        for name, value in getattr(thermal, "temperatures", ()):
            kind = temperature_kind(str(name))
            if kind not in targets:
                continue
            current, source = targets[kind]
            value = float(value)
            if current is None or value > current:
                targets[kind] = (value, _zone_text(str(name)))
    for gpu in getattr(snapshot, "gpus", ()) or ():
        if getattr(gpu, "stale", False):
            continue
        value = getattr(gpu, "temperature", None)
        if value is None:
            continue
        index = getattr(gpu, "index", 0)
        base = getattr(gpu, "name", None) or f"GPU {index}"
        current, source = targets[KIND_GPU]
        value = float(value)
        if current is None or value > current:
            targets[KIND_GPU] = (value, f"{base} core")
    return targets


def _history_source(field: str) -> str:
    from app.i18n import tr

    if field == "temp_cpu":
        return f"wmi_acpi · {tr('therm_zone', n='max')}"
    key = "temp_src_gpu_core" if field == "temp_gpu" else "temp_src_gpu_hotspot"
    return f"nvml · {tr(key)}"


class TemperatureService:
    def __init__(
        self,
        history: _HistoryLike | None = None,
        *,
        system_selector: Selector = max_cpu_thermal,
        gpu_selector: Selector = max_gpu_thermal,
        now: Callable[[], float] | None = None,
    ) -> None:
        self._history = history
        self._system_selector = system_selector
        self._gpu_selector = gpu_selector
        self._now = now or time
        self._query_cache: tuple[float, tuple[HistorySample, ...], tuple[str, ...]] | None = None
        self._live_stats: dict[tuple[str, str], _LiveStats] = {}

    def thresholds(self) -> dict[str, tuple[float, float]]:
        return thresholds()

    def invalidate_cache(self) -> None:
        self._query_cache = None

    def readings_from_snapshot(
        self,
        snapshot: Snapshot,
        *,
        record: bool = True,
    ) -> TemperatureReport:
        limits = thresholds()
        system_warn, system_danger = limits["system"]
        gpu_warn, gpu_danger = limits["gpu"]
        readings: list[TemperatureReading] = []

        thermal = getattr(snapshot, "thermal", None)
        if thermal is not None:
            backend = getattr(thermal, "source", None) or "wmi_acpi"
            for name, value in getattr(thermal, "temperatures", ()):
                raw_name = str(name)
                kind = temperature_kind(raw_name)
                warn, danger = limits.get(kind, limits["system"])
                source = f"{backend} · {_zone_text(raw_name)}"
                readings.append(
                    self._live_reading(
                        source,
                        float(value),
                        warn,
                        danger,
                        kind,
                        (kind, f"zone:{raw_name}"),
                        record,
                    )
                )
        else:
            hot = self._system_selector(snapshot)
            if hot is not None:
                value, name = hot
                raw_name = str(name)
                source = f"wmi_acpi · {_zone_text(raw_name)}"
                readings.append(
                    self._live_reading(
                        source,
                        float(value),
                        system_warn,
                        system_danger,
                        KIND_SYSTEM,
                        (KIND_SYSTEM, f"selector:{raw_name}"),
                        record,
                    )
                )

        gpus = getattr(snapshot, "gpus", ()) or ()
        for gpu in gpus:
            if getattr(gpu, "stale", False):
                continue
            index = getattr(gpu, "index", 0)
            base = getattr(gpu, "name", None) or f"GPU {index}"
            core = getattr(gpu, "temperature", None)
            if core is not None:
                readings.append(
                    self._live_reading(
                        f"nvml · {base} core",
                        float(core),
                        gpu_warn,
                        gpu_danger,
                        KIND_GPU,
                        (KIND_GPU, f"{index}:{base}:core"),
                        record,
                    )
                )
            hotspot = getattr(gpu, "temperature_hotspot", None)
            if hotspot is not None:
                readings.append(
                    self._live_reading(
                        f"nvml · {base} hotspot",
                        float(hotspot),
                        gpu_warn,
                        gpu_danger,
                        KIND_HOTSPOT,
                        (KIND_HOTSPOT, f"{index}:{base}:hotspot"),
                        record,
                    )
                )
        if not gpus:
            hot = self._gpu_selector(snapshot)
            if hot is not None:
                value, name = hot
                readings.append(
                    self._live_reading(
                        f"nvml · {name}",
                        float(value),
                        gpu_warn,
                        gpu_danger,
                        KIND_GPU,
                        (KIND_GPU, f"selector:{name}"),
                        record,
                    )
                )

        errors = tuple(
            f"{key}: {message}"
            for key, message in (getattr(snapshot, "errors", None) or {}).items()
            if key in {"thermal", "nvml", "gpu"}
        )
        return TemperatureReport(tuple(readings), errors, self._now())

    def from_history(self, minutes: float) -> TemperatureReport:
        samples, errors = self._query(minutes)
        limits = thresholds()
        readings: list[TemperatureReading] = []
        fields = (
            ("temp_cpu", "system", limits["system"]),
            ("temp_gpu", "gpu", limits["gpu"]),
            ("gpu_hotspot", "hotspot", limits["gpu"]),
        )
        for field, kind, (warn, danger) in fields:
            values = [float(value) for s in samples if (value := getattr(s, field, None)) is not None]
            if not values:
                continue
            readings.append(
                TemperatureReading(
                    source=_history_source(field),
                    current=values[-1],
                    peak=max(values),
                    avg=sum(values) / len(values),
                    min=min(values),
                    max=max(values),
                    status=classify(values[-1], warn, danger),
                    available=True,
                    kind=kind,
                )
            )
        return TemperatureReport(tuple(readings), errors, self._now())

    def history_series(self, minutes: float) -> dict[str, list[float]]:
        samples, _ = self._query(minutes)
        keys = (("temp_cpu", "system"), ("temp_gpu", "gpu"), ("gpu_hotspot", "hotspot"))
        return {
            key: [float(value) for s in samples if (value := getattr(s, field, None)) is not None]
            for field, key in keys
        }

    def _live_reading(
        self,
        source: str,
        value: float,
        warn: float,
        danger: float,
        kind: str,
        key: tuple[str, str],
        record: bool,
    ) -> TemperatureReading:
        if record:
            previous = self._live_stats.get(key)
            if previous is None:
                self._live_stats[key] = (1, value, value, value)
            else:
                count, low, high, total = previous
                self._live_stats[key] = (
                    count + 1,
                    min(low, value),
                    max(high, value),
                    total + value,
                )
        stats = self._live_stats.get(key)
        if stats is None:
            peak = avg = low = high = None
        else:
            count, low, high, total = stats
            peak = high
            avg = total / count
        return TemperatureReading(
            source=source,
            current=value,
            peak=peak,
            avg=avg,
            min=low,
            max=high,
            status=classify(value, warn, danger),
            available=True,
            kind=kind,
        )

    def _query(self, minutes: float) -> tuple[tuple[HistorySample, ...], tuple[str, ...]]:
        cached = self._query_cache
        if cached is not None and cached[0] == minutes:
            return cached[1], cached[2]
        if self._history is None:
            samples, errors = (), ()
        else:
            try:
                samples, errors = tuple(self._history.query(minutes)), ()
            except Exception as exc:
                samples, errors = (), (f"history: {exc}",)
        self._query_cache = (minutes, samples, errors)
        return samples, errors
