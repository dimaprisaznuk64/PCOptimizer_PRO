from __future__ import annotations

from time import monotonic

from .base import Backend, Partial, SensorUnavailable
from .types import ThermalStat

_TTL_S = 2.0


class ThermalBackend(Backend):
    name = "thermal"

    def __init__(self) -> None:
        # WMI dispatch objects are apartment-bound. Creating them here (on the
        # GUI thread) and reading them from SensorSampler (another thread) can
        # crash with RPC_E_WRONG_THREAD, so initialise lazily inside collect().
        self._zones: object | None = None
        self._cache: tuple[float, Partial] | None = None

    def _ensure_zones(self) -> None:
        if self._zones is not None:
            return
        try:
            import wmi
        except ImportError as e:
            raise SensorUnavailable(f"WMI not installed: {e}") from e
        try:
            zones = wmi.WMI(namespace="root\\wmi").MSAcpi_ThermalZoneTemperature()
        except Exception as e:
            raise SensorUnavailable(f"ACPI thermal zones unavailable: {e}") from e
        if not zones:
            raise SensorUnavailable("no MSAcpi thermal zones")
        self._zones = zones

    def collect(self) -> Partial:
        now = monotonic()
        if self._cache is not None and now - self._cache[0] < _TTL_S:
            return self._cache[1]
        try:
            self._ensure_zones()
            temps = tuple(
                (f"zone{i}", zone.CurrentTemperature / 10.0 - 273.15)
                for i, zone in enumerate(self._zones)  # type: ignore[union-attr]
            )
            part: Partial = {"thermal": ThermalStat(source="wmi_acpi", temperatures=temps)}
        except Exception:
            return {}
        self._cache = (now, part)
        return part

    def close(self) -> None:
        self._zones = None
        self._cache = None
