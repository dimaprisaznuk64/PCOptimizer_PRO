from __future__ import annotations

import threading
import time

from app.sensors import Backend, CommitCharge, MockBackend, Partial, SensorManager
from app.sensors.psutil_backend import PsutilBackend


class OkBackend(Backend):
    name = "ok"

    def __init__(self, data: Partial) -> None:
        self._data = data

    def collect(self) -> Partial:
        return dict(self._data)


class FailingBackend(Backend):
    name = "failing"

    def collect(self) -> Partial:
        raise RuntimeError("boom")


def test_mock_snapshot_is_complete_and_clean() -> None:
    manager = SensorManager.mock()
    s = manager.snapshot()
    assert s.healthy
    assert s.cpu and s.memory and s.disks and s.net and s.gpu and s.thermal
    assert s.gpus[0].index == 0
    assert dict(s.errors) == {}


def test_mock_values_are_deterministic() -> None:
    a = SensorManager.mock().snapshot()
    b = SensorManager.mock().snapshot()
    assert a.cpu and b.cpu
    assert a.cpu.percent == b.cpu.percent
    assert a.memory and b.memory
    assert a.memory.used == b.memory.used


def test_manager_merges_partial_backends() -> None:
    manager = SensorManager(
        [
            OkBackend({"cpu": MockBackend().collect()["cpu"]}),
            OkBackend({"memory": MockBackend().collect()["memory"]}),
        ]
    )
    s = manager.snapshot()
    assert s.cpu is not None
    assert s.memory is not None
    assert s.net is None


def test_first_backend_wins_on_duplicate_keys() -> None:
    manager = SensorManager(
        [
            OkBackend({"cpu": MockBackend(cpu_percent=11.0).collect()["cpu"]}),
            OkBackend({"cpu": MockBackend(cpu_percent=99.0).collect()["cpu"]}),
        ]
    )
    s = manager.snapshot()
    assert s.cpu and s.cpu.percent == 11.0


def test_failing_backend_is_recorded_and_others_survive() -> None:
    manager = SensorManager([FailingBackend(), OkBackend({"memory": MockBackend().collect()["memory"]})])
    s = manager.snapshot()
    assert s.memory is not None
    assert s.errors["failing"] == "boom"


def test_defaults_produce_healthy_snapshot_on_this_pc() -> None:
    manager = SensorManager.with_defaults()
    assert "psutil" in manager.backend_names
    s = manager.snapshot()
    assert s.healthy
    assert s.cpu and 0 <= s.cpu.percent <= 100
    assert s.memory and s.memory.total > 0
    assert s.disks
    assert s.net and s.net.send_rate >= 0 and s.net.recv_rate >= 0
    manager.close()


def test_thermal_close_from_foreign_thread_keeps_com_object() -> None:
    from app.sensors.thermal_backend import ThermalBackend

    backend = ThermalBackend()
    sentinel = object()
    backend._zones = sentinel
    backend._owner_thread_id = threading.get_ident() + 1
    backend.close()
    assert backend._zones is sentinel

    backend._owner_thread_id = threading.get_ident()
    backend.close()
    assert backend._zones is None
    assert backend._owner_thread_id is None


def test_gpu_backend_records_error_when_unavailable() -> None:
    manager = SensorManager([], unavailable={"nvml": "no driver"})
    s = manager.snapshot()
    assert s.gpu is None
    assert s.errors["nvml"] == "no driver"


def test_psutil_rates_change_between_samples() -> None:
    manager = SensorManager.with_defaults()
    first = manager.snapshot()
    time.sleep(0.3)
    second = manager.snapshot()
    manager.close()
    assert first.net and second.net
    assert second.net.bytes_recv >= first.net.bytes_recv
    assert second.net.bytes_sent >= first.net.bytes_sent


def test_psutil_backend_reports_commit_charge() -> None:
    backend = PsutilBackend(
        commit_reader=lambda: CommitCharge(limit=100 * 1024**3, available=40 * 1024**3, used=60 * 1024**3)
    )
    try:
        memory = backend.collect()["memory"]
        assert memory is not None
        assert memory.commit_limit == 100 * 1024**3
        assert memory.commit_used == 60 * 1024**3
    finally:
        backend.close()


