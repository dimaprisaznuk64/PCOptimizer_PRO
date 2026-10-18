from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtTest import QSignalSpy, QTest

from app.sensors import MockBackend, SensorManager
from app.ui.components import RingCard
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


def test_ring_card_emits_click(qapp) -> None:
    card = RingCard("CPU", "#00BFFF", icon_name="cpu")
    card.resize(160, 180)
    spy = QSignalSpy(card.clicked)
    QTest.mouseClick(card, Qt.MouseButton.LeftButton, pos=card.rect().center())
    assert spy.count() == 1


def test_dashboard_cards_emit_navigation(qapp) -> None:
    page = DashboardPage()
    spy = QSignalSpy(page.navigate)
    page.cpu.clicked.emit()
    page.ram.clicked.emit()
    page.gpu.clicked.emit()
    page.disk.clicked.emit()
    assert [spy.at(i)[0] for i in range(spy.count())] == ["monitor", "monitor", "gpu", "disk"]


def test_main_window_card_navigates_to_detail(qapp) -> None:
    window = MainWindow()
    page = window.page("dashboard")
    QTest.mouseClick(page.gpu, Qt.MouseButton.LeftButton, pos=page.gpu.rect().center())
    assert window.current_key == "gpu"
    QTest.mouseClick(page.cpu, Qt.MouseButton.LeftButton, pos=page.cpu.rect().center())
    assert window.current_key == "monitor"
    QTest.mouseClick(page.disk, Qt.MouseButton.LeftButton, pos=page.disk.rect().center())
    assert window.current_key == "disk"
    window.close()


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


def test_dashboard_thermal_rows_show_cpu_and_gpu(qapp) -> None:
    from app.sensors.types import GpuStat, Snapshot, ThermalStat

    page = DashboardPage()
    s = Snapshot(
        ts=0.0,
        thermal=ThermalStat(source="wmi_acpi", temperatures=(("zone0", 66.0),)),
        gpus=(GpuStat(index=0, name="RTX", utilization=0.0, memory_used=0, memory_total=1, temperature=79.0),),
    )
    page.apply_snapshot(s)
    keys = list(page.thermal._rows)
    # The lone ACPI zone is promoted to a CPU row; GPU comes from NVML.
    assert keys[0].startswith("CPU")
    assert any(k.startswith("GPU") for k in keys)


def test_dashboard_notifications_hidden_when_empty(qapp) -> None:
    from app.ui.activity import ActivityLog

    log = ActivityLog.instance()
    log.clear()
    log.health = None
    page = DashboardPage()
    # No warnings recorded -> the notifications card collapses.
    page.notif_widget._render()
    assert page.notif_widget.isHidden()
    log.record("Problem", "disk full", level="warn")
    assert not page.notif_widget.isHidden()
    log.clear()  # do not leak the warning into other tests


def test_dashboard_error_entry_shows_in_notifications(qapp) -> None:
    from app.ui.activity import ActivityLog

    log = ActivityLog.instance()
    log.clear()
    page = DashboardPage()
    # Failed operations (level=error) must be visible in the bell card too.
    page.notif_widget._render()
    assert page.notif_widget.isHidden()
    log.record("Apply failed", "powercfg denied", level="error")
    assert not page.notif_widget.isHidden()
    log.clear()


def test_activity_style_levels(qapp) -> None:
    from app.ui.dashboard import _activity_style
    from app.ui.theme import DANGER, OK, WARN

    assert _activity_style("ok") == (OK, "check")
    assert _activity_style("warn") == (WARN, "warning")
    assert _activity_style("error") == (DANGER, "error")


def test_dashboard_disk_extra_color_follows_level(qapp) -> None:
    from app.sensors.types import DiskStat, Snapshot
    from app.ui.theme import WARN

    page = DashboardPage()
    s = Snapshot(
        ts=0.0,
        disks=(
            DiskStat(
                device="C:\\",
                mountpoint="C:\\",
                fstype="NTFS",
                total=100 * 1024**3,
                used=86 * 1024**3,
                free=14 * 1024**3,
                percent=86.0,
            ),
        ),
    )
    page.apply_snapshot(s)
    assert "86%" in page.disk.value.text()
    assert WARN in page.disk.extra.styleSheet()
