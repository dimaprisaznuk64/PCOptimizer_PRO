from __future__ import annotations

import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from app.cleaner import CleanTarget
from app.cleaner.service import RECYCLE_BIN_ID, CleanOutcome, ScanResult
from app.disk import DriveUsage
from app.health import (
    SEVERITY_PENALTY,
    Finding,
    FixReport,
    HealthError,
    HealthReport,
    HealthService,
    grade_for,
    score_from,
)
from app.i18n import tr
from app.optimizer.service import ApplyReport, OptimizerState
from app.sensors import Snapshot
from app.sensors.types import CpuStat, GpuStat, MemoryStat, ThermalStat
from app.startup.service import StartupItem
from app.ui.health import HealthPage, action_for, localize_finding


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _cpu(percent=10.0) -> CpuStat:
    return CpuStat(percent=percent, per_core=(percent,), physical_cores=4, logical_cores=8)


def _memory(percent=40.0) -> MemoryStat:
    return MemoryStat(
        total=1000, used=int(percent * 10), available=1000 - int(percent * 10),
        percent=percent, swap_total=0, swap_used=0, swap_percent=0.0,
    )


def _thermal(temp) -> ThermalStat:
    return ThermalStat(source="test", temperatures=(("CPU", temp),))


class FakeSensors:
    def __init__(self, cpu_percent=10.0, mem_percent=40.0, temp=55.0, gpus=()) -> None:
        self._snapshot = Snapshot(
            ts=0.0, cpu=_cpu(cpu_percent), memory=_memory(mem_percent),
            thermal=None if temp is None else _thermal(temp), gpus=tuple(gpus),
        )

    def snapshot(self) -> Snapshot:
        return self._snapshot


def _gpu(utilization=10.0, temperature=50.0) -> GpuStat:
    return GpuStat(
        index=0, name="Test GPU", utilization=utilization,
        memory_used=1, memory_total=2, temperature=temperature,
    )


class FakeDisks:
    def __init__(self, percents=(50.0,)) -> None:
        self._drives = [
            DriveUsage(mount=f"{chr(67 + i)}:\\", total=1000, used=int(p * 10), free=0, percent=p)
            for i, p in enumerate(percents)
        ]

    def list_drives(self):
        return list(self._drives)


class FakeStartup:
    def __init__(self, heavy=0) -> None:
        self._items = [
            StartupItem(
                id=f"h{i}", name=f"app{i}", source="HKCU", kind="registry",
                command="x", location="Run", enabled=True, impact="High", impact_reason="",
            )
            for i in range(heavy)
        ]

    def list_items(self):
        return list(self._items), []


class FakeOptimizer:
    def __init__(self, power_name="Balanced") -> None:
        self._state = OptimizerState(
            power_guid="guid", power_name=power_name, game_mode=True, hags=True,
            visual_fx=0, visual_name="Custom", is_admin=True,
        )

    def state(self):
        return self._state


class FakeCleaner:
    def __init__(self, sizes=None, error_targets=()) -> None:
        self.sizes = sizes or {}
        self.error_targets = set(error_targets)
        self.scanned: list[str] = []
        self.cleaned: list[str] = []

    def scan(self, target: CleanTarget) -> ScanResult:
        self.scanned.append(target.id)
        if target.id in self.error_targets:
            return ScanResult(target.id, 0, 0, error="boom")
        return ScanResult(target.id, 3, self.sizes.get(target.id, 0))

    def clean(self, target: CleanTarget, known_bytes: int = 0) -> CleanOutcome:
        self.cleaned.append(target.id)
        size = self.sizes.get(target.id, 0)
        return CleanOutcome(target.id, freed_bytes=size, files_deleted=3, files_skipped=0)


def _service(sensors=None, disks=None, startup=None, optimizer=None, cleaner=None) -> HealthService:
    return HealthService(
        sensors=sensors or FakeSensors(),
        disks=disks or FakeDisks(),
        startup=startup or FakeStartup(),
        optimizer=optimizer or FakeOptimizer(),
        cleaner=cleaner or FakeCleaner(),
    )


