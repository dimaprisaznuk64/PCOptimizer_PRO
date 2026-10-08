from __future__ import annotations

from app.sensors import MockBackend, SensorManager
from app.sensors.types import CpuStat, Snapshot
from app.ui.main_window import MainWindow
from app.ui.monitor import MonitorPage


def test_monitor_updates_from_mock(qapp) -> None:
    page = MonitorPage()
    page.apply_snapshot(SensorManager([MockBackend(cpu_percent=42.0, memory_percent=60.0)]).snapshot())
    assert page.cpu_value.text() == "42%"
    assert page.mem_value.text() == "60%"
    assert len(page.cores._cells) == 8
    assert page.swap_bar._percent == 25.0
    assert page.net_down_value.text().endswith("/s")
    assert page.disks._rows
    assert page.thermals._rows
    assert page.errors.isHidden()


def test_monitor_core_bars_rebuild_on_count_change(qapp) -> None:
    page = MonitorPage()
    page.apply_snapshot(SensorManager([MockBackend()]).snapshot())
    assert len(page.cores._cells) == 8
    custom = Snapshot(
        ts=0.0,
        cpu=CpuStat(percent=10.0, per_core=tuple(10.0 for _ in range(16)), physical_cores=8, logical_cores=16),
    )
    page.apply_snapshot(custom)
    assert len(page.cores._cells) == 16
    assert page.cores._cells[0][1]._percent == 10.0


def test_monitor_history_grows(qapp) -> None:
    page = MonitorPage()
    manager = SensorManager([MockBackend()])
    for _ in range(4):
        page.apply_snapshot(manager.snapshot())
    assert len(page.cpu_spark._values) == 4
    assert len(page.mem_spark._values) == 4
    assert len(page.net_down_spark._values) == 4
    assert len(page.net_up_spark._values) == 4


def test_main_window_broadcast_reaches_monitor(qapp) -> None:
    window = MainWindow()
    window.show_page("monitor")
    window.handle_snapshot(SensorManager([MockBackend(cpu_percent=33.0)]).snapshot())
    monitor = window.stack.widget(window._index_by_key["monitor"])
    assert monitor.cpu_value.text() == "33%"
    window.close()
