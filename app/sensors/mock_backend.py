from __future__ import annotations

from .base import Backend, Partial
from .types import CpuStat, DiskStat, GpuStat, MemoryStat, NetStat, ThermalStat


class MockBackend(Backend):
    name = "mock"

    def __init__(
        self,
        cpu_percent: float = 42.0,
        memory_percent: float = 60.0,
        gpu_percent: float = 25.0,
        temperature_c: float = 55.0,
    ) -> None:
        self.cpu_percent = cpu_percent
        self.memory_percent = memory_percent
        self.gpu_percent = gpu_percent
        self.temperature_c = temperature_c

    def collect(self) -> Partial:
        total = 32 * 1024**3
        used = int(total * self.memory_percent / 100)
        disk_total = 512 * 1024**3
        disk_used = int(disk_total * 0.5)
        return {
            "cpu": CpuStat(
                percent=self.cpu_percent,
                per_core=tuple(self.cpu_percent for _ in range(8)),
                physical_cores=8,
                logical_cores=16,
                freq_mhz=3200.0,
                freq_max_mhz=4500.0,
            ),
            "memory": MemoryStat(
                total=total,
                used=used,
                available=total - used,
                percent=self.memory_percent,
                swap_total=4 * 1024**3,
                swap_used=1024**3,
                swap_percent=25.0,
            ),
            "disks": (
                DiskStat(
                    device="C:\\",
                    mountpoint="C:\\",
                    fstype="NTFS",
                    total=disk_total,
                    used=disk_used,
                    free=disk_total - disk_used,
                    percent=50.0,
                ),
            ),
            "net": NetStat(
                bytes_sent=1024**3,
                bytes_recv=4 * 1024**3,
                packets_sent=1_000_000,
                packets_recv=2_000_000,
                send_rate=1.5 * 1024**2,
                recv_rate=12.0 * 1024**2,
            ),
            "gpus": (
                GpuStat(
                    index=0,
                    name="Mock GPU 3050",
                    utilization=self.gpu_percent,
                    memory_used=2 * 1024**3,
                    memory_total=4 * 1024**3,
                    temperature=self.temperature_c,
                    power_w=45.0,
                    fan_percent=60.0,
                    clock_mhz=1500.0,
                    power_limit_w=80.0,
                ),
            ),
            "thermal": ThermalStat(
                source="mock",
                temperatures=(("cpu", self.temperature_c), ("gpu", self.temperature_c - 5.0)),
            ),
        }
