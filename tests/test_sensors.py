from __future__ import annotations

import time

from app.sensors import Backend, MockBackend, Partial, SensorManager


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


def test_mock_factory_on_real_manager_does_not_need_hardware() -> None:
    s = SensorManager([MockBackend(cpu_percent=7.5)]).snapshot()
    assert s.cpu and s.cpu.percent == 7.5
    assert not s.errors
