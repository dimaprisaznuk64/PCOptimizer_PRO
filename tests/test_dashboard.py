from __future__ import annotations

import time

from PySide6.QtTest import QSignalSpy

from app.sensors import MockBackend, SensorManager
from app.ui.dashboard import DashboardPage
from app.ui.main_window import MainWindow
from app.ui.sampler import SensorSampler


def test_dashboard_updates_from_mock(qapp) -> None:
    page = DashboardPage()
    s = SensorManager([MockBackend(cpu_percent=42.0, memory_percent=60.0)]).snapshot()
    page.apply_snapshot(s)
    assert page.cpu.value.text() == "42%"
    assert page.ram.value.text() == "60%"
    assert page.gpu.value.text() == "25%"
    assert page.net.value.text().endswith("/s")
    assert page.errors.isHidden()
    assert page.disks._rows
    assert page.thermal._rows


def test_dashboard_records_errors(qapp) -> None:
    page = DashboardPage()
    s = SensorManager([], unavailable={"nvml": "no driver"}).snapshot()
    page.apply_snapshot(s)
    assert not page.errors.isHidden()
    assert "nvml" in page.errors.text()


def test_dashboard_missing_fields_show_placeholder(qapp) -> None:
    page = DashboardPage()
    s = SensorManager([]).snapshot()
    page.apply_snapshot(s)
    assert page.cpu.value.text() == "—"
    assert page.gpu.value.text() == "—"
    assert page.errors.isHidden()


def test_dashboard_history_grows(qapp) -> None:
    page = DashboardPage()
    manager = SensorManager([MockBackend()])
    for _ in range(3):
        page.apply_snapshot(manager.snapshot())
    assert len(page.cpu.spark._values) == 3


def test_main_window_dispatches_snapshot(qapp) -> None:
    window = MainWindow()
    window.handle_snapshot(SensorManager([MockBackend(cpu_percent=7.0)]).snapshot())
    page = window.stack.widget(window._index_by_key["dashboard"])
    assert page.cpu.value.text() == "7%"
    window.close()


def test_dashboard_spark_ranges_fixed_to_100(qapp) -> None:
    page = DashboardPage()
    assert page.cpu.spark._range == (0, 100)
    assert page.ram.spark._range == (0, 100)
    assert page.gpu.spark._range == (0, 100)


def test_sampler_emits_snapshots(qapp) -> None:
    sampler = SensorSampler(SensorManager.mock(), interval_ms=60)
    spy = QSignalSpy(sampler.snapshot_ready)
    sampler.start()
    deadline = time.monotonic() + 3.0
    while spy.count() < 2 and time.monotonic() < deadline:
        spy.wait(200)
    sampler.stop()
    assert spy.count() >= 2
    snapshot = spy.at(1)[0]
    assert snapshot.cpu is not None
    assert snapshot.gpu is not None
