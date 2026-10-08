from __future__ import annotations

from .base import Backend, Partial, SensorUnavailable
from .types import ThermalStat


class ThermalBackend(Backend):
    name = "thermal"

    def __init__(self) -> None:
        try:
            import wmi
        except ImportError as e:
            raise SensorUnavailable(f"WMI not installed: {e}") from e
        try:
            self._zones = wmi.WMI(namespace="root\\wmi").MSAcpi_ThermalZoneTemperature()
        except Exception as e:
            raise SensorUnavailable(f"ACPI thermal zones unavailable: {e}") from e
        if not self._zones:
            raise SensorUnavailable("no MSAcpi thermal zones")

    def collect(self) -> Partial:
        temps = tuple(
            (f"zone{i}", zone.CurrentTemperature / 10.0 - 273.15) for i, zone in enumerate(self._zones)
        )
        return {"thermal": ThermalStat(source="wmi_acpi", temperatures=temps)}
