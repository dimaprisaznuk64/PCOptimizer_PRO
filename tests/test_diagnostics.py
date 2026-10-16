from __future__ import annotations

import json
import time

from app.diagnostics import DiagnosticsReport, DiagnosticsService
from app.diagnostics.service import DISK_LIST_SCRIPT, RELIABILITY_SCRIPT, parse_events
from app.ui.diagnostics import DiagnosticsPage
from app.ui.main_window import MainWindow
from app.ui.sidebar import NAV_ITEMS


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _disk_rows() -> list[dict]:
    return [
        {
            "DeviceId": "0",
            "FriendlyName": "Samsung SSD 970 EVO Plus 1TB",
            "MediaType": "SSD",
            "Size": 1000204886016,
            "HealthStatus": "Healthy",
            "SerialNumber": "S6B0NL0T",
        },
        {
            "DeviceId": "1",
            "FriendlyName": "WDC WD10EZEX-08WN4A0",
            "MediaType": "HDD",
            "Size": 1000204886016,
            "HealthStatus": "Warning",
            "SerialNumber": "WD-WCC6Y",
        },
    ]


def _counter_rows() -> list[dict]:
    return [
        {
            "DeviceId": "0",
            "Temperature": 38,
            "Wear": 3,
            "PowerOnHours": 1234,
            "ReadErrorsTotal": 0,
            "WriteErrorsTotal": 0,
        },
        {"DeviceId": "1", "Temperature": 0, "Wear": None, "PowerOnHours": None},
    ]


def _event_rows() -> list[dict]:
    return [
        {
            "Time": "2026-10-16 12:39:44",
            "Level": 2,
            "ProviderName": "Service Control Manager",
            "Id": 7023,
            "Message": "The service terminated with error.",
        },
        {
            "Time": "2026-10-16 12:10:00",
            "Level": 1,
            "ProviderName": "Kernel-Power",
            "Id": 41,
            "Message": "The system has rebooted without cleanly shutting down.",
        },
    ]


def _service(fail: bool = False) -> DiagnosticsService:
    def run(args, timeout):
        script = args[-1]
        if fail:
            return 1, ""
        if script == DISK_LIST_SCRIPT:
            return 0, json.dumps(_disk_rows())
        if script == RELIABILITY_SCRIPT:
            return 0, json.dumps(_counter_rows())
        return 0, json.dumps(_event_rows())

    return DiagnosticsService(run=run)


# ---------- service ----------


def test_disk_health_parses_powershell_output() -> None:
    disks = _service().disk_health()
    assert len(disks) == 2
    ssd = disks[0]
    assert ssd.name == "Samsung SSD 970 EVO Plus 1TB"
    assert ssd.media == "SSD"
    assert ssd.size_bytes == 1000204886016
    assert ssd.health == "healthy"
    assert ssd.temperature_c == 38
    assert ssd.wear_percent == 3
    assert ssd.power_on_hours == 1234
    assert ssd.read_errors == 0
    assert ssd.write_errors == 0
    assert ssd.serial == "S6B0NL0T"


def test_disk_health_zero_values_become_unknown() -> None:
    hdd = _service().disk_health()[1]
    assert hdd.health == "warning"
    assert hdd.temperature_c is None  # 0°C is a "not reported" sentinel
    assert hdd.power_on_hours is None
    assert hdd.wear_percent is None


def test_disk_health_without_reliability_counters() -> None:
    def run(args, timeout):
        script = args[-1]
        if script == DISK_LIST_SCRIPT:
            return 0, json.dumps(_disk_rows())
        return 0, ""

    disks = DiagnosticsService(run=run).disk_health()
    assert len(disks) == 2
    assert all(d.temperature_c is None for d in disks)
    assert all(d.wear_percent is None for d in disks)


def test_events_parse_single_object() -> None:
    payload = json.dumps(_event_rows()[0])
    events = parse_events(payload)
    assert len(events) == 1
    assert events[0].level == 2
    assert events[0].level_name == "error"
    assert events[0].event_id == 7023
    assert events[0].source == "Service Control Manager"


def test_events_parse_empty_and_garbage() -> None:
    assert parse_events("") == []
    assert parse_events("   \n") == []
    assert parse_events("not json at all") == []


def test_events_level_names_mapped() -> None:
    events = parse_events(json.dumps([
        {"Level": 1, "Message": "a"},
        {"Level": 3, "Message": "b"},
        {"Level": 9, "Message": "c"},
    ]))
    assert [e.level_name for e in events] == ["critical", "warning", ""]


def test_events_message_is_collapsed_and_truncated() -> None:
    long_text = "line one\n\tline two   " + "x" * 600
    events = parse_events(json.dumps([{"Level": 2, "Message": long_text}]))
    message = events[0].message
    assert "\n" not in message and "\t" not in message
    assert message.endswith("…")
    assert len(message) <= 400


