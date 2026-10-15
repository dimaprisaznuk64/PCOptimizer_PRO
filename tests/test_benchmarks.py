from __future__ import annotations

import time

import pytest

from app.benchmarks import (
    BenchmarkError,
    BenchmarkResult,
    BenchmarkService,
    BenchmarkType,
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
    target = tmp_path / "bench.bin"
    results = _tiny_service().run(BenchmarkType.DISK, disk_path=target)
    assert [r.metric for r in results] == ["disk_write", "disk_read"]
    for result in results:
        assert result.type is BenchmarkType.DISK
        assert result.unit == "MB/s"
        assert result.value > 0
    assert not target.exists()


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


# ---------- page ----------


class FakeBenchmarkService:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls: list[BenchmarkType] = []

    def run(self, btype: BenchmarkType, *, disk_path=None) -> list[BenchmarkResult]:
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


def test_page_registered_in_nav(qapp) -> None:
    assert "benchmarks" in {key for key, _ in NAV_ITEMS}
    window = MainWindow()
    assert isinstance(window.page("benchmarks"), BenchmarksPage)
    window.close()


def test_page_renders_idle(qapp) -> None:
    page = BenchmarksPage(service=FakeBenchmarkService())
    assert page.table.rowCount() == 0
    assert page.status_label.text() == "Idle"
    assert page.cpu_btn.isEnabled()


def test_page_run_cpu_renders_row(qapp) -> None:
    service = FakeBenchmarkService()
    page = BenchmarksPage(service=service)
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert service.calls == [BenchmarkType.CPU]
    assert page.table.item(0, 0).text() == "CPU single-thread"
    assert page.table.item(0, 1).text() == "123.4"
    assert "Done" in page.status_label.text()
    assert page.cpu_btn.isEnabled()


def test_page_busy_disables_buttons(qapp) -> None:
    page = BenchmarksPage(service=FakeBenchmarkService())
    page.start_run(BenchmarkType.ALL)
    assert not page.cpu_btn.isEnabled()
    assert not page.ram_btn.isEnabled()
    assert not page.disk_btn.isEnabled()
    assert not page.all_btn.isEnabled()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert page.all_btn.isEnabled()


def test_page_reports_failure(qapp) -> None:
    page = BenchmarksPage(service=FakeBenchmarkService(fail=True))
    page.start_run(BenchmarkType.CPU)
    assert _wait_until(qapp, lambda: "Failed" in page.status_label.text())
    assert page.table.rowCount() == 0
    assert page.cpu_btn.isEnabled()


def test_page_second_run_ignored_while_busy(qapp) -> None:
    service = FakeBenchmarkService()
    page = BenchmarksPage(service=service)
    page.start_run(BenchmarkType.CPU)
    page.start_run(BenchmarkType.RAM)
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    assert service.calls == [BenchmarkType.CPU]