# ---------- scoring ----------


def test_score_from_penalties() -> None:
    findings = [
        Finding("a", "X", "critical", "t", "d"),
        Finding("b", "X", "warning", "t", "d"),
        Finding("c", "X", "ok", "t", "d"),
    ]
    assert score_from(findings) == 100 - 30 - 10
    assert score_from([]) == 100
    assert score_from([Finding("a", "X", "critical", "t", "d")] * 4) == 0


@pytest.mark.parametrize(
    "score,expected",
    [(100, "Excellent"), (95, "Excellent"), (94, "Good"), (75, "Good"),
     (74, "Fair"), (50, "Fair"), (49, "Poor"), (0, "Poor")],
)
def test_grade_for(score, expected) -> None:
    assert grade_for(score) == expected


def test_any_warning_no_longer_excellent() -> None:
    # A warning costs 10 points -> 90 must not read as "Excellent" any more.
    findings = [Finding("a", "X", "warning", "t", "d")]
    assert grade_for(score_from(findings)) == "Good"


# ---------- scan ----------


def test_scan_healthy_machine() -> None:
    report = _service().scan()
    assert isinstance(report, HealthReport)
    assert report.score == 100
    assert report.grade == "Excellent"
    assert report.fixable_count == 0
    severities = {f.id: f.severity for f in report.findings}
    assert severities["memory"] == "ok"
    assert severities["thermal"] == "ok"
    assert "junk" in severities


def test_scan_flags_memory_and_disk_and_temp() -> None:
    report = _service(
        sensors=FakeSensors(cpu_percent=95.0, mem_percent=97.0, temp=97.0),
        disks=FakeDisks(percents=(98.0,)),
    ).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["memory"].severity == "critical"
    assert by_id["thermal"].severity == "critical"
    assert by_id["disk:C:\\"].severity == "critical"
    assert by_id["cpu_load"].severity == "info"
    assert report.score == 100 - 30 - 30 - 30 - 3


def test_scan_flags_gpu_temp_and_load() -> None:
    # The reviewer's real case: GPU 86 C + 91% load must not score 90/Excellent.
    report = _service(sensors=FakeSensors(gpus=(_gpu(utilization=91.0, temperature=86.0),))).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["thermal_gpu"].severity == "warning"
    assert by_id["gpu_load"].severity == "info"
    assert report.score == 100 - 10 - 3
    assert report.grade == "Good"


def test_scan_gpu_critical_temperature() -> None:
    report = _service(sensors=FakeSensors(gpus=(_gpu(utilization=50.0, temperature=92.0),))).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["thermal_gpu"].severity == "critical"
    # Cool GPU + light load contributes nothing.
    report = _service(sensors=FakeSensors(gpus=(_gpu(utilization=40.0, temperature=60.0),))).scan()
    ids = {f.id for f in report.findings}
    assert "thermal_gpu" not in ids
    assert "gpu_load" not in ids
    assert report.score == 100


def test_scan_localizes_gpu_findings() -> None:
    from app.ui.health import localize_finding

    report = _service(sensors=FakeSensors(gpus=(_gpu(utilization=95.0, temperature=86.0),))).scan()
    by_id = {f.id: f for f in report.findings}
    _cat, title, detail = localize_finding(by_id["thermal_gpu"])
    assert title == "High GPU temperature"
    assert "86°C" in detail and "86C" not in detail
    _cat, title, detail = localize_finding(by_id["gpu_load"])
    assert title == "GPU load is high right now"
    assert "95%" in detail


def test_scan_startup_heavy_counts() -> None:
    report = _service(startup=FakeStartup(heavy=8)).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["startup"].severity == "warning"

    report = _service(startup=FakeStartup(heavy=5)).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["startup"].severity == "info"

    report = _service(startup=FakeStartup(heavy=1)).scan()
    assert "startup" not in {f.id for f in report.findings}


