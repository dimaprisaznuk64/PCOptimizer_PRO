from __future__ import annotations

import time
from datetime import datetime

from app.benchmarks.hardware import DEFAULT_TYPES, HardwareBenchmarkReport, HardwareBenchmarkService
from app.benchmarks.history import HistoryEntry
from app.benchmarks.service import BenchmarkResult, BenchmarkType
from app.hardware import (
    BoardInfo,
    CpuInfo,
    DiskInfo,
    GpuInfo,
    HardwareReport,
    MemoryInfo,
    SystemInfo,
)
from app.i18n import tr
from app.i18n.service import I18nService
from app.reports.system import REDACTED
from app.ui.hardware_benchmark import BASELINE_COLUMN_KEYS, COLUMN_KEYS, HardwareBenchmarkPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _result(metric: str, value: float, unit: str, btype: BenchmarkType = BenchmarkType.CPU) -> BenchmarkResult:
    return BenchmarkResult(
        type=btype,
        metric=metric,
        value=value,
        min_value=value,
        max_value=value,
        unit=unit,
        duration_ms=4,
        runs=1,
        detail="fake",
    )


def _hardware(errors: tuple[str, ...] = ()) -> HardwareReport:
    return HardwareReport(
        system=SystemInfo(manufacturer="LENOVO", model="82RF", os_name="Windows 11", hostname="TEST-PC"),
        cpu=CpuInfo(name="Ryzen 7 5800H", physical_cores=8, logical_cores=16),
        gpus=(GpuInfo(name="RTX 5060"),),
        memory=MemoryInfo(total_bytes=16 * 1024**3, slots_used=1, slots_total=2, speed_mhz=3200),
        board=BoardInfo(manufacturer="LENOVO", product="82K2", serial="BOARD-SERIAL-42"),
        disks=(DiskInfo(model="Samsung SSD 990", media="SSD", serial="DISK-SERIAL-99"),),
        errors=errors,
    )


class FakeHardwareService:
    def __init__(self, report: HardwareReport | None = None, *, fail: bool = False) -> None:
        self._report = report or _hardware()
        self._fail = fail
        self.calls = 0

    def report(self) -> HardwareReport:
        self.calls += 1
        if self._fail:
            raise RuntimeError("no wmi")
        return self._report


class FakeBenchmarkService:
    def __init__(self, *, fail: bool = False, fail_types: tuple[BenchmarkType, ...] = ()) -> None:
        self._fail = fail
        self._fail_types = set(fail_types)
        self.calls: list[BenchmarkType] = []

    def run(self, btype: BenchmarkType, *, disk_dir=None) -> list[BenchmarkResult]:
        self.calls.append(btype)
        if self._fail or btype in self._fail_types:
            raise RuntimeError(f"boom {btype.name}")
        if btype is BenchmarkType.CPU:
            return [_result("cpu_single", 100.0, "MB/s", btype)]
        if btype is BenchmarkType.RAM:
            return [_result("ram_copy", 8.0, "GB/s", btype)]
        if btype is BenchmarkType.DISK:
            return [_result("disk_write", 200.0, "MB/s", btype)]
        return []


class FixedBenchmarkService:
    def __init__(self, results: list[BenchmarkResult]) -> None:
        self.results = results

    def run(self, btype: BenchmarkType, *, disk_dir=None) -> list[BenchmarkResult]:
        return self.results


class FailingService:
    def run(self) -> HardwareBenchmarkReport:
        raise RuntimeError("boom")


class FakeHistory:
    def __init__(self) -> None:
        self.by_metric: dict[str, list[HistoryEntry]] = {}
        self.baselines: dict[str, float] = {}
        self.record_calls = 0

    def record(self, results, *, baseline: bool = False) -> list[HistoryEntry]:
        self.record_calls += 1
        when = f"2026-01-0{self.record_calls}T00:00:00"
        fresh: list[HistoryEntry] = []
        for result in results:
            entry = HistoryEntry(
                when=when,
                metric=result.metric,
                value=float(result.value),
                unit=result.unit,
                detail=result.detail,
                baseline=baseline,
            )
            self.by_metric.setdefault(result.metric, []).append(entry)
            if baseline:
                self.baselines[result.metric] = float(result.value)
            fresh.append(entry)
        return fresh

    def latest_of(self, metric: str) -> HistoryEntry | None:
        items = self.by_metric.get(metric, ())
        return items[-1] if items else None

    def baseline_of(self, metric: str) -> float | None:
        if metric in self.baselines:
            return self.baselines[metric]
        items = self.by_metric.get(metric, ())
        return items[0].value if items else None

    def delta_pct(self, metric: str, value: float) -> float | None:
        base = self.baseline_of(metric)
        return None if not base else (value - base) / base * 100.0

    def set_baseline(self) -> int:
        for metric, items in self.by_metric.items():
            if items:
                self.baselines[metric] = items[-1].value
        return len(self.baselines)


