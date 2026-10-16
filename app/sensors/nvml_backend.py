from __future__ import annotations

from .base import Backend, Partial, SensorUnavailable
from .types import GpuStat


class NvmlBackend(Backend):
    name = "nvml"

    def __init__(self) -> None:
        try:
            import pynvml
        except ImportError as e:
            raise SensorUnavailable(f"nvidia-ml-py not installed: {e}") from e
        try:
            pynvml.nvmlInit()
        except pynvml.NVMLError as e:
            raise SensorUnavailable(f"NVML init failed: {e}") from e
        self._nvml = pynvml
        try:
            self._handles = [pynvml.nvmlDeviceGetHandleByIndex(i) for i in range(pynvml.nvmlDeviceGetCount())]
        except pynvml.NVMLError as e:
            # nvmlInit() already succeeded; release it so a failed probe does
            # not leak the NVML refcount (it would prevent a later re-init).
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass
            raise SensorUnavailable(f"NVML device query failed: {e}") from e
        if not self._handles:
            try:
                pynvml.nvmlShutdown()
            except pynvml.NVMLError:
                pass
            raise SensorUnavailable("no NVIDIA GPUs reported by NVML")
        self._last: dict[int, GpuStat] = {}

    def _opt(self, fn):
        try:
            return fn()
        except self._nvml.NVMLError:
            return None

    def _read(self, index: int, handle) -> GpuStat:
        nvml = self._nvml
        prev = self._last.get(index)

        # On laptops with hybrid graphics the GPU may be asleep, and some NVML
        # calls (notably utilization) intermittently return NVML_ERROR_UNKNOWN.
        # Read best-effort and fall back to the last known values so the GPU
        # stays visible instead of dropping out of the snapshot.
        name = self._opt(lambda: nvml.nvmlDeviceGetName(handle))
        if isinstance(name, bytes):
            name = name.decode(errors="replace")
        if not name:
            name = prev.name if prev is not None else f"GPU {index}"

        util = self._opt(lambda: nvml.nvmlDeviceGetUtilizationRates(handle))
        utilization = float(util.gpu) if util is not None else (prev.utilization if prev is not None else 0.0)

        mem = self._opt(lambda: nvml.nvmlDeviceGetMemoryInfo(handle))
        if mem is not None:
            memory_used, memory_total = int(mem.used), int(mem.total)
        elif prev is not None:
            memory_used, memory_total = prev.memory_used, prev.memory_total
        else:
            memory_used = memory_total = 0

        temperature = self._opt(lambda: nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU))
        power_w = self._opt(lambda: nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0)
        fan_percent = self._opt(lambda: float(nvml.nvmlDeviceGetFanSpeed(handle)))
        clock_mhz = self._opt(lambda: float(nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_SM)))
        power_limit_w = (
            self._opt(lambda: nvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0)
            or self._opt(lambda: nvml.nvmlDeviceGetPowerManagementDefaultLimit(handle) / 1000.0)
            or self._opt(lambda: nvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0)
        )
        if power_limit_w is None and prev is not None:
            power_limit_w = prev.power_limit_w

        stat = GpuStat(
            index=index,
            name=name,
            utilization=utilization,
            memory_used=memory_used,
            memory_total=memory_total,
            temperature=float(temperature) if temperature is not None else None,
            power_w=power_w,
            fan_percent=fan_percent,
            clock_mhz=clock_mhz,
            power_limit_w=power_limit_w,
        )
        self._last[index] = stat
        return stat

    def collect(self) -> Partial:
        return {"gpus": tuple(self._read(i, h) for i, h in enumerate(self._handles))}

    def close(self) -> None:
        try:
            self._nvml.nvmlShutdown()
        except self._nvml.NVMLError:
            pass
