from __future__ import annotations

import time

import pytest

from app.benchmarks import (
    BenchmarkError,
    BenchmarkHistory,
    BenchmarkResult,
    BenchmarkService,
    BenchmarkType,
    HistoryEntry,
)
from app.ui.benchmarks import BenchmarksPage
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


def _tiny_service() -> BenchmarkService:
    return BenchmarkService(
        cpu_bytes=256 * 1024,
        ram_bytes=1024 * 1024,
        disk_bytes=2 * 1024 * 1024,
        runs=2,
        disk_runs=1,
        target_ms=0,
    )


# ---------- service ----------


def test_cpu_benchmark_returns_results() -> None:
    results = _tiny_service().run(BenchmarkType.CPU)
    assert [r.metric for r in results] == ["cpu_single", "cpu_multi"]
    for result in results:
        assert result.type is BenchmarkType.CPU
        assert result.value > 0
        assert result.unit == "MB/s"
        assert result.runs >= 1
        assert result.duration_ms >= 0


def test_ram_benchmark_returns_result() -> None:
    results = _tiny_service().run(BenchmarkType.RAM)
    assert len(results) == 1
    result = results[0]
    assert result.type is BenchmarkType.RAM
    assert result.metric == "ram_copy"
    assert result.value > 0
    assert result.unit == "GB/s"


def test_disk_benchmark_writes_and_removes_file(tmp_path) -> None:
    results = _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    assert [r.metric for r in results] == ["disk_write", "disk_read"]
    for result in results:
        assert result.type is BenchmarkType.DISK
        assert result.unit == "MB/s"
        assert result.value > 0
    # The scratch file is always cleaned up (nothing left behind).
    assert list(tmp_path.glob("pcoptimizer_bench_*")) == []


def test_disk_benchmark_never_touches_caller_file(tmp_path) -> None:
    # A pre-existing file in the target folder must survive untouched.
    keeper = tmp_path / "important.bin"
    keeper.write_bytes(b"precious user data")
    _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    assert keeper.read_bytes() == b"precious user data"


def test_disk_benchmark_cleans_up_on_failure(tmp_path, monkeypatch) -> None:
    calls = {"n": 0}

    def boom(*_args, **_kwargs):
        calls["n"] += 1
        raise OSError("disk exploded")

    monkeypatch.setattr("app.benchmarks.service.os.fsync", boom)
    with pytest.raises(OSError):
        _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    assert calls["n"] >= 1
    # Even though the write raised, no scratch file is left behind.
    assert list(tmp_path.glob("pcoptimizer_bench_*")) == []


def test_disk_read_reports_cache_mode(tmp_path) -> None:
    results = _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    read = next(r for r in results if r.metric == "disk_read")
    # The read either bypasses the OS cache or says it fell back to it.
    assert "unbuffered" in read.detail or "cached" in read.detail


def test_disk_write_uses_distinct_random_blocks(tmp_path, monkeypatch) -> None:
    import os

    import app.benchmarks.service as svc

    calls: list[int] = []
    real = os.urandom

    def spy(n: int) -> bytes:
        calls.append(n)
        return real(n)

    monkeypatch.setattr(svc.os, "urandom", spy)
    _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    # A rotating pool — not one reused buffer that a compressing controller
    # would squeeze into a phantom speedup.
    assert len(calls) >= 2


def test_disk_benchmark_refuses_when_disk_full(tmp_path, monkeypatch) -> None:
    import shutil

    import app.benchmarks.service as svc

    usage = shutil.disk_usage(tmp_path)
    monkeypatch.setattr(svc.shutil, "disk_usage", lambda _p: usage._replace(free=1))
    with pytest.raises(BenchmarkError, match="free space"):
        _tiny_service().run(BenchmarkType.DISK, disk_dir=tmp_path)
    # The scratch file (created before the check) is still cleaned up.
    assert list(tmp_path.glob("pcoptimizer_bench_*")) == []


def test_read_helpers_return_full_size(tmp_path) -> None:
    from app.benchmarks.service import _read_buffered, _read_unbuffered

    payload = tmp_path / "data.bin"
    payload.write_bytes(b"x" * (4 * 1024 * 1024))
    assert _read_buffered(payload) == 4 * 1024 * 1024
    try:
        total = _read_unbuffered(payload)
    except OSError:
        pytest.skip("unbuffered reads unsupported on this filesystem")
    else:
        assert total == 4 * 1024 * 1024