def _service(
    tmp_path,
    *,
    hardware: FakeHardwareService | None = None,
    benchmark: FakeBenchmarkService | FixedBenchmarkService | None = None,
    history: FakeHistory | None = None,
) -> HardwareBenchmarkService:
    return HardwareBenchmarkService(
        hardware=hardware or FakeHardwareService(),
        benchmark=benchmark or FakeBenchmarkService(),
        history=history or FakeHistory(),
        now=lambda: 1_700_000_000.0,
        disk_dir=tmp_path,
    )


def _page(tmp_path, **kwargs) -> HardwareBenchmarkPage:
    return HardwareBenchmarkPage(service=_service(tmp_path, **kwargs))


def test_run_returns_real_results_and_hardware(tmp_path) -> None:
    hardware = FakeHardwareService()
    benchmark = FakeBenchmarkService()
    history = FakeHistory()
    report = _service(tmp_path, hardware=hardware, benchmark=benchmark, history=history).run()

    assert isinstance(report, HardwareBenchmarkReport)
    assert [r.metric for r in report.results] == ["cpu_single", "ram_copy", "disk_write"]
    assert benchmark.calls == list(DEFAULT_TYPES)
    assert hardware.calls == 1
    assert report.hardware.system.model == "82RF"
    assert report.errors == ()
    assert history.record_calls == 1
    assert datetime.fromisoformat(report.generated).year == 2023


def test_run_captures_hardware_failure_without_faking_values(tmp_path) -> None:
    service = _service(tmp_path, hardware=FakeHardwareService(fail=True))
    report = service.run()
    assert report.hardware == HardwareReport()
    assert any(error.startswith("hardware:") for error in report.errors)
    assert len(report.results) == 3


def test_run_captures_benchmark_section_errors(tmp_path) -> None:
    service = _service(tmp_path, benchmark=FakeBenchmarkService(fail_types=(BenchmarkType.RAM,)))
    report = service.run()
    assert [r.metric for r in report.results] == ["cpu_single", "disk_write"]
    assert any("RAM" in error for error in report.errors)


def test_run_propagates_hardware_warnings(tmp_path) -> None:
    service = _service(tmp_path, hardware=FakeHardwareService(_hardware(("BIOS: unavailable",))))
    assert service.run().errors == ("BIOS: unavailable",)


def test_service_never_mutates_caller_data(tmp_path) -> None:
    types = [BenchmarkType.CPU]
    results = [_result("cpu_single", 100.0, "MB/s")]
    service = _service(tmp_path, benchmark=FixedBenchmarkService(results))
    report = service.run(types)

    assert types == [BenchmarkType.CPU]
    assert results == [_result("cpu_single", 100.0, "MB/s")]
    assert isinstance(report.results, tuple)
    assert report.results == tuple(results)
    service.summary_rows(report)
    service.baseline_rows(report)
    assert report.errors == ()


def test_summary_rows_cover_hardware_and_results(tmp_path) -> None:
    service = _service(tmp_path)
    rows = dict(service.summary_rows(service.run()))
    assert "82RF" in rows["hwb_row_system"]
    assert "Ryzen 7 5800H" in rows["hwb_row_cpu"]
    assert "16.0 GB" in rows["hwb_row_memory"]
    assert "RTX 5060" in rows["hwb_row_gpu"]
    assert "Samsung SSD 990" in rows["hwb_row_storage"]
    assert rows["hwb_row_benchmarks"] == "3"
    assert "hwb_row_errors" not in rows


def test_summary_rows_report_errors(tmp_path) -> None:
    service = _service(tmp_path, hardware=FakeHardwareService(_hardware(("BIOS: missing",))))
    rows = dict(service.summary_rows(service.run()))
    assert "BIOS: missing" in rows["hwb_row_errors"]


def test_baseline_rows_use_previous_before_record_and_delta(tmp_path) -> None:
    history = FakeHistory()
    history.record([_result("cpu_single", 80.0, "MB/s")])
    history.set_baseline()
    service = _service(tmp_path, history=history)
    report = service.run()

    rows = service.baseline_rows(report)
    assert len(rows) == 3
    assert rows[0].metric == "cpu_single"
    assert rows[0].value == 100.0
    assert rows[0].previous == 80.0
    assert report.previous[0].metric == "cpu_single"
    assert report.previous[0].value == 80.0
    assert rows[0].delta_pct is not None and round(rows[0].delta_pct, 3) == 25.0
    assert rows[1].previous is None
    assert rows[1].delta_pct == 0.0


def test_export_text_contains_hardware_results_and_errors(tmp_path) -> None:
    service = _service(tmp_path, hardware=FakeHardwareService(_hardware(("BIOS: missing",))))
    report = service.run()
    json_text = service.export_text(report, "json")
    csv_text = service.export_text(report, "csv")
    assert "cpu_single" in json_text and "82RF" in json_text and "BIOS: missing" in json_text
    assert "cpu_single" in csv_text and "BIOS: missing" in csv_text
    assert "Previous" in csv_text


def test_export_record_redacts_identifiers_by_default(tmp_path) -> None:
    service = _service(tmp_path)
    record = service.export_record(service.run())

    assert record["hardware"]["system"]["hostname"] == REDACTED
    assert record["hardware"]["board"]["serial"] == REDACTED
    assert record["hardware"]["disks"][0]["serial"] == REDACTED
    json_text = service.export_text(service.run(), "json")
    assert "TEST-PC" not in json_text
    assert "BOARD-SERIAL-42" not in json_text
    assert "DISK-SERIAL-99" not in json_text


