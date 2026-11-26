from __future__ import annotations

import json
import threading
import time

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QPushButton

from app.history import HistorySample, PerformanceHistory
from app.i18n import tr
from app.sensors import MockBackend, SensorManager
from app.ui import theme
from app.ui.components import RingCard
from app.ui.dashboard import DashboardPage, ProcessLoadWidget
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
    page = window.page("dashboard")
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
        # Queued cross-thread signals are delivered by processEvents, not by
        # QSignalSpy.wait() when no nested event loop is running.
        qapp.processEvents()
        time.sleep(0.01)
    sampler.stop()
    assert spy.count() >= 2
    snapshot = spy.at(1)[0]
    assert snapshot.cpu is not None
    assert snapshot.gpu is not None


def test_sampler_closes_manager_on_sampler_thread(qapp) -> None:
    class RecordingManager:
        def __init__(self) -> None:
            self._snapshot = SensorManager.mock().snapshot()
            self.closed_on: int | None = None

        def snapshot(self):
            return self._snapshot

        def close(self) -> None:
            self.closed_on = threading.get_ident()

    manager = RecordingManager()
    sampler = SensorSampler(manager, interval_ms=60)
    spy = QSignalSpy(sampler.snapshot_ready)
    sampler.start()
    deadline = time.monotonic() + 3.0
    while spy.count() < 1 and time.monotonic() < deadline:
        spy.wait(200)
    assert sampler.stop()

    assert manager.closed_on is not None
    assert manager.closed_on != threading.get_ident()


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
    assert keys[0].startswith(tr("temp_target_cpu"))
    assert keys[1].startswith(tr("temp_target_board"))
    assert keys[2].startswith(tr("temp_target_gpu"))
    assert any("System zone 0 (ACPI)" in key for key in keys)
    assert page.thermal._rows[keys[0]][2].text() == "—"
    assert page.thermal._rows[keys[2]][2].text() == "79°C"


def test_dashboard_thermal_card_explains_missing_sensors(qapp) -> None:
    from app.sensors.types import Snapshot, ThermalStat

    page = DashboardPage()
    snapshot = Snapshot(
        ts=0.0,
        thermal=ThermalStat(
            source="lhm_pythonnet",
            temperatures=(("gpu", 52.0),),
            notes=("LHM CPU temperature sensor reports 0°C", "LHM motherboard has no temperature sensors"),
            sources=("lhm_pythonnet",),
        ),
    )
    page.apply_snapshot(snapshot)
    tooltip = page.thermal.toolTip()
    assert tr("temp_note_cpu_zero") in tooltip
    assert tr("temp_note_board_missing") in tooltip


def test_dashboard_has_no_status_strip(qapp) -> None:
    page = DashboardPage()
    assert not hasattr(page, "status_strip")
    s = SensorManager([MockBackend(cpu_percent=42.0, memory_percent=60.0)]).snapshot()
    page.apply_snapshot(s)
    assert page.cpu.value.text() == "42%"


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
    from app.ui import theme
    from app.ui.dashboard import _activity_style

    assert _activity_style("ok") == (theme.OK, "check")
    assert _activity_style("warn") == (theme.WARN, "warning")
    assert _activity_style("error") == (theme.DANGER, "error")


def test_dashboard_disk_extra_color_follows_level(qapp) -> None:
    from app.sensors.types import DiskStat, Snapshot

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
    # The card colours RAM/disk by load level; the exact hue follows the theme,
    # which earlier tests may have reconfigured — compare against the source.
    from app.ui import dashboard as _dash

    assert _dash.DANGER not in page.disk.extra.styleSheet()
    assert _dash.WARN in page.disk.extra.styleSheet()


def _row4_spans(page: DashboardPage, width: int) -> list[int]:
    page._relayout(width)
    grid, widgets = page._grid_rows["row4"]
    spans: list[int] = []
    for w in widgets:
        for i in range(grid.count()):
            if grid.itemAt(i).widget() is w:
                spans.append(grid.getItemPosition(i)[3])
                break
    return spans


