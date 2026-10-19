from __future__ import annotations

import time

import pytest

from app.cleaner import CleanTarget
from app.cleaner.service import RECYCLE_BIN_ID, CleanOutcome, ScanResult
from app.disk import DriveUsage
from app.health import (
    SEVERITY_PENALTY,
    Finding,
    FixReport,
    HealthReport,
    HealthService,
    grade_for,
    score_from,
)
from app.optimizer.service import OptimizerState
from app.sensors import Snapshot
from app.sensors.types import CpuStat, GpuStat, MemoryStat, ThermalStat
from app.startup.service import StartupItem
from app.ui.health import HealthPage


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

    def scan(self, *, include_junk: bool = True) -> HealthReport:
        self.scan_calls += 1
        return super().scan(include_junk=include_junk)

    def fix_all(self, *, include_recycle_bin: bool = False) -> FixReport:
        self.fix_calls += 1
        return super().fix_all(include_recycle_bin=include_recycle_bin)


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