def test_events_script_uses_requested_log_and_levels() -> None:
    captured: dict[str, str] = {}

    def run(args, timeout):
        captured["script"] = args[-1]
        return 0, json.dumps(_event_rows())

    DiagnosticsService(run=run).events("Application", (1, 2, 3), limit=5)
    script = captured["script"]
    assert "LogName='Application'" in script
    assert "Level=1,2,3" in script
    assert "-MaxEvents 5" in script


def test_events_falls_back_to_default_log() -> None:
    captured: dict[str, str] = {}

    def run(args, timeout):
        captured["script"] = args[-1]
        return 0, ""

    DiagnosticsService(run=run).events("BogusLog")
    assert "LogName='System'" in captured["script"]


def test_report_collects_errors_without_raising() -> None:
    report = _service(fail=True).report()
    assert report.disks == ()
    assert report.events == ()
    assert len(report.errors) == 3  # Drives + Reliability + Events
    assert all("exit" in e for e in report.errors)


# ---------- UI ----------


class FakeDiagnosticsService:
    def __init__(self, report: DiagnosticsReport | None = None, fail: bool = False) -> None:
        self._report = report or _service().report()
        self._fail = fail
        self.calls = 0
        self.last_args: tuple[str, tuple[int, ...]] | None = None

    def report(self, log_name: str = "System", levels=(1, 2)) -> DiagnosticsReport:
        self.calls += 1
        self.last_args = (log_name, tuple(levels))
        if self._fail:
            raise RuntimeError("no powershell")
        return self._report


def test_page_registered_in_nav(qapp) -> None:
    assert "diagnostics" in {key for key, _ in NAV_ITEMS}
    window = MainWindow()
    assert isinstance(window.page("diagnostics"), DiagnosticsPage)
    window.close()


def test_page_renders_report(qapp) -> None:
    service = FakeDiagnosticsService()
    page = DiagnosticsPage(service=service)
    page.start_load()
    assert _wait_until(qapp, lambda: page.disk_table.rowCount() == 2)
    assert service.calls == 1
    assert page.disk_table.item(0, 0).text() == "Samsung SSD 970 EVO Plus 1TB"
    assert page.disk_table.item(0, 1).text() == "SSD"
    assert page.disk_table.item(0, 3).text() == "38°C"
    assert page.disk_table.item(0, 4).text() == "3%"
    assert page.disk_table.item(0, 6).text() == "Healthy"
    assert page.disk_table.item(1, 6).text() == "Warning"
    assert page.events_table.rowCount() == 2
    assert page.events_table.item(0, 1).text() == "Error"
    assert page.events_table.item(1, 1).text() == "Critical"
    assert page.events_table.item(0, 2).text() == "Service Control Manager"
    assert page.events_table.item(0, 3).text() == "7023"
    assert "loaded" in page.status_label.text().lower()


def test_page_passes_selected_filters(qapp) -> None:
    service = FakeDiagnosticsService()
    page = DiagnosticsPage(service=service)
    page.log_combo.setCurrentIndex(1)  # Application
    page.level_combo.setCurrentIndex(2)  # all
    page.start_load()
    assert _wait_until(qapp, lambda: page.disk_table.rowCount() == 2)
    assert service.last_args == ("Application", (1, 2, 3, 4))


def test_page_busy_disables_controls(qapp) -> None:
    page = DiagnosticsPage(service=FakeDiagnosticsService())
    page.start_load()
    assert not page.refresh_button.isEnabled()
    assert not page.events_button.isEnabled()
    assert not page.log_combo.isEnabled()
    assert _wait_until(qapp, lambda: page.disk_table.rowCount() == 2)
    assert page.refresh_button.isEnabled()
    assert page.log_combo.isEnabled()


def test_page_reports_failure(qapp) -> None:
    page = DiagnosticsPage(service=FakeDiagnosticsService(fail=True))
    page.start_load()
    assert _wait_until(qapp, lambda: "Failed" in page.status_label.text())
    assert page.disk_table.rowCount() == 0
    assert page.refresh_button.isEnabled()


def test_page_marks_warnings(qapp) -> None:
    report = _service(fail=True).report()
    page = DiagnosticsPage(service=FakeDiagnosticsService(report=report))
    page.start_load()
    assert _wait_until(qapp, lambda: "warning" in page.status_label.text().lower())


def test_retranslate_updates_headers_and_combos(qapp) -> None:
    from app.i18n import I18nService, tr

    page = DiagnosticsPage(service=FakeDiagnosticsService())
    page.start_load()
    assert _wait_until(qapp, lambda: page.disk_table.rowCount() == 2)
    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert page.disk_table.horizontalHeaderItem(0).text() == tr("diag_col_name")
        assert page.log_combo.itemText(0) == tr("diag_log_system")
        assert page.disk_table.item(0, 6).text() == tr("diag_health_healthy")
    finally:
        I18nService.instance().set_language("EN", emit=False)
