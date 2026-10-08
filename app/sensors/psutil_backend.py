from __future__ import annotations

import time

from .base import Backend, Partial, SensorUnavailable
from .types import CpuStat, DiskStat, MemoryStat, NetStat


class PsutilBackend(Backend):
    name = "psutil"

    def __init__(self) -> None:
        try:
            import psutil
        except ImportError as e:
            raise SensorUnavailable(f"psutil not installed: {e}") from e
        self._psutil = psutil
        self._prev_net = psutil.net_io_counters()
        self._prev_ts = time.monotonic()
        psutil.cpu_percent(interval=None)

    def collect(self) -> Partial:
        psutil = self._psutil
        vm = psutil.virtual_memory()
        swap = psutil.swap_memory()
        freq = psutil.cpu_freq()

        disks: list[DiskStat] = []
        for part in psutil.disk_partitions(all=False):
            if not part.mountpoint:
                continue
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (OSError, PermissionError):
                continue
            disks.append(
                DiskStat(
                    device=part.device,
                    mountpoint=part.mountpoint,
                    fstype=part.fstype,
                    total=u.total,
                    used=u.used,
                    free=u.free,
                    percent=u.percent,
                )
            )

        net = psutil.net_io_counters()
        now = time.monotonic()
        dt = max(now - self._prev_ts, 1e-6)
        send_rate = max(net.bytes_sent - self._prev_net.bytes_sent, 0) / dt
        recv_rate = max(net.bytes_recv - self._prev_net.bytes_recv, 0) / dt
        self._prev_net, self._prev_ts = net, now

        return {
            "cpu": CpuStat(
                percent=psutil.cpu_percent(interval=None),
                per_core=tuple(psutil.cpu_percent(percpu=True)),
                physical_cores=psutil.cpu_count(logical=False) or 0,
                logical_cores=psutil.cpu_count(logical=True) or 0,
                freq_mhz=freq.current if freq else None,
                freq_max_mhz=freq.max if freq else None,
            ),
            "memory": MemoryStat(
                total=vm.total,
                used=vm.used,
                available=vm.available,
                percent=vm.percent,
                swap_total=swap.total,
                swap_used=swap.used,
                swap_percent=swap.percent,
            ),
            "disks": tuple(disks),
            "net": NetStat(
                bytes_sent=net.bytes_sent,
                bytes_recv=net.bytes_recv,
                packets_sent=net.packets_sent,
                packets_recv=net.packets_recv,
                send_rate=send_rate,
                recv_rate=recv_rate,
            ),
        }