def test_dashboard_row4_widgets_are_equal_width(qapp) -> None:
    # Review: gaming banner / network / notifications must align on the grid.
    page = DashboardPage()
    assert _row4_spans(page, 1600) == [4, 4, 4]  # wide
    assert _row4_spans(page, 1200) == [12, 6, 6]  # mid: net and notif equal
    assert _row4_spans(page, 800) == [12, 6, 6]  # compact


def test_recent_actions_empty_hint_is_centered(qapp) -> None:
    from app.ui.activity import ActivityLog

    ActivityLog.instance().clear()
    from app.ui.dashboard import RecentActionsWidget

    widget = RecentActionsWidget()
    # stretch + hint + stretch (the card no longer reads as "big and empty")
    assert widget._rows.count() == 3
    hint = widget._rows.itemAt(1).widget()
    assert hint.alignment() & Qt.AlignmentFlag.AlignCenter


def test_dashboard_thermal_bars_have_threshold_marker(qapp) -> None:
    from app.sensors.types import Snapshot, ThermalStat

    page = DashboardPage()
    snap = Snapshot(ts=1.0, thermal=ThermalStat(source="t", temperatures=(("CPU", 70.0),)))
    page.apply_snapshot(snap)
    markers = [b._marker for _l, b, _t in page.thermal._rows.values()]
    assert markers and all(m == 85.0 for m in markers)


def _row_spans(page: DashboardPage, row: str, width: int) -> list[int]:
    page._relayout(width)
    grid, widgets = page._grid_rows[row]
    spans: list[int] = []
    for w in widgets:
        for i in range(grid.count()):
            if grid.itemAt(i).widget() is w:
                spans.append(grid.getItemPosition(i)[3])
                break
    return spans


def test_dashboard_four_zone_layout_spans(qapp) -> None:
    page = DashboardPage()
    assert len(page.sections) == 4
    assert [label.text() for label in page.sections] == [
        tr("dash_sec_overview").upper(),
        tr("dash_sec_monitoring").upper(),
        tr("dash_sec_system").upper(),
        tr("dash_sec_activity").upper(),
    ]
    assert _row_spans(page, "row1", 1600) == [2, 2, 2, 2, 2, 2]
    assert _row_spans(page, "row2", 1600) == [5, 4, 3]
    assert _row_spans(page, "row5", 1600) == [6, 6]
    assert _row_spans(page, "row2", 800) == [12, 12, 12]


def test_dashboard_temp_tile_shows_hottest_sensor(qapp) -> None:
    from app.sensors.types import GpuStat, Snapshot, ThermalStat

    page = DashboardPage()
    snap = Snapshot(
        ts=1.0,
        thermal=ThermalStat(source="t", temperatures=(("CPU", 72.0), ("zone1", 61.0))),
        gpus=(GpuStat(index=0, name="RTX", utilization=20.0, memory_used=0, memory_total=1, temperature=79.0),),
    )
    page.apply_snapshot(snap)
    assert page.temp_tile.value.text() == "79°C"
    assert page.temp_tile.sub.text() == tr("dash_temp_sub")

    page.apply_snapshot(SensorManager([]).snapshot())
    assert page.temp_tile.value.text() == "—"
    assert page.temp_tile.sub.text() == tr("dash_temp_none")


def test_dashboard_resource_history_reads_last_hour(qapp, tmp_path) -> None:
    store = tmp_path / "history.jsonl"
    now = time.time()
    samples = [
        HistorySample(ts=now - 40 * 60, cpu=31.0, ram=48.0, gpu=12.0),
        HistorySample(ts=now - 10 * 60, cpu=62.0, ram=55.0, gpu=35.0),
        HistorySample(ts=now - 2 * 3600, cpu=99.0, ram=99.0, gpu=99.0),
    ]
    store.write_text("".join(json.dumps(s.to_dict()) + "\n" for s in samples), encoding="utf-8")
    history = PerformanceHistory(store=store)
    page = DashboardPage(history=history)
    assert page.history_widget.history is history
    assert len(page.history_widget.chart._canvas._times) == 2
    assert list(page.history_widget.chart._canvas._history["cpu"]) == [31.0, 62.0]
    assert tr("hist_samples", count=2) in page.history_widget.info.text()

    page.retranslate()
    assert page.history_widget.chart._title_label.text() == tr("dash_hist_title")