def test_export_opt_in_keeps_identifiers(tmp_path) -> None:
    service = _service(tmp_path)
    report = service.run()

    json_text = service.export_text(report, "json", include_identifiers=True)
    assert "TEST-PC" in json_text
    assert "BOARD-SERIAL-42" in json_text
    assert "DISK-SERIAL-99" in json_text
    assert REDACTED not in json_text


def test_page_renders_report_via_task(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    assert page.results_table.rowCount() == 0
    assert page.status_label.text() == tr("hwb_idle")

    page.start_run()
    assert _wait_until(qapp, lambda: page.results_table.rowCount() == 3)
    assert page.baseline_table.rowCount() == 3
    assert "82RF" in page.summary_card._rows[tr("hwb_row_system")].text()
    assert page.results_table.item(0, 0).text() == tr("bench_metric_cpu_single")
    assert page.status_label.text() == tr("hwb_done", count=3)
    assert page._task is None
    assert page.run_button.isEnabled()


def test_task_uses_com_and_is_cleared_before_delete_later(qapp, tmp_path, monkeypatch) -> None:
    import app.ui.hardware_benchmark as module

    real_task = module.Task
    seen: dict[str, object] = {}
    holder: dict[str, HardwareBenchmarkPage] = {}

    class SpyTask(real_task):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            seen["com"] = kwargs.get("com")

        def deleteLater(self) -> None:
            seen["task_at_delete"] = holder["page"]._task
            super().deleteLater()

    monkeypatch.setattr(module, "Task", SpyTask)
    page = _page(tmp_path)
    holder["page"] = page

    page.start_run()
    assert _wait_until(qapp, lambda: "task_at_delete" in seen)
    assert seen["com"] is True
    assert seen["task_at_delete"] is None


def test_page_busy_disables_controls(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    page.start_run()
    assert not page.run_button.isEnabled()
    assert not page.baseline_button.isEnabled()
    assert not page.export_button.isEnabled()
    assert _wait_until(qapp, lambda: page.results_table.rowCount() == 3)
    assert page.run_button.isEnabled()
    assert page.baseline_button.isEnabled()
    assert page.export_button.isEnabled()


def test_page_shows_previous_value_before_current(qapp, tmp_path) -> None:
    history = FakeHistory()
    history.record([_result("cpu_single", 80.0, "MB/s")])
    page = _page(tmp_path, history=history)
    page.start_run()
    assert _wait_until(qapp, lambda: page.baseline_table.rowCount() == 3)

    assert page.baseline_table.item(0, 1).text() == "100.0"
    assert page.baseline_table.item(0, 3).text() == "80.0"


def test_page_set_baseline(qapp, tmp_path) -> None:
    history = FakeHistory()
    page = _page(tmp_path, history=history)
    page.start_run()
    assert _wait_until(qapp, lambda: page.baseline_table.rowCount() == 3)

    page.set_baseline()
    assert set(history.baselines) == {"cpu_single", "ram_copy", "disk_write"}
    assert page.status_label.text() == tr("hwb_baseline_set", count=3)
    assert page.baseline_table.item(0, 5).text() == "+0.0%"


def test_page_export_writes_file(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    page.start_run()
    assert _wait_until(qapp, lambda: page.results_table.rowCount() == 3)
    target = tmp_path / "hardware_benchmark.json"
    page._ask_save_path = lambda _default: str(target)
    page.export_report()

    text = target.read_text(encoding="utf-8")
    assert target.exists()
    assert "cpu_single" in text
    assert REDACTED in text
    assert "TEST-PC" not in text
    assert tr("exp_done", path=str(target)) == page.status_label.text()


def test_page_export_without_report(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    page.export_report()
    assert page.status_label.text() == tr("exp_nothing")


def test_page_reports_failure(qapp) -> None:
    page = HardwareBenchmarkPage(service=FailingService())
    page.start_run()
    prefix = tr("hwb_failed").split("{")[0]
    assert _wait_until(qapp, lambda: prefix in page.status_label.text())
    assert page.results_table.rowCount() == 0
    assert page.baseline_table.rowCount() == 0
    assert page.run_button.isEnabled()
    assert page._task is None


def test_page_retranslate_rerenders_cached_report(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    page.start_run()
    assert _wait_until(qapp, lambda: page.results_table.rowCount() == 3)

    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert page._title.text() == tr("hwb_title")
        assert [page.results_table.horizontalHeaderItem(i).text() for i in range(len(COLUMN_KEYS))] == [
            tr(key) for key in COLUMN_KEYS
        ]
        assert [page.baseline_table.horizontalHeaderItem(i).text() for i in range(len(BASELINE_COLUMN_KEYS))] == [
            tr(key) for key in BASELINE_COLUMN_KEYS
        ]
        assert page.results_table.rowCount() == 3
        assert tr("hwb_row_cpu") in page.summary_card._rows
    finally:
        I18nService.instance().set_language("EN", emit=False)
