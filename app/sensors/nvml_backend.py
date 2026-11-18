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
        self._nvml_fail_count: dict[int, int] = {}

    def _opt(self, fn):
        try:
            return fn()
        except self._nvml.NVMLError:
            return None

    def _opt_fn(self, name: str, *args):
        fn = getattr(self._nvml, name, None)
        if fn is None:
            return None
        return self._opt(lambda: fn(*args))

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

        hotspot_sensor = getattr(nvml, "NVML_TEMPERATURE_GPU_HOT_SPOT", 1)
        temperature_hotspot = self._opt(lambda: nvml.nvmlDeviceGetTemperature(handle, hotspot_sensor))
        if temperature_hotspot is None and prev is not None:
            temperature_hotspot = prev.temperature_hotspot

        memory_clock_mhz = self._opt_fn(
            "nvmlDeviceGetClockInfo", handle, getattr(nvml, "NVML_CLOCK_MEM", 2)
        )
        if memory_clock_mhz is None and prev is not None:
            memory_clock_mhz = prev.memory_clock_mhz

        throttle_current = self._opt_fn("nvmlDeviceGetCurrentClocksThrottleReasons", handle)
        throttle_supported = self._opt_fn("nvmlDeviceGetSupportedClocksThrottleReasons", handle)
        if throttle_current is None:
            throttle_reasons = prev.throttle_reasons if prev is not None else None
            throttling = prev.throttling if prev is not None else False
        else:
            throttle_reasons = int(throttle_current)
            mask = int(throttle_supported) if throttle_supported is not None else throttle_reasons
            idle_bit = int(getattr(nvml, "NVML_CLOCKS_THROTTLE_REASON_GPU_IDLE", 0x1))
            throttling = bool(throttle_reasons & mask & ~idle_bit)

        # Check if dynamic metrics failed to query in this sample
        dynamic_ok = util is not None or mem is not None
        if dynamic_ok:
            self._nvml_fail_count[index] = 0
        else:
            self._nvml_fail_count[index] = self._nvml_fail_count.get(index, 0) + 1

        # If NVML continuously fails for 3+ polls, stop producing stale cached data
        if self._nvml_fail_count.get(index, 0) >= 3 and prev is not None:
            return None  # type: ignore[return-value]

        is_stale = not dynamic_ok and prev is not None

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
            stale=is_stale,
            temperature_hotspot=float(temperature_hotspot) if temperature_hotspot is not None else None,
            memory_clock_mhz=float(memory_clock_mhz) if memory_clock_mhz is not None else None,
            throttle_reasons=throttle_reasons,
            throttling=throttling,
        )
        self._last[index] = stat
        return stat

    def collect(self) -> Partial:
        gpus = [self._read(i, h) for i, h in enumerate(self._handles)]
        return {"gpus": tuple(g for g in gpus if g is not None)}

    def close(self) -> None:
        try:
            self._nvml.nvmlShutdown()
        except self._nvml.NVMLError:
            pass