def test_dashboard_recommendations_from_snapshot(qapp) -> None:
    from app.sensors.types import DiskStat, GpuStat, Snapshot, ThermalStat

    page = DashboardPage()
    snap = Snapshot(
        ts=1.0,
        cpu=SensorManager([MockBackend(cpu_percent=94.0)]).snapshot().cpu,
        memory=SensorManager([MockBackend(memory_percent=50.0)]).snapshot().memory,
        thermal=ThermalStat(source="t", temperatures=(("CPU", 88.0),)),
        gpus=(GpuStat(index=0, name="RTX", utilization=92.0, memory_used=0, memory_total=1, temperature=70.0),),
        disks=(
            DiskStat(
                device="C:\\",
                mountpoint="C:\\",
                fstype="NTFS",
                total=100 * 1024**3,
                used=87 * 1024**3,
                free=13 * 1024**3,
                percent=87.0,
            ),
        ),
    )
    page.apply_snapshot(snap)
    keys = [key for key, _fmt, target in page.recommendations._specs]
    assert keys == ["dash_rec_high_cpu", "dash_rec_high_gpu", "dash_rec_hot", "dash_rec_disk"]

    buttons = [w for w in page.recommendations.findChildren(QPushButton) if w.text() == tr("dash_rec_open")]
    assert len(buttons) == 4
    spy = QSignalSpy(page.navigate)
    QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
    assert [spy.at(i)[0] for i in range(spy.count())] == ["processes"]


def test_dashboard_customizer_dialog_values(qapp) -> None:
    from app.ui.dashboard_custom import (
        DashboardCustomizerDialog,
        parse_dashboard_hidden,
        serialize_dashboard_hidden,
    )

    dialog = DashboardCustomizerDialog("cpu,chart", None)
    assert dialog.values() == {"cpu", "chart"}
    dialog._checks["ram"].setChecked(False)
    assert dialog.values() == {"cpu", "chart", "ram"}
    assert parse_dashboard_hidden("cpu,unknown,ram") == {"cpu", "ram"}
    assert serialize_dashboard_hidden({"ram", "cpu"}) == "cpu,ram"


def test_dashboard_hides_selected_widgets_and_sections(qapp) -> None:
    page = DashboardPage(dashboard_hidden="cpu,history,recent")
    assert page.cpu.isHidden()
    assert not page.ram.isHidden()
    assert page.history_widget.isHidden()
    assert page.recent_actions.isHidden()
    assert not page.sections[0].isHidden()
    assert not page.sections[3].isHidden()

    page.set_hidden_widgets("cpu,ram,gpu,disk,temp,health")
    assert page.sections[0].isHidden()
    assert page.sections[1].isHidden() is False
    assert not page.chart.isHidden()


def test_main_window_applies_dashboard_hidden(qapp) -> None:
    window = MainWindow()
    window.apply_dashboard_hidden("cpu,chart")
    dashboard = window.page("dashboard")
    assert dashboard.cpu.isHidden()
    assert dashboard.chart.isHidden()
    assert not dashboard.ram.isHidden()
    window.close()


def test_main_window_shares_history_with_dashboard(qapp, tmp_path) -> None:
    history = PerformanceHistory(store=tmp_path / "shared.jsonl")
    window = MainWindow(history=history)
    dashboard = window.page("dashboard")
    history_page = window.page("history")
    assert dashboard.history_widget.history is history
    assert history_page._history is history
    window.close()


def test_process_load_labels_scale_with_ui(qapp) -> None:
    original = theme.UI_SCALE
    try:
        theme.set_ui_scale(150)
        widget = ProcessLoadWidget()
        widget.set_rows([("python.exe", 36.1, 2048)])
        row = widget._rows_box.itemAt(0).layout()
        cpu_label = row.itemAt(2).widget()
        mem_label = row.itemAt(3).widget()
        assert cpu_label.minimumWidth() == theme.ls(48)
        assert mem_label.minimumWidth() == theme.ls(60)
        assert cpu_label.minimumWidth() >= QFontMetrics(cpu_label.font()).horizontalAdvance("36.1%")
    finally:
        theme.set_ui_scale(original)