def test_mock_factory_on_real_manager_does_not_need_hardware() -> None:
    s = SensorManager([MockBackend(cpu_percent=7.5)]).snapshot()
    assert s.cpu and s.cpu.percent == 7.5
    assert not s.errors


class _FakeNVMLError(Exception):
    pass


class _FakeUtil:
    def __init__(self, gpu: float) -> None:
        self.gpu = gpu


class _FakeMem:
    used = 1024
    total = 4096


class _FakeNvml:
    NVMLError = _FakeNVMLError
    NVML_TEMPERATURE_GPU = 0
    NVML_TEMPERATURE_GPU_HOT_SPOT = 1
    NVML_CLOCK_SM = 0
    NVML_CLOCK_MEM = 1
    NVML_CLOCKS_THROTTLE_REASON_GPU_IDLE = 1

    def __init__(
        self,
        util_fails: bool = False,
        hotspot: float | None = None,
        mem_clock: float | None = None,
        throttle_current: int | None = None,
        throttle_supported: int | None = None,
    ) -> None:
        self.util_fails = util_fails
        self.hotspot = hotspot
        self.mem_clock = mem_clock
        self.throttle_current = throttle_current
        self.throttle_supported = throttle_supported

    def nvmlDeviceGetName(self, handle):
        return "Fake GPU"

    def nvmlDeviceGetUtilizationRates(self, handle):
        if self.util_fails:
            raise _FakeNVMLError("Unknown Error")
        return _FakeUtil(42.0)

    def nvmlDeviceGetMemoryInfo(self, handle):
        if self.util_fails:
            raise _FakeNVMLError("Unknown Error")
        return _FakeMem()

    def nvmlDeviceGetTemperature(self, handle, sensor):
        if sensor == self.NVML_TEMPERATURE_GPU_HOT_SPOT and self.hotspot is not None:
            return self.hotspot
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetPowerUsage(self, handle):
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetFanSpeed(self, handle):
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetClockInfo(self, handle, clock):
        if clock == self.NVML_CLOCK_MEM and self.mem_clock is not None:
            return self.mem_clock
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetCurrentClocksThrottleReasons(self, handle):
        if self.throttle_current is None:
            raise _FakeNVMLError("not supported")
        return self.throttle_current

    def nvmlDeviceGetSupportedClocksThrottleReasons(self, handle):
        if self.throttle_supported is None:
            raise _FakeNVMLError("not supported")
        return self.throttle_supported

    def nvmlDeviceGetPowerManagementLimit(self, handle):
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetPowerManagementDefaultLimit(self, handle):
        raise _FakeNVMLError("not supported")

    def nvmlDeviceGetEnforcedPowerLimit(self, handle):
        raise _FakeNVMLError("not supported")


def _fake_nvml_backend(nvml: _FakeNvml):
    from app.sensors.nvml_backend import NvmlBackend

    backend = NvmlBackend.__new__(NvmlBackend)
    backend._nvml = nvml
    backend._handles = [object()]
    backend._last = {}
    backend._nvml_fail_count = {}
    return backend


def test_nvml_utilization_error_does_not_drop_the_gpu() -> None:
    backend = _fake_nvml_backend(_FakeNvml(util_fails=True))
    part = backend.collect()
    assert len(part["gpus"]) == 1
    assert part["gpus"][0].utilization == 0.0


def test_nvml_utilization_falls_back_to_last_known_value() -> None:
    backend = _fake_nvml_backend(_FakeNvml(util_fails=False))
    first = backend.collect()["gpus"][0]
    assert first.utilization == 42.0
    assert not first.stale
    backend._nvml.util_fails = True
    second = backend.collect()["gpus"][0]
    assert second.utilization == 42.0
    assert second.memory_total == 4096
    assert second.stale


