from __future__ import annotations

import threading
from time import monotonic
from typing import Any

from .base import Backend, Partial, SensorUnavailable
from .lhm_backend import LhmReader
from .temperature_names import (
    KIND_BOARD,
    KIND_CPU,
    KIND_GPU,
    KIND_HOTSPOT,
    KIND_SYSTEM,
    canonical_temperature_name,
    raw_temperature_kind,
    temperature_kind,
)
from .types import ThermalStat

_TTL_S = 2.0
_LHM_NAMESPACES = ("root\\LibreHardwareMonitor", "root\\OpenHardwareMonitor")
_SOURCE_PRIORITY = {"hwinfo": 5, "lhm": 4, "lhm_pythonnet": 3, "wmi_acpi": 1}
_EMPTY_TTL_S = 15.0


def _is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _merge_stats(stats: tuple[ThermalStat, ...], notes: tuple[str, ...]) -> ThermalStat:
    best: dict[str, tuple[int, float, str]] = {}
    system: dict[str, tuple[int, float]] = {}
    sources: list[str] = []
    for stat in stats:
        if not stat.temperatures:
            continue
        priority = _SOURCE_PRIORITY.get(stat.source, 0)
        sources.append(stat.source)
        for name, value in stat.temperatures:
            kind = temperature_kind(name)
            if kind == KIND_SYSTEM:
                previous = system.get(name)
                if previous is None or (priority, value) > previous:
                    system[name] = (priority, value)
                continue
            current = best.get(kind)
            if current is None or (priority, value) > (current[0], current[1]):
                best[kind] = (priority, value, name)
    temperatures = [(name, value) for _priority, value, name in best.values()]
    temperatures.extend((name, value) for name, (priority, value) in system.items())
    temperatures.sort(key=lambda item: item[0])
    source = " + ".join(sources) if sources else (stats[0].source if stats else "")
    merged_notes = tuple(dict.fromkeys([*(note for stat in stats for note in stat.notes), *notes]))
    return ThermalStat(source, tuple(temperatures), merged_notes, tuple(dict.fromkeys(sources)))