def test_scan_power_saver_hint() -> None:
    report = _service(optimizer=FakeOptimizer(power_name="Power saver")).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["power"].severity == "info"

    report = _service(optimizer=FakeOptimizer(power_name="Balanced")).scan()
    assert "power" not in {f.id for f in report.findings}


def test_scan_junk_levels_and_fixable() -> None:
    gb = 1024**3
    report = _service(cleaner=FakeCleaner(sizes={"user_temp": 6 * gb})).scan()
    junk = next(f for f in report.findings if f.id == "junk")
    assert junk.severity == "critical"
    assert junk.fixable is True
    assert report.junk_bytes >= 6 * gb
    assert report.fixable_count == 1
    assert report.score < 100

    report = _service(cleaner=FakeCleaner(sizes={"user_temp": 2 * gb})).scan()
    junk = next(f for f in report.findings if f.id == "junk")
    assert junk.severity == "warning"
    assert report.fixable_count == 1


def test_scan_recycle_bin_excluded_from_junk() -> None:
    gb = 1024**3
    cleaner = FakeCleaner(sizes={"user_temp": 1 * gb, RECYCLE_BIN_ID: 50 * gb})
    report = _service(cleaner=cleaner).scan()
    assert report.junk_bytes == 1 * gb
    assert RECYCLE_BIN_ID not in cleaner.scanned


def test_scan_collects_errors_without_crashing() -> None:
    class Boom:
        def snapshot(self):
            raise RuntimeError("no sensors")

    report = _service(sensors=Boom(), cleaner=FakeCleaner(error_targets=("user_temp",))).scan()
    assert any("sensors:" in e for e in report.errors)
    assert report.score <= 100


def test_scan_flags_missing_sensor_data() -> None:
    class EmptySensors:
        def snapshot(self):
            return Snapshot(ts=0.0, cpu=None, memory=None, thermal=None)

    report = _service(sensors=EmptySensors()).scan()
    by_id = {f.id: f for f in report.findings}
    assert by_id["memory_missing"].severity == "info"
    assert by_id["thermal_missing"].severity == "info"
    # Missing data must not silently yield a perfect score.
    assert report.score == 100 - SEVERITY_PENALTY["info"] * 2


# ---------- fix ----------


def test_fix_all_skips_recycle_bin_and_reports() -> None:
    gb = 1024**3
    cleaner = FakeCleaner(sizes={"user_temp": 2 * gb})
    report = _service(cleaner=cleaner).fix_all()
    assert isinstance(report, FixReport)
    assert RECYCLE_BIN_ID not in cleaner.cleaned
    assert "user_temp" in cleaner.cleaned
    assert report.reclaimed_bytes >= 2 * gb
    assert report.files_deleted > 0
    assert report.applied


def test_fix_all_include_recycle_bin() -> None:
    gb = 1024**3
    cleaner = FakeCleaner(sizes={RECYCLE_BIN_ID: 5 * gb})
    report = _service(cleaner=cleaner).fix_all(include_recycle_bin=True)
    assert RECYCLE_BIN_ID in cleaner.cleaned
    assert report.reclaimed_bytes >= 5 * gb


def test_fix_all_counts_partial_cleanup() -> None:
    # A partial clean frees bytes but leaves some files locked: the reclaimed
    # amount must still be counted and the user told it was incomplete.
    class PartialCleaner:
        def __init__(self) -> None:
            self.cleaned: list[str] = []

        def scan(self, target):
            return ScanResult(target.id, 3, 2048)

        def clean(self, target, known_bytes=0):
            self.cleaned.append(target.id)
            return CleanOutcome(
                target.id, freed_bytes=512, files_deleted=1, files_skipped=1,
                error=None, partial=True,
            )

    cleaner = PartialCleaner()
    report = _service(cleaner=cleaner).fix_all()
    assert report.reclaimed_bytes > 0
    assert report.files_deleted > 0
    assert report.applied
    assert any("partially cleaned" in e for e in report.errors)


# ---------- UI ----------