def test_nvml_consecutive_failures_drop_gpu_after_threshold() -> None:
    backend = _fake_nvml_backend(_FakeNvml(util_fails=False))
    backend.collect()  # sample 1 ok
    backend._nvml.util_fails = True
    assert len(backend.collect()["gpus"]) == 1  # sample 2 fail (stale)
    assert len(backend.collect()["gpus"]) == 1  # sample 3 fail (stale)
    assert len(backend.collect()["gpus"]) == 0  # sample 4 fail (threshold reached)


def test_nvml_reads_advanced_telemetry() -> None:
    nvml = _FakeNvml(hotspot=72.0, mem_clock=7000.0, throttle_current=3, throttle_supported=3)
    gpu = _fake_nvml_backend(nvml).collect()["gpus"][0]
    assert gpu.temperature_hotspot == 72.0
    assert gpu.memory_clock_mhz == 7000.0
    assert gpu.throttle_reasons == 3
    assert gpu.throttling is True


def test_nvml_idle_only_is_not_throttling() -> None:
    nvml = _FakeNvml(throttle_current=1, throttle_supported=3)
    gpu = _fake_nvml_backend(nvml).collect()["gpus"][0]
    assert gpu.throttle_reasons == 1
    assert gpu.throttling is False


def test_nvml_advanced_fields_fall_back_to_last_known_values() -> None:
    nvml = _FakeNvml(hotspot=70.0, mem_clock=6800.0, throttle_current=2, throttle_supported=3)
    backend = _fake_nvml_backend(nvml)
    first = backend.collect()["gpus"][0]
    nvml.hotspot = None
    nvml.mem_clock = None
    nvml.throttle_current = None
    second = backend.collect()["gpus"][0]
    assert second.temperature_hotspot == first.temperature_hotspot
    assert second.memory_clock_mhz == first.memory_clock_mhz
    assert second.throttle_reasons == first.throttle_reasons
    assert second.throttling == first.throttling


class _FakePsutil:
    class _VM:
        total = 16 * 1024**3
        used = 8 * 1024**3
        available = 8 * 1024**3
        percent = 50.0

    class _Net:
        bytes_sent = 100
        bytes_recv = 200
        packets_sent = 1
        packets_recv = 2

    class _Freq:
        current = 3200.0
        max = 3600.0

    def virtual_memory(self):
        return self._VM()

    def swap_memory(self):
        raise RuntimeError("PdhAddEnglishCounterW failed. Performance counters may be disabled.")

    def cpu_freq(self):
        return self._Freq()

    def cpu_percent(self, interval=None, percpu=False):
        return [5.0, 5.0] if percpu else 5.0

    def cpu_count(self, logical=True):
        return 2

    def disk_partitions(self, all=False):
        return []

    def net_io_counters(self):
        return self._Net()


def test_psutil_swap_failure_does_not_drop_other_metrics() -> None:
    from app.sensors.psutil_backend import PsutilBackend

    backend = PsutilBackend.__new__(PsutilBackend)
    backend._psutil = _FakePsutil()
    backend._prev_net = _FakePsutil().net_io_counters()
    backend._prev_ts = time.monotonic()
    part = backend.collect()
    assert part["cpu"] and part["cpu"].percent == 5.0
    assert part["memory"] and part["memory"].swap_total == 0
    assert part["net"] and part["net"].bytes_recv == 200


def test_thermal_backend_initializes_wmi_on_collect_thread(monkeypatch) -> None:
    import sys
    import types

    from app.sensors.thermal_backend import ThermalBackend

    calls: list[str] = []

    class _Zone:
        CurrentTemperature = 3431.5

    class _Wmi:
        def __init__(self, namespace: str) -> None:
            calls.append(f"WMI:{namespace}")

        def MSAcpi_ThermalZoneTemperature(self):
            calls.append("zones")
            return [_Zone()]

    fake = types.ModuleType("wmi")
    fake.WMI = _Wmi
    monkeypatch.setitem(sys.modules, "wmi", fake)

    backend = ThermalBackend()
    assert calls == []
    part = backend.collect()
    assert calls == ["WMI:root\\wmi", "zones"]
    assert part["thermal"].temperatures == (("zone0", 70.0),)
    backend.close()
    assert backend._zones is None