class ThermalBackend(Backend):
    name = "thermal"

    def __init__(
        self,
        lhm_reader: LhmReader | None = None,
        *,
        hwinfo_reader: Any | None = None,
        empty_ttl_s: float = _EMPTY_TTL_S,
    ) -> None:
        self._zones: Any = None
        self._source: str | None = None
        self._owner_thread_id: int | None = None
        self._cache: tuple[float, Partial] | None = None
        self._empty_until = 0.0
        self._empty_ttl_s = max(0.0, float(empty_ttl_s))
        self._lhm_reader = lhm_reader
        self._hwinfo_reader = hwinfo_reader

    def _hwinfo(self) -> ThermalStat:
        if self._hwinfo_reader is None:
            raise SensorUnavailable("HWiNFO reader is not enabled")
        values = self._hwinfo_reader.read()
        if not values:
            raise SensorUnavailable(self._hwinfo_reader.last_error or "no HWiNFO temperature sensors")
        temperatures = tuple((kind, values[kind][0]) for kind in sorted(values))
        return ThermalStat(
            source="hwinfo",
            temperatures=temperatures,
            sources=("hwinfo",),
        )

    def _pythonnet(self) -> ThermalStat:
        if self._lhm_reader is None:
            raise SensorUnavailable("pythonnet LHM reader is not enabled")
        values = self._lhm_reader.read()
        if not values:
            raise SensorUnavailable(self._lhm_reader.last_error or "no LHM temperature sensors")
        raw = tuple(getattr(self._lhm_reader, "last_raw", ()) or ())
        notes: list[str] = []
        if self._lhm_reader.last_error:
            notes.append(f"LHM: {self._lhm_reader.last_error}")
        cpu_zero = any(
            raw_temperature_kind(name) == KIND_CPU
            and value <= 0.0
            and ("temp" in name.lower() or "tctl" in name.lower() or "tdie" in name.lower() or "core" in name.lower())
            for name, value in raw
        )
        if cpu_zero and KIND_CPU not in values:
            notes.append("LHM CPU temperature sensor reports 0°C (driver or CPU unsupported)")
        if not any(raw_temperature_kind(name) == KIND_BOARD and value > 0.0 for name, value in raw):
            notes.append("LHM motherboard has no temperature sensors")
        return ThermalStat(
            source="lhm_pythonnet",
            temperatures=tuple((kind, values[kind][0]) for kind in sorted(values)),
            notes=tuple(notes),
            sources=("lhm_pythonnet",),
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
        for index, zone in enumerate(self._zones):
            raw = str(getattr(zone, "InstanceName", "") or "").strip() or f"zone{index}"
            value = float(zone.CurrentTemperature) / 10.0 - 273.15
            temps.append((raw, value))
        notes: tuple[str, ...] = ()
        if not any(raw_temperature_kind(name) in (KIND_CPU, KIND_BOARD) for name, _value in temps):
            notes = ("ACPI exposes system zones only; CPU/motherboard need HWiNFO or LHM",)
        return ThermalStat(
            source="wmi_acpi",
            temperatures=tuple(temps),
            notes=notes,
            sources=("wmi_acpi",),
        )

    def _lhm_namespace(self, namespace: str) -> ThermalStat | None:
        import wmi

        sensors = wmi.WMI(namespace=namespace).Sensor()
        if not sensors:
            return None
        best: dict[str, tuple[int, float, str]] = {}
        for sensor in sensors:
            if str(getattr(sensor, "SensorType", "")).lower() != "temperature":
                continue
            raw = str(getattr(sensor, "Name", "") or "").strip()
            identifier = str(getattr(sensor, "Identifier", "") or "")
            if not raw:
                continue
            kind = raw_temperature_kind(raw, identifier)
            if kind not in (KIND_CPU, KIND_BOARD, KIND_GPU, KIND_HOTSPOT):
                continue
            value = float(sensor.Value)
            score = len(raw) if raw.lower() in (KIND_CPU, KIND_BOARD, KIND_GPU) else 0
            current = best.get(kind)
            if current is None or (score, value) > (current[0], current[1]):
                best[kind] = (score, value, canonical_temperature_name(raw))
        if not best:
            return None
        self._zones = sensors
        self._source = "lhm"
        self._owner_thread_id = threading.get_ident()
        return ThermalStat(
            source="lhm",
            temperatures=tuple((kind, entry[1]) for kind, entry in sorted(best.items())),
            sources=("lhm",),
        )

    def _lhm(self) -> ThermalStat:
        errors: list[str] = []
        for namespace in _LHM_NAMESPACES:
            try:
                stat = self._lhm_namespace(namespace)
                if stat is not None:
                    return stat
                errors.append(f"{namespace}: no target sensors")
            except Exception as exc:
                errors.append(f"{namespace}: {exc}")
        raise SensorUnavailable("; ".join(errors) or "no LHM WMI sensors")

    def collect(self) -> Partial:
        now = monotonic()
        if self._cache is not None and now - self._cache[0] < _TTL_S:
            return self._cache[1]
        if self._empty_ttl_s and now < self._empty_until:
            return {}
        stats: list[ThermalStat] = []
        notes: list[str] = []

        if self._hwinfo_reader is not None:
            try:
                stats.append(self._hwinfo())
            except Exception as exc:
                notes.append(f"HWiNFO: {exc}")

        if self._lhm_reader is not None:
            try:
                stats.append(self._pythonnet())
            except Exception as exc:
                notes.append(f"LHM: {exc}")

        try:
            stats.append(self._acpi())
        except Exception as exc:
            if not _is_admin() and ("denied" in str(exc).lower() or "0x80041003" in str(exc)):
                notes.append("ACPI: access denied; restart as administrator to read system zones")
            else:
                notes.append(f"ACPI: {exc}")
            try:
                stats.append(self._lhm())
            except Exception as exc2:
                notes.append(f"LHM WMI: {exc2}")

        if not stats:
            # No ACPI/LHM/HWiNFO on this machine: avoid retrying several WMI
            # namespace queries on every sampler tick when nothing can change.
            self._empty_until = now + self._empty_ttl_s
            return {}
        self._empty_until = 0.0
        result: Partial = {"thermal": _merge_stats(tuple(stats), tuple(notes))}
        self._cache = (now, result)
        return result

    def close(self) -> None:
        self._cache = None
        self._empty_until = 0.0
        if self._lhm_reader is not None:
            self._lhm_reader.close()
        if self._owner_thread_id is not None and self._owner_thread_id != threading.get_ident():
            return
        self._zones = None
        self._source = None
        self._owner_thread_id = None
