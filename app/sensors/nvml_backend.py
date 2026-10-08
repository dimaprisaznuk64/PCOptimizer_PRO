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
            raise SensorUnavailable(f"NVML device query failed: {e}") from e
        if not self._handles:
            raise SensorUnavailable("no NVIDIA GPUs reported by NVML")

    def _opt(self, fn):
        try:
            return fn()
        except self._nvml.NVMLError:
            return None

    def _read(self, index: int, handle) -> GpuStat:
        nvml = self._nvml
        name = nvml.nvmlDeviceGetName(handle)
        if isinstance(name, bytes):
            name = name.decode(errors="replace")
        util = nvml.nvmlDeviceGetUtilizationRates(handle)
        mem = nvml.nvmlDeviceGetMemoryInfo(handle)
        temperature = self._opt(lambda: nvml.nvmlDeviceGetTemperature(handle, nvml.NVML_TEMPERATURE_GPU))
        power_w = self._opt(lambda: nvml.nvmlDeviceGetPowerUsage(handle) / 1000.0)
        fan_percent = self._opt(lambda: float(nvml.nvmlDeviceGetFanSpeed(handle)))
        clock_mhz = self._opt(lambda: float(nvml.nvmlDeviceGetClockInfo(handle, nvml.NVML_CLOCK_SM)))
        power_limit_w = (
            self._opt(lambda: nvml.nvmlDeviceGetPowerManagementLimit(handle) / 1000.0)
            or self._opt(lambda: nvml.nvmlDeviceGetPowerManagementDefaultLimit(handle) / 1000.0)
            or self._opt(lambda: nvml.nvmlDeviceGetEnforcedPowerLimit(handle) / 1000.0)
        )
        return GpuStat(
            index=index,
            name=name,
            utilization=float(util.gpu),
            memory_used=mem.used,
            memory_total=mem.total,
            temperature=float(temperature) if temperature is not None else None,
            power_w=power_w,
            fan_percent=fan_percent,
            clock_mhz=clock_mhz,
            power_limit_w=power_limit_w,
        )

    def collect(self) -> Partial:
        return {"gpus": tuple(self._read(i, h) for i, h in enumerate(self._handles))}

    def close(self) -> None:
        try:
            self._nvml.nvmlShutdown()
        except self._nvml.NVMLError:
            pass