class UiFakeHealth(HealthService):
    def __init__(self, sizes=None) -> None:
        self._fake_cleaner = FakeCleaner(sizes=sizes)
        super().__init__(
            sensors=FakeSensors(mem_percent=97.0),
            disks=FakeDisks(percents=(98.0,)),
            startup=FakeStartup(heavy=8),
            optimizer=FakeOptimizer(),
            cleaner=self._fake_cleaner,
        )
        self.scan_calls = 0
        self.fix_calls = 0
        self.fix_one_calls = 0

    def scan(self, *, include_junk: bool = True) -> HealthReport:
        self.scan_calls += 1
        return super().scan(include_junk=include_junk)

    def fix_all(self, *, include_recycle_bin: bool = False) -> FixReport:
        self.fix_calls += 1
        return super().fix_all(include_recycle_bin=include_recycle_bin)

    def fix_finding(self, finding: Finding) -> FixReport:
        self.fix_one_calls += 1
        return super().fix_finding(finding)


def _healthy_service() -> HealthService:
    return HealthService(
        sensors=FakeSensors(),
        disks=FakeDisks(percents=(40.0,)),
        startup=FakeStartup(),
        optimizer=FakeOptimizer(),
        cleaner=FakeCleaner(),
    )


def test_health_page_scan_renders(qapp) -> None:
    service = UiFakeHealth()
    page = HealthPage(service=service)
    assert page.score_label.text() == "—"
    assert not page.fix_button.isEnabled()

    page.start_scan()
    assert not page.scan_button.isEnabled()
    assert _wait_until(qapp, lambda: service.scan_calls >= 1 and page.findings_table.rowCount() > 0)
    assert page.score_label.text() != "—"
    assert page.grade_label.text()
    assert page.scan_button.isEnabled()
    assert page.findings_table.rowCount() == len(page._report.findings)


def test_health_page_fix_disabled_when_nothing_fixable(qapp) -> None:
    page = HealthPage(service=UiFakeHealth())
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)
    assert page.fix_button.isEnabled() is False


def test_health_page_fix_flow_rescans(qapp) -> None:
    gb = 1024**3
    service = UiFakeHealth(sizes={"user_temp": 3 * gb})
    page = HealthPage(service=service)
    page._ask_confirm = lambda *a, **k: True
    page.start_fix()  # no report yet -> no-op
    assert service.fix_calls == 0

    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None and page.fix_button.isEnabled())
    page.start_fix()
    assert _wait_until(qapp, lambda: service.fix_calls >= 1 and service.scan_calls >= 2)
    assert "user_temp" in service._fake_cleaner.cleaned
    assert page.scan_button.isEnabled()


# ---------- per-finding fix ----------


def test_fix_finding_junk_cleans_only_junk() -> None:
    gb = 1024**3
    cleaner = FakeCleaner(sizes={"user_temp": 2 * gb})
    service = _service(cleaner=cleaner)
    finding = Finding("junk", "Cleanup", "warning", "Temporary files found", "d", fixable=True)
    report = service.fix_finding(finding)
    assert "user_temp" in cleaner.cleaned
    assert RECYCLE_BIN_ID not in cleaner.cleaned
    assert report.reclaimed_bytes >= 2 * gb


def test_fix_finding_power_uses_backup_without_restore_point() -> None:
    calls = []

    class Opt(FakeOptimizer):
        def apply_profile(self, profile, *, with_restore_point: bool = True):
            calls.append((profile, with_restore_point))
            return ApplyReport(
                applied=("power plan → Balanced",), errors=(),
                restore_point=None, restore_status=None,
            )

    report = _service(optimizer=Opt(power_name="Power saver")).fix_finding(
        Finding("power", "Power", "info", "Power saver plan is active", "d")
    )
    assert calls == [("BALANCED", False)]
    assert report.applied == ("power plan → Balanced",)
    assert report.errors == ()