def test_all_benchmark_runs_in_order() -> None:
    results = _tiny_service().run(BenchmarkType.ALL)
    assert [r.type for r in results] == [
        BenchmarkType.CPU,
        BenchmarkType.CPU,
        BenchmarkType.RAM,
        BenchmarkType.DISK,
        BenchmarkType.DISK,
    ]


def test_unknown_benchmark_type_raises() -> None:
    class _Other:
        pass

    with pytest.raises(BenchmarkError):
        BenchmarkService().run(_Other())  # type: ignore[arg-type]


def test_calibration_lengthens_short_runs() -> None:
    # A fast workload is repeated internally so each timed run reaches the
    # target duration instead of reporting a noisy sub-millisecond figure.
    service = BenchmarkService(
        cpu_bytes=256 * 1024, runs=2, target_ms=80, max_repeats=100000
    )
    result = service.run(BenchmarkType.CPU)[0]
    assert result.duration_ms >= 40
    assert result.value > 0


def test_ram_benchmark_uses_memmove() -> None:
    service = BenchmarkService(ram_bytes=8 * 1024 * 1024, runs=1, target_ms=0, workers=4)
    result = service.run(BenchmarkType.RAM)[0]
    assert result.value > 0
    assert "threads" in result.detail


# ---------- history ----------


def _result(metric: str, value: float, unit: str = "MB/s", detail: str = "") -> BenchmarkResult:
    return BenchmarkResult(
        type=BenchmarkType.CPU,
        metric=metric,
        value=value,
        unit=unit,
        duration_ms=5,
        runs=1,
        detail=detail,
    )


def test_history_records_and_reads_back(tmp_path) -> None:
    history = BenchmarkHistory(store=tmp_path / "h.json", now=lambda: 1000.0)
    history.record([_result("cpu_single", 100.0), _result("ram_copy", 12.0, "GB/s")])
    entries = history.entries()
    # Newest first, both metrics preserved.
    assert [e.metric for e in entries] == ["ram_copy", "cpu_single"]
    assert entries[1].value == 100.0
    assert all(e.when for e in entries)


def test_history_ignores_empty_results(tmp_path) -> None:
    history = BenchmarkHistory(store=tmp_path / "h.json")
    assert history.record([]) == []
    assert history.entries() == []


def test_history_implicit_baseline_is_oldest(tmp_path) -> None:
    history = BenchmarkHistory(store=tmp_path / "h.json", now=lambda: 0.0)
    history.record([_result("cpu_single", 100.0)])
    history.record([_result("cpu_single", 150.0)])
    baseline = history.baseline_of("cpu_single")
    assert baseline is not None and baseline.value == 100.0
    # +50% against the implicit (oldest) baseline.
    assert history.delta_pct("cpu_single", 150.0) == pytest.approx(50.0)


def test_history_explicit_baseline_wins(tmp_path) -> None:
    history = BenchmarkHistory(store=tmp_path / "h.json", now=lambda: 0.0)
    history.record([_result("cpu_single", 100.0)])
    history.record([_result("cpu_single", 120.0)])
    marked = history.set_baseline()
    assert marked == 1
    baseline = history.baseline_of("cpu_single")
    assert baseline is not None and baseline.value == 120.0
    history.record([_result("cpu_single", 180.0)])
    # Regression vs the pinned 120 baseline should read as negative.
    assert history.delta_pct("cpu_single", 90.0) == pytest.approx(-25.0)


def test_history_clear_and_baseline_reset(tmp_path) -> None:
    history = BenchmarkHistory(store=tmp_path / "h.json")
    history.record([_result("cpu_single", 100.0)])
    history.set_baseline()
    assert history.has_baseline()
    history.clear_baseline()
    assert not history.has_baseline()
    history.clear()
    assert history.entries() == []


def test_history_quarantines_corrupt_store(tmp_path) -> None:
    store = tmp_path / "h.json"
    store.write_text("{ not json", encoding="utf-8")
    history = BenchmarkHistory(store=store)
    assert history.entries() == []
    assert not store.exists()
    assert list(tmp_path.glob("h.json.corrupt-*"))


def test_history_sets_time_from_now(tmp_path) -> None:
    from datetime import datetime

    history = BenchmarkHistory(store=tmp_path / "h.json", now=lambda: 1_700_000_000.0)
    entry = history.record([_result("cpu_single", 5.0)])[0]
    assert entry.when == datetime.fromtimestamp(1_700_000_000.0).isoformat(timespec="seconds")


