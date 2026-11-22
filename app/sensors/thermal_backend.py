from __future__ import annotations

import threading
from time import monotonic

from .base import Backend, Partial, SensorUnavailable
from .lhm_backend import LhmReader
from .temperature_names import KIND_BOARD, KIND_CPU, KIND_GPU, canonical_temperature_name
from .types import ThermalStat

_TTL_S = 2.0


class ThermalBackend(Backend):
    name = "thermal"

    def __init__(self, lhm_reader: LhmReader | None = None) -> None:
        self._zones: object | None = None
        self._source: str | None = None
        self._owner_thread_id: int | None = None
        self._cache: tuple[float, Partial] | None = None
        self._lhm_reader = lhm_reader

    def _pythonnet(self) -> ThermalStat:
        if self._lhm_reader is None:
            raise SensorUnavailable("pythonnet LHM reader is not enabled")
        values = self._lhm_reader.read()
        if not values:
            raise SensorUnavailable(self._lhm_reader.last_error or "no LHM temperature sensors")
        return ThermalStat(
            source="lhm_pythonnet",
            temperatures=tuple((kind, values[kind][0]) for kind in sorted(values)),
        )

    def _acpi(self) -> ThermalStat:
        if self._zones is None or self._source != "wmi_acpi":
            import wmi

            zones = wmi.WMI(namespace="root\\wmi").MSAcpi_ThermalZoneTemperature()
            if not zones:
                raise SensorUnavailable("no MSAcpi thermal zones")
            self._zones = zones
            self._source = "wmi_acpi"
            self._owner_thread_id = threading.get_ident()
        temps = []
        for index, zone in enumerate(self._zones):  # type: ignore[union-attr]
            raw = str(getattr(zone, "InstanceName", "") or "").strip() or f"zone{index}"
            value = float(zone.CurrentTemperature) / 10.0 - 273.15
            temps.append((raw, value))
        return ThermalStat(source="wmi_acpi", temperatures=tuple(temps))

    def _lhm(self) -> ThermalStat:
        if self._zones is None or self._source != "lhm":
            import wmi

            sensors = wmi.WMI(namespace="root\\OpenHardwareMonitor").Sensor()
            if not sensors:
                raise SensorUnavailable("no LHM sensors")
            self._zones = sensors
            self._source = "lhm"
            self._owner_thread_id = threading.get_ident()
        best: dict[str, float] = {}
        for sensor in self._zones:  # type: ignore[union-attr]
            if str(getattr(sensor, "SensorType", "")).lower() != "temperature":
                continue
            raw = str(getattr(sensor, "Name", "") or "").strip()
            if not raw:
                continue
            name = canonical_temperature_name(raw)
            if name not in (KIND_CPU, KIND_BOARD, KIND_GPU):
                continue
            value = float(sensor.Value)
            best[name] = max(best.get(name, value), value)
        if not best:
            raise SensorUnavailable("no LHM target temperature sensors")
        return ThermalStat(source="lhm", temperatures=tuple(sorted(best.items())))

    def collect(self) -> Partial:
        now = monotonic()
        if self._cache is not None and now - self._cache[0] < _TTL_S:
            return self._cache[1]
        part: Partial | None = None
        if self._lhm_reader is not None:
            try:
                part = {"thermal": self._pythonnet()}
            except Exception:
                part = None
        if part is None:
            try:
                part = {"thermal": self._acpi()}
            except Exception:
                try:
                    part = {"thermal": self._lhm()}
                except Exception:
                    return {}
        self._cache = (now, part)
        return part

    def close(self) -> None:
        self._cache = None
        if self._lhm_reader is not None:
            self._lhm_reader.close()
        if self._owner_thread_id is not None and self._owner_thread_id != threading.get_ident():
            return
        self._zones = None
        self._source = None
        self._owner_thread_id = None