def test_fix_finding_power_reports_errors() -> None:
    class Opt(FakeOptimizer):
        def apply_profile(self, profile, *, with_restore_point: bool = True):
            raise RuntimeError("no powercfg")

    report = _service(optimizer=Opt()).fix_finding(
        Finding("power", "Power", "info", "Power saver plan is active", "d")
    )
    assert report.applied == ()
    assert any("no powercfg" in e for e in report.errors)


class RecordingStartup(FakeStartup):
    def __init__(self, heavy=0, failing=()) -> None:
        super().__init__(heavy=heavy)
        self.disabled: list[str] = []
        self.failing = set(failing)

    def set_enabled(self, item, enabled: bool) -> None:
        if item.name in self.failing:
            raise RuntimeError("access denied")
        self.disabled.append(item.name)


def test_fix_finding_startup_disables_heavy_items() -> None:
    startup = RecordingStartup(heavy=5)
    report = _service(startup=startup).fix_finding(
        Finding("startup", "Startup", "warning", "5 heavy startup apps", "d")
    )
    assert startup.disabled == ["app0", "app1", "app2", "app3", "app4"]
    assert report.applied == ("app0", "app1", "app2", "app3", "app4")
    assert report.errors == ()


def test_fix_finding_startup_collects_failures() -> None:
    startup = RecordingStartup(heavy=3, failing={"app1"})
    report = _service(startup=startup).fix_finding(
        Finding("startup", "Startup", "warning", "3 heavy startup apps", "d")
    )
    assert report.applied == ("app0", "app2")
    assert any("app1" in e for e in report.errors)


def test_fix_finding_rejects_non_fixable() -> None:
    service = _service()
    with pytest.raises(HealthError):
        service.fix_finding(Finding("thermal", "Thermal", "warning", "High CPU temperature", "d"))
    with pytest.raises(HealthError):
        service.fix_finding(Finding("disk:C:", "Storage", "critical", "C: nearly full", "d"))


def test_action_for_maps_findings() -> None:
    assert action_for(Finding("junk", "Cleanup", "warning", "t", "d", fixable=True)) == ("fix", "")
    assert action_for(Finding("power", "Power", "info", "t", "d")) == ("fix", "")
    assert action_for(Finding("startup", "Startup", "warning", "t", "d")) == ("fix", "")
    assert action_for(Finding("disk:C:", "Storage", "critical", "t", "d")) == ("go", "cleaner")
    assert action_for(Finding("thermal", "Thermal", "warning", "t", "d")) == ("go", "monitor")
    assert action_for(Finding("thermal_missing", "Thermal", "info", "t", "d")) == ("go", "monitor")
    assert action_for(Finding("memory", "Memory", "ok", "t", "d")) == ("", "")
    assert action_for(Finding("mystery", "Other", "info", "t", "d")) == ("", "")


def _action_button(page, row: int):
    host = page.findings_table.cellWidget(row, 4)
    return None if host is None else host.findChild(QPushButton)


def _row_expectations(page) -> dict[str, tuple[str, str]]:
    """Localized issue text -> (kind, page) as produced by action_for()."""
    expected: dict[str, tuple[str, str]] = {}
    for finding in page._report.findings:
        title = localize_finding(finding)[1]
        expected[title] = action_for(finding)
    return expected


def _label_for(kind: str) -> str:
    return {"fix": tr("health_btn_fix"), "go": tr("health_btn_go")}.get(kind, "")


def test_health_page_shows_per_row_buttons(qapp) -> None:
    service = UiFakeHealth(sizes={"user_temp": 3 * 1024**3})
    page = HealthPage(service=service)
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    table = page.findings_table
    expected = _row_expectations(page)
    kinds = set()
    for row in range(table.rowCount()):
        issue = table.item(row, 2).text()
        kind, _page = expected[issue]
        button = _action_button(page, row)
        kinds.add(kind)
        if kind:
            assert button is not None and button.text() == _label_for(kind), issue
        else:
            assert button is None, issue
    # the report must exercise all three states: fix, go and no action
    assert {"fix", "go", ""} <= kinds | {""}