def test_history_entry_roundtrip() -> None:
    entry = HistoryEntry("2026-01-01T00:00:00", "cpu_single", 1.0, "MB/s", "x", True)
    assert HistoryEntry.from_dict(entry.to_dict()) == entry
    assert HistoryEntry.from_dict({"nope": 1}) is None
    assert HistoryEntry.from_dict({"when": "t", "metric": "m", "value": "zz", "unit": "u"}) is None


# ---------- page ----------


class FakeBenchmarkService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[BenchmarkType] = []

    def run(self, btype: BenchmarkType, *, disk_dir=None) -> list[BenchmarkResult]:
        self.calls.append(btype)
        if self.fail:
            raise RuntimeError("boom")
        return [
            BenchmarkResult(
                type=btype,
                metric="cpu_single",
                value=123.4,
                unit="MB/s",
                duration_ms=11,
                runs=1,
                detail="fake",
            )
        ]


def _page(service, tmp_path) -> BenchmarksPage:
    history = BenchmarkHistory(store=tmp_path / "bench_history.json")
    return BenchmarksPage(service=service, history=history)


def test_page_registered_in_nav(qapp) -> None:
    assert "benchmarks" in {key for key, _ in NAV_ITEMS}
    window = MainWindow()
    assert isinstance(window.page("benchmarks"), BenchmarksPage)
    window.close()


def test_page_renders_idle(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    assert page.table.rowCount() == 0
    assert page.history_table.rowCount() == 0
    assert page.status_label.text() == "Idle"
    assert page.cpu_btn.isEnabled()


def test_page_run_cpu_renders_row(qapp, tmp_path) -> None:
    service = FakeBenchmarkService()
    page = _page(service, tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert service.calls == [BenchmarkType.CPU]
    assert page.table.item(0, 0).text() == "CPU · SHA-256 single-thread"
    assert page.table.item(0, 1).text() == "123.4"
    assert "Done" in page.status_label.text()
    assert page.cpu_btn.isEnabled()


def test_page_busy_disables_buttons(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.ALL)
    assert not page.cpu_btn.isEnabled()
    assert not page.ram_btn.isEnabled()
    assert not page.disk_btn.isEnabled()
    assert not page.all_btn.isEnabled()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert page.all_btn.isEnabled()


def test_page_reports_failure(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(fail=True), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: "Failed" in page.status_label.text())
    assert page.table.rowCount() == 0
    assert page.cpu_btn.isEnabled()


def test_page_second_run_ignored_while_busy(qapp, tmp_path) -> None:
    service = FakeBenchmarkService()
    page = _page(service, tmp_path)
    page.start_run(BenchmarkType.CPU)
    page.start_run(BenchmarkType.RAM)
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert service.calls == [BenchmarkType.CPU]


def test_page_highlights_only_active_button(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    assert not page.cpu_btn.property("primary")
    page.start_run(BenchmarkType.RAM)
    assert page.ram_btn.property("primary")
    assert not page.cpu_btn.property("primary")
    assert not page.all_btn.property("primary")
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    page.start_run(BenchmarkType.ALL)
    assert page.all_btn.property("primary")
    assert not page.ram_btn.property("primary")
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)


def test_page_records_run_into_history(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)
    assert len(page.history.entries()) == 1
    assert page.history_table.item(0, 1).text() == "CPU · SHA-256 single-thread"
    # The implicit baseline against itself is a 0.0% change, not blank.
    assert page.history_table.item(0, 4).text() == "+0.0%"


def test_page_set_baseline_marks_current(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)
    page.set_baseline()
    assert page.history.has_baseline()
    assert "★" in page.history_table.item(0, 1).text()
    # A baseline row has no delta of its own.
    assert page.history_table.item(0, 4).text() == "—"


def test_page_clear_history_confirmed(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)
    page._ask_confirm = lambda: True  # type: ignore[method-assign]
    page.clear_history()
    assert page.history_table.rowCount() == 0
    assert page.history.entries() == []
    assert page.status_label.text() == "History cleared"


def test_page_clear_history_cancelled(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)
    page._ask_confirm = lambda: False  # type: ignore[method-assign]
    page.clear_history()
    assert page.history_table.rowCount() == 1


def test_page_history_retranslate_keeps_rows(qapp, tmp_path) -> None:
    page = _page(FakeBenchmarkService(), tmp_path)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.history_table.rowCount() == 1)
    page.retranslate()
    assert page.history_table.rowCount() == 1
    assert page.history_title.text() == "HISTORY"
