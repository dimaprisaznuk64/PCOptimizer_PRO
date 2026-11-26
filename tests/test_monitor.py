from __future__ import annotations

import time

from app.sensors import MockBackend, SensorManager
from app.sensors.types import CpuStat, MemoryStat, Snapshot, ThermalStat
from app.ui import theme
from app.ui.main_window import MainWindow
from app.ui.monitor import MonitorPage


def _wait_until(qapp, cond, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeProcessService:
    def top_by_memory(self, limit: int = 8):
        return [
            type("P", (), {"name": "chrome.exe", "memory_bytes": 2 * 1024**3, "memory_percent": 12.5})(),
            type("P", (), {"name": "python.exe", "memory_bytes": 1 * 1024**3, "memory_percent": 6.25})(),
        ][:limit]


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


def test_monitor_tracks_peak_cpu_memory_and_temperature(qapp) -> None:
    page = MonitorPage()
    low = Snapshot(
        ts=0.0,
        cpu=CpuStat(percent=20.0, per_core=(10.0, 20.0), physical_cores=1, logical_cores=2),
        memory=MemoryStat(100, 30, 70, 30.0, 0, 0, 0.0),
        thermal=ThermalStat(source="wmi_acpi", temperatures=(("zone0", 55.0),)),
    )
    high = Snapshot(
        ts=1.0,
        cpu=CpuStat(percent=80.0, per_core=(90.0, 70.0), physical_cores=1, logical_cores=2),
        memory=MemoryStat(100, 70, 30, 70.0, 0, 0, 0.0),
        thermal=ThermalStat(source="wmi_acpi", temperatures=(("zone0", 90.0),)),
    )
    page.apply_snapshot(low)
    page.apply_snapshot(high)
    assert "peak 80%" in page.cpu_sub.text()
    assert "peak 70%" in page.mem_sub.text()
    assert "peak 90°c" in page.thermals.title_label.text().lower()

    page.apply_snapshot(low)
    assert "peak 80%" in page.cpu_sub.text()
    assert "peak 70%" in page.mem_sub.text()
    assert "peak 90°c" in page.thermals.title_label.text().lower()


def test_monitor_shows_commit_charge_when_available(qapp) -> None:
    page = MonitorPage()
    charged = Snapshot(
        ts=0.0,
        memory=MemoryStat(
            100 * 1024**3,
            60 * 1024**3,
            40 * 1024**3,
            60.0,
            0,
            0,
            0.0,
            commit_used=30 * 1024**3,
            commit_limit=100 * 1024**3,
        ),
    )
    page.apply_snapshot(charged)
    assert not page.commit_sub.isHidden()
    assert "30.0GB" in page.commit_sub.text()
    assert "100.0GB" in page.commit_sub.text()

    page.retranslate()
    assert "30.0GB" in page.commit_sub.text()

    page.apply_snapshot(
        Snapshot(
            ts=1.0,
            memory=MemoryStat(100 * 1024**3, 60 * 1024**3, 40 * 1024**3, 60.0, 0, 0, 0.0),
        )
    )
    assert page.commit_sub.isHidden()


def test_monitor_shows_top_ram_processes(qapp) -> None:
    page = MonitorPage(process_service=FakeProcessService())
    page.refresh_memory_processes()
    assert _wait_until(qapp, lambda: page.proc_table.rowCount() == 2)
    assert page.proc_table.item(0, 0).text() == "chrome.exe"
    assert page.proc_table.item(0, 1).text() == "2.0GB"
    assert page.proc_table.item(0, 2).text() == "12.5%"
    assert page.proc_table.item(1, 0).text() == "python.exe"


def test_monitor_refresh_after_task_deleted(qapp) -> None:
    page = MonitorPage(process_service=FakeProcessService())
    page.refresh_memory_processes()
    assert _wait_until(qapp, lambda: page.proc_table.rowCount() == 2)
    assert _wait_until(qapp, lambda: page._proc_task is None)
    page.refresh_memory_processes()
    assert page._proc_task is not None
    assert _wait_until(qapp, lambda: page.proc_table.rowCount() == 2)


def test_main_window_broadcast_reaches_monitor(qapp) -> None:
    window = MainWindow()
    window.show_page("monitor")
    window.handle_snapshot(SensorManager([MockBackend(cpu_percent=33.0)]).snapshot())
    monitor = window.page("monitor")
    assert monitor.cpu_value.text() == "33%"
    window.close()


def test_core_labels_scale_with_ui(qapp) -> None:
    original = theme.UI_SCALE
    try:
        theme.set_ui_scale(150)
        page = MonitorPage()
        page.apply_snapshot(SensorManager([MockBackend()]).snapshot())
        label = page.cores._cells[0][0]
        assert label.width() == theme.ls(28)
        assert page.cores._layout.columnMinimumWidth(3) == theme.SPACING_XL
    finally:
        theme.set_ui_scale(original)