def _row_of_finding(page, finding_id: str) -> int:
    title = next(localize_finding(f)[1] for f in page._report.findings if f.id == finding_id)
    table = page.findings_table
    return next(r for r in range(table.rowCount()) if table.item(r, 2).text() == title)


def test_health_page_fix_button_starts_single_fix(qapp) -> None:
    gb = 1024**3
    service = UiFakeHealth(sizes={"user_temp": 3 * gb})
    page = HealthPage(service=service)
    page._ask_confirm = lambda *a, **k: True
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    _action_button(page, _row_of_finding(page, "junk")).click()
    assert _wait_until(qapp, lambda: service.fix_one_calls >= 1 and service.scan_calls >= 2)
    assert "user_temp" in service._fake_cleaner.cleaned


def test_health_page_fix_button_cancelled_does_nothing(qapp) -> None:
    service = UiFakeHealth(sizes={"user_temp": 3 * 1024**3})
    page = HealthPage(service=service)
    page._ask_confirm = lambda *a, **k: False
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    _action_button(page, _row_of_finding(page, "junk")).click()
    qapp.processEvents()
    assert service.fix_one_calls == 0
    assert service._fake_cleaner.cleaned == []


def test_health_page_go_button_emits_navigate(qapp) -> None:
    service = UiFakeHealth()
    page = HealthPage(service=service)
    targets: list[str] = []
    page.navigate.connect(targets.append)
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    expected = _row_expectations(page)
    row = next(
        r for r in range(page.findings_table.rowCount())
        if expected[page.findings_table.item(r, 2).text()][0] == "go"
    )
    _action_button(page, row).click()
    assert targets == [expected[page.findings_table.item(row, 2).text()][1]]


def test_health_page_healthy_rows_have_no_buttons(qapp) -> None:
    page = HealthPage(service=_healthy_service())
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)
    assert page.findings_table.rowCount() > 0
    for row in range(page.findings_table.rowCount()):
        assert _action_button(page, row) is None


def test_health_page_rerender_detaches_action_cells(qapp) -> None:
    service = UiFakeHealth(sizes={"user_temp": 3 * 1024**3})
    page = HealthPage(service=service)
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)
    unhealthy = page._report
    assert page._action_buttons

    healthy = _healthy_service().scan()
    page._render_report(healthy)
    qapp.processEvents()
    for row in range(page.findings_table.rowCount()):
        assert page.findings_table.cellWidget(row, 4) is None
        assert _action_button(page, row) is None

    page._render_report(unhealthy)
    qapp.processEvents()
    assert page._action_buttons
    expected = _row_expectations(page)
    for row in range(page.findings_table.rowCount()):
        issue = page.findings_table.item(row, 2).text()
        kind, _page = expected[issue]
        assert (_action_button(page, row) is not None) == bool(kind), issue
    assert all(cell.parent() is not None for cell in page._action_cells)


def test_health_page_busy_disables_row_buttons(qapp) -> None:
    service = UiFakeHealth(sizes={"user_temp": 3 * 1024**3})
    page = HealthPage(service=service)
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    page._set_busy(True)
    assert all(not b.isEnabled() for b in page._action_buttons)
    page._set_busy(False)
    assert all(b.isEnabled() for b in page._action_buttons)


def test_health_page_buttons_follow_rows_after_sort(qapp) -> None:
    service = UiFakeHealth(sizes={"user_temp": 3 * 1024**3})
    page = HealthPage(service=service)
    page.start_scan()
    assert _wait_until(qapp, lambda: page._report is not None)

    table = page.findings_table
    expected = _row_expectations(page)
    table.sortItems(1, Qt.SortOrder.AscendingOrder)  # severity column
    qapp.processEvents()
    seen = set()
    for row in range(table.rowCount()):
        issue = table.item(row, 2).text()
        kind, _page = expected[issue]
        seen.add(kind)
        widget = table.cellWidget(row, 4)
        if kind:
            assert widget is not None, issue
            labels = {b.text() for b in widget.findChildren(QPushButton)}
            assert labels == {_label_for(kind)}, issue
    assert "fix" in seen and "go" in seen
