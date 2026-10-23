"""Temperature alert rules: turn raw sensor snapshots into overheat events."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.sensors.types import Snapshot


@dataclass(frozen=True, slots=True)
class TempAlert:
    temperature: float
    source: str
    limit: float


def max_cpu_thermal(snapshot: Snapshot) -> tuple[float, str] | None:
    """Hottest ACPI thermal zone (CPU/system) as ``(celsius, source)`` or ``None``."""
    if snapshot.thermal is None or not snapshot.thermal.temperatures:
        return None
    return max(((value, name) for name, value in snapshot.thermal.temperatures), key=lambda i: i[0])


def max_gpu_thermal(snapshot: Snapshot) -> tuple[float, str] | None:
    """Hottest GPU core temperature as ``(celsius, source)`` or ``None``."""
    readings = [
        (gpu.temperature, gpu.name or f"GPU {gpu.index}")
        for gpu in snapshot.gpus
        if gpu.temperature is not None and not gpu.stale
    ]
    if not readings:
        return None
    return max(readings, key=lambda item: item[0])


def max_thermal(snapshot: Snapshot) -> tuple[float, str] | None:
    """Return the hottest reading in *snapshot* as ``(celsius, source)``.

    Considers ACPI thermal zones and GPU core temperatures. Returns ``None``
    when no temperature is available.
    """
    readings: list[tuple[float, str]] = []
    cpu = max_cpu_thermal(snapshot)
    if cpu is not None:
        readings.append(cpu)
    gpu = max_gpu_thermal(snapshot)
    if gpu is not None:
        readings.append(gpu)
    if not readings:
        return None
    return max(readings, key=lambda item: item[0])


class TemperatureAlertMonitor:
    """Fires an alert when the hottest sensor crosses *limit*, then stays quiet.

    The alert triggers on the rising edge and, if the temperature stays above
    the limit, at most once per ``cooldown_s``. It re-arms as soon as the
    temperature drops back below the limit.
    """

    def __init__(
        self,
        cooldown_s: float = 300.0,
        clock: Callable[[], float] = time.monotonic,
        reading: Callable[[Snapshot], tuple[float, str] | None] = max_thermal,
    ) -> None:
        self._cooldown = cooldown_s
        self._clock = clock
        self._reading = reading
        self._last_alert: float | None = None
        self._above = False

    def check(self, snapshot: Snapshot, limit: float) -> TempAlert | None:
        reading = self._reading(snapshot)
        if reading is None:
            return None
        value, source = reading
        if value < limit:
            self._above = False
            return None
        now = self._clock()
        if self._above and self._last_alert is not None and now - self._last_alert < self._cooldown:
            return None
        self._above = True
        self._last_alert = now
        return TempAlert(temperature=value, source=source, limit=limit)
