from __future__ import annotations

from time import time
from typing import Iterable

from .base import Backend, SensorUnavailable
from .nvml_backend import NvmlBackend
from .psutil_backend import PsutilBackend
from .thermal_backend import ThermalBackend
from .types import Snapshot

AUTO_BACKENDS = (PsutilBackend, NvmlBackend, ThermalBackend)


class SensorManager:
    def __init__(self, backends: Iterable[Backend] = (), unavailable: dict[str, str] | None = None) -> None:
        self._backends = list(backends)
        self._unavailable = dict(unavailable or {})

    @classmethod
    def with_defaults(cls) -> SensorManager:
        backends: list[Backend] = []
        unavailable: dict[str, str] = {}
        for factory in AUTO_BACKENDS:
            try:
                backends.append(factory())
            except SensorUnavailable as e:
                unavailable[factory.name] = str(e)
        return cls(backends, unavailable)

    @classmethod
    def mock(cls) -> SensorManager:
        from .mock_backend import MockBackend

        return cls([MockBackend()])

    @property
    def backend_names(self) -> tuple[str, ...]:
        return tuple(b.name for b in self._backends)

    def snapshot(self) -> Snapshot:
        data: dict[str, object] = {}
        errors = dict(self._unavailable)
        for backend in self._backends:
            try:
                part = backend.collect()
            except Exception as e:
                errors[backend.name] = str(e) or type(e).__name__
                continue
            for key, value in part.items():
                if value is None or key in data:
                    continue
                data[key] = value
        return Snapshot(ts=time(), errors=errors, **data)  # type: ignore[arg-type]

    def close(self) -> None:
        for backend in self._backends:
            try:
                backend.close()
            except Exception:
                pass
