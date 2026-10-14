from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CpuStat:
    percent: float
    per_core: tuple[float, ...]
    physical_cores: int
    logical_cores: int
    freq_mhz: float | None = None
    freq_max_mhz: float | None = None


@dataclass(frozen=True, slots=True)
class MemoryStat:
    total: int
    used: int
    available: int
    percent: float
    swap_total: int
    swap_used: int
    swap_percent: float


@dataclass(frozen=True, slots=True)
class DiskStat:
    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass(frozen=True, slots=True)
class NetStat:
    bytes_sent: int
    bytes_recv: int
    packets_sent: int
    packets_recv: int
    send_rate: float = 0.0
    recv_rate: float = 0.0


@dataclass(frozen=True, slots=True)
class GpuStat:
    index: int
    name: str
    utilization: float
    memory_used: int
    memory_total: int
    temperature: float | None = None
    power_w: float | None = None
    fan_percent: float | None = None
    clock_mhz: float | None = None
    power_limit_w: float | None = None


@dataclass(frozen=True, slots=True)
class ThermalStat:
    source: str
    temperatures: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class Snapshot:
    ts: float
    cpu: CpuStat | None = None
    memory: MemoryStat | None = None
    disks: tuple[DiskStat, ...] = ()
    net: NetStat | None = None
    gpus: tuple[GpuStat, ...] = ()
    thermal: ThermalStat | None = None
    errors: Mapping[str, str] = field(default_factory=dict)

    @property
    def gpu(self) -> GpuStat | None:
        return self.gpus[0] if self.gpus else None

    @property
    def healthy(self) -> bool:
        return self.cpu is not None and self.memory is not None
