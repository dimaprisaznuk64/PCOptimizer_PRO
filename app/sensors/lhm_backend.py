from __future__ import annotations

import os
import sys
import threading
from collections.abc import Callable, Iterable
from pathlib import Path

from .temperature_names import (
    KIND_BOARD,
    KIND_CPU,
    KIND_GPU,
    temperature_kind,
    temperature_priority,
)

_DLL_NAMES = (
    "LibreHardwareMonitorLib",
    "HidSharp",
    "RAMSPDToolkit-NDD",
    "DiskInfoToolkit",
    "System.Memory",
    "System.Runtime.CompilerServices.Unsafe",
    "BlackSharp.Core",
    "System.Numerics.Vectors",
    "System.Buffers",
)

_TARGETS = frozenset((KIND_CPU, KIND_BOARD, KIND_GPU))


class LhmUnavailable(Exception):
    pass


def lhm_dll_dir() -> Path:
    override = os.environ.get("PCOPTIMIZER_LHM_DLL_DIR")
    if override:
        return Path(override)
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).parent
        for candidate in (exe / "_internal" / "lib" / "lhm", exe / "lib" / "lhm", exe):
            if (candidate / "LibreHardwareMonitorLib.dll").exists():
                return candidate
        return exe / "_internal" / "lib" / "lhm"
    return Path(__file__).resolve().parents[2] / "assets" / "lib" / "lhm"


def pick_temperatures(entries: Iterable[tuple[str, float]]) -> dict[str, tuple[float, str]]:
    best: dict[str, tuple[int, float, str]] = {}
    for raw, value in entries:
        if not value or value <= 0.0:
            continue
        kind = temperature_kind(raw)
        if kind not in _TARGETS:
            continue
        score = temperature_priority(raw, kind)
        current = best.get(kind)
        if current is None or (score, value) > (current[0], current[1]):
            best[kind] = (score, float(value), raw)
    return {kind: (entry[1], entry[2]) for kind, entry in best.items()}


class LhmReader:
    def __init__(
        self,
        dll_dir: Path | str | None = None,
        *,
        add_reference: Callable[[str], object] | None = None,
        computer_factory: Callable[[], object] | None = None,
    ) -> None:
        self._dll_dir = Path(dll_dir) if dll_dir is not None else lhm_dll_dir()
        self._add_reference = add_reference
        self._computer_factory = computer_factory
        self._computer: object | None = None
        self._loaded = False
        self._lock = threading.RLock()
        self.last_error: str = ""
        self.last_raw: tuple[tuple[str, float], ...] = ()
        self._disabled = (
            os.environ.get("PCOPTIMIZER_LHM_DISABLED") == "1"
            and add_reference is None
            and computer_factory is None
        )

    def _load(self) -> None:
        if self._loaded:
            return
        if self._add_reference is not None:
            for name in _DLL_NAMES:
                self._add_reference(str(self._dll_dir / f"{name}.dll"))
        else:
            import clr

            for name in _DLL_NAMES:
                clr.AddReference(str(self._dll_dir / f"{name}.dll"))
        self._loaded = True

    def _new_computer(self) -> object:
        if self._computer_factory is not None:
            computer = self._computer_factory()
        else:
            from LibreHardwareMonitor.Hardware import Computer

            computer = Computer()
        computer.IsCpuEnabled = True
        computer.IsGpuEnabled = True
        computer.IsMotherboardEnabled = True
        computer.Open()
        return computer

    @staticmethod
    def _walk(hardware: object) -> Iterable[tuple[str, float]]:
        for sensor in getattr(hardware, "Sensors", ()) or ():
            sensor_type = str(getattr(sensor, "SensorType", "")).lower()
            if sensor_type != "temperature":
                continue
            value = getattr(sensor, "Value", None)
            if value is None:
                continue
            value = float(value)
            raw = str(getattr(sensor, "Name", "") or "").strip()
            if raw:
                yield raw, value
        for child in getattr(hardware, "SubHardware", ()) or ():
            yield from LhmReader._walk(child)

    def read(self) -> dict[str, tuple[float, str]] | None:
        with self._lock:
            if self._disabled:
                return None
            try:
                self._load()
                if self._computer is None:
                    self._computer = self._new_computer()
                entries: list[tuple[str, float]] = []
                for hardware in getattr(self._computer, "Hardware", ()) or ():
                    hardware.Update()
                    entries.extend(self._walk(hardware))
                self.last_raw = tuple(entries)
                result = pick_temperatures(entries)
                self.last_error = ""
                return result or None
            except Exception as exc:
                self.last_error = str(exc) or type(exc).__name__
                return None

    def close(self) -> None:
        with self._lock:
            computer, self._computer = self._computer, None
            if computer is not None:
                try:
                    computer.Close()
                except Exception:
                    pass
