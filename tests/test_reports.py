from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from app.benchmarks import BenchmarkHistory, BenchmarkResult, BenchmarkType, HistoryEntry
from app.health import Finding, HealthReport
from app.reports import (
    ReportError,
    export_health,
    export_history,
    format_for_path,
    health_to_csv,
    health_to_json,
    history_to_csv,
    history_to_json,
    timestamp_name,
    write_report,
)


def _health_report() -> HealthReport:
    findings = (
        Finding("memory", "Memory", "ok", "RAM usage healthy", "50% used", fixable=False),
        Finding("junk", "Cleanup", "warning", "Temporary files found", "1.2 GB across 2 locations", fixable=True),
    )
    return HealthReport(
        score=75,
        grade="Good",
        findings=findings,
        junk_bytes=1024**3,
        junk_targets=2,
        generated=datetime(2026, 10, 17, 12, 0, 0).timestamp(),
        errors=("cleanup warning",),
    )


def _hist_entries(now=lambda: 1000.0) -> list[HistoryEntry]:
    return [
        HistoryEntry("2026-10-17T12:00:00", "cpu_single", 150.0, "MB/s", "detail", baseline=False),
        HistoryEntry("2026-10-17T11:00:00", "ram_copy", 12.5, "GB/s", "", baseline=True),
    ]


def test_health_to_json_and_csv() -> None:
    report = _health_report()

    def localize(f: Finding) -> tuple[str, str, str]:
        return f"{f.category}_loc", f"{f.title}_loc", f"{f.detail}_loc"

    j = health_to_json(report, localize=localize)
    data = json.loads(j)
    assert data["score"] == 75
    assert data["findings"][0]["category"] == "Memory_loc"
    assert data["findings"][1]["fixable"] is True
    assert "cleanup warning" in data["errors"]

    csv_text = health_to_csv(report, localize=localize)
    assert "Category" in csv_text.splitlines()[0]
    assert "Memory_loc" in csv_text


def test_format_for_path_and_timestamp_name() -> None:
    assert format_for_path("r.csv") == "csv"
    assert format_for_path("R.JSON") == "json"
    assert format_for_path("noext") == "csv"

    ts = timestamp_name("health", "csv", now=datetime(2026, 10, 17, 12, 0, 0).timestamp())
    assert ts.startswith("health_20261017_120000.csv")


def test_history_export_json_and_csv(tmp_path) -> None:
    entries = _hist_entries()
    j = history_to_json(entries, localize=lambda m: f"{m}_tr", delta_of=lambda e: 5.0 if not e.baseline else None)
    data = json.loads(j)
    assert data["entries"][0]["metric_label"] == "cpu_single_tr"
    assert data["entries"][0]["delta_pct"] == 5.0
    assert data["entries"][1]["baseline"] is True
    assert data["entries"][1]["delta_pct"] is None

    csv_text = history_to_csv(entries, localize=lambda m: f"{m}_tr", delta_of=lambda e: 5.0 if not e.baseline else None)
    assert csv_text.splitlines()[0].startswith("Time")
    assert "cpu_single_tr" in csv_text


def test_write_report_respects_fmt(tmp_path) -> None:
    p = tmp_path / "out"
    write_report(p, "hello", fmt="csv")
    assert p.read_text(encoding="utf-8-sig").startswith("hello")

    p2 = tmp_path / "out.json"
    write_report(p2, '{"a":1}', fmt="json")
    # utf-8 (no BOM) starts with {
    assert p2.read_text(encoding="utf-8").startswith("{")

    # no suffix -> csv BOM
    p3 = tmp_path / "out3"
    write_report(p3, "hi")
    assert p3.read_text(encoding="utf-8-sig") == "hi"


def test_export_health_and_history(tmp_path) -> None:
    report = _health_report()
    out = tmp_path / "health.csv"
    target = export_health(report, out)
    assert target == out
    assert target.exists()

    entries = _hist_entries()
    out2 = tmp_path / "hist.json"
    export_history(entries, out2)
    assert out2.exists()
    data = json.loads(out2.read_text(encoding="utf-8"))
    assert data["count"] == 2


def test_report_error_on_write_failure(tmp_path, monkeypatch) -> None:
    bad = tmp_path / "subdir" / "x.csv"

    def boom(*_a, **_k):
        raise OSError("disk full")

    monkeypatch.setattr(Path, "write_text", boom)
    with pytest.raises(ReportError, match="disk full"):
        write_report(bad, "x", fmt="csv")


# ---------- UI export ----------


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    import time

    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class FakeService:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[BenchmarkType] = []

    def run(self, btype: BenchmarkType, *, disk_dir=None) -> list[BenchmarkResult]:
        self.calls.append(btype)
        if self.fail:
            raise RuntimeError("boom")
        return [BenchmarkResult(type=btype, metric="cpu_single", value=123.4, unit="MB/s", duration_ms=11, runs=1, detail="d")]


def _bench_page(tmp_path):
    from app.ui.benchmarks import BenchmarksPage

    history = BenchmarkHistory(store=tmp_path / "bench_history.json")
    return BenchmarksPage(service=FakeService(), history=history)


def test_health_export_button_and_flow(qapp, tmp_path) -> None:
    from app.ui.health import HealthPage

    page = HealthPage(service=None)
    assert page.export_button.isEnabled() is False
    page._report = HealthReport(score=90, grade="Excellent", findings=())
    page.export_button.setEnabled(True)

    target = tmp_path / "report.csv"
    page._ask_save_path = lambda *a, **k: str(target)

    page.export_report()
    assert target.exists()
    assert target.read_text(encoding="utf-8-sig").startswith("Category")
    assert "Exported to" in page.status_label.text()


def test_health_export_nothing_when_no_report(qapp, monkeypatch) -> None:
    from app.ui.health import HealthPage

    page = HealthPage(service=None)
    monkeypatch.setattr("app.ui.health.export_health", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not export")))
    page.export_report()
    assert "Nothing to export" in page.status_label.text()


def test_bench_export_nothing_when_empty(qapp, tmp_path, monkeypatch) -> None:
    page = _bench_page(tmp_path)
    monkeypatch.setattr("app.ui.benchmarks.export_history", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not export")))
    page.export_history()
    assert "Nothing to export" in page.status_label.text()


def test_bench_export_writes_file(qapp, tmp_path) -> None:
    page = _bench_page(tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)

    target = tmp_path / "hist.json"
    page._ask_save_path = lambda *a, **k: str(target)

    page.export_history()
    assert target.exists()
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["count"] >= 1
    assert "Exported to" in page.status_label.text()
