from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

Partial = dict[str, Any]


class SensorError(Exception):
    pass


class SensorUnavailable(SensorError):
    pass


class Backend(ABC):
    name: str = "backend"

    @abstractmethod
    def collect(self) -> Partial:
        ...

    def close(self) -> None:
        return None
