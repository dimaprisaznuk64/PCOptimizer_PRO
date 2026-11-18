from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from threading import Event

import pytest
from PySide6.QtCore import QObject, Signal

from app.i18n import I18nService, tr
from app.reports.center import (
    PERFORMANCE_HISTORY_MINUTES,
    ExportBundle,
    ExportCenterService,
    ExportKind,
    ExportResult,
    default_exporters,
)
from app.reports.service import ReportError, write_report

STAMP = datetime(2026, 11, 18, 12, 34, 56).timestamp()


def _now() -> float:
    return STAMP


def _fake_exporter(text: str = "SENTINEL"):
    def exporter(path: Path, data: object | None, fmt: str) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if fmt == "pdf":
            target.write_bytes(b"%PDF-1.4\n%%EOF\n")
        else:
            write_report(target, f"{text},{fmt}\n", fmt)
        return target

    return exporter


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


class _FakeHistory:
    def __init__(self, samples: list) -> None:
        self.samples = samples
        self.minutes: float | None = None

    def query(self, minutes: float) -> list:
        self.minutes = minutes
        return self.samples


def test_jobs_cover_all_kinds_and_report_availability() -> None:
    service = ExportCenterService(exporters={ExportKind.HEALTH: _fake_exporter()}, now=_now)
    jobs = service.jobs()
    by_kind = {job.kind: job for job in jobs}

    assert len(jobs) == 5
    assert set(by_kind) == set(ExportKind)
    assert by_kind[ExportKind.HEALTH].available is True
    assert by_kind[ExportKind.BENCHMARKS].available is False
    assert by_kind[ExportKind.BENCHMARKS].label_key == "export_kind_benchmarks"
    assert "csv" in by_kind[ExportKind.HEALTH].formats
    assert "pdf" not in by_kind[ExportKind.PERFORMANCE_HISTORY].formats

    forced = ExportCenterService(
        exporters={ExportKind.HEALTH: _fake_exporter()},
        now=_now,
        availability={ExportKind.BENCHMARKS: True},
    )
    assert next(job for job in forced.jobs() if job.kind is ExportKind.BENCHMARKS).available


def test_default_filename_uses_injected_now() -> None:
    service = ExportCenterService(exporters={}, now=_now)
    assert (
        service.default_filename(ExportKind.HEALTH, "csv")
        == "health_report_20261118_123456.csv"
    )
    assert service.default_filename("diagnostics", "json").endswith(".json")


def test_export_dispatches_with_inferred_format_and_data(tmp_path) -> None:
    calls: list[tuple[Path, object | None, str]] = []

    def exporter(path: Path, data: object | None, fmt: str) -> Path:
        calls.append((path, data, fmt))
        return write_report(path, "ok\n", fmt)

    service = ExportCenterService(exporters={ExportKind.HEALTH: exporter}, now=_now)
    target = tmp_path / "health.JSON"
    marker = {"score": 75}

    assert service.export(ExportKind.HEALTH, target, marker) == target
    assert calls == [(target, marker, "json")]
    assert target.read_text(encoding="utf-8") == "ok\n"

    service.export("health", tmp_path / "explicit", fmt="csv")
    assert calls[-1][2] == "csv"
    assert (tmp_path / "explicit").read_bytes()[:3] == b"\xef\xbb\xbf"


def test_export_wraps_oserror_and_missing_exporter(tmp_path, monkeypatch) -> None:
    def boom(path: Path, data: object | None, fmt: str) -> Path:
        raise OSError("disk full")

    service = ExportCenterService(exporters={ExportKind.HEALTH: boom}, now=_now)
    with pytest.raises(ReportError, match="disk full"):
        service.export(ExportKind.HEALTH, tmp_path / "x.csv")

    bare = ExportCenterService(exporters={}, now=_now)
    with pytest.raises(ReportError, match="no exporter"):
        bare.export(ExportKind.DIAGNOSTICS, tmp_path / "x.csv")

    def no_dir(*_a, **_k) -> None:
        raise OSError("read only")

    monkeypatch.setattr(Path, "mkdir", no_dir)
    with pytest.raises(ReportError, match="read only"):
        service.export_selected([ExportKind.HEALTH], tmp_path / "locked", "csv")


def test_export_selected_writes_unique_bundle(tmp_path) -> None:
    exporters = {
        ExportKind.HEALTH: _fake_exporter("health"),
        ExportKind.DIAGNOSTICS: _fake_exporter("diag"),
    }
    service = ExportCenterService(exporters=exporters, now=_now)
    directory = tmp_path / "bundle"
    directory.mkdir()

    collision = directory / "health_report_20261118_123456.csv"
    collision.write_text("old", encoding="utf-8")

    bundle = service.export_selected([ExportKind.HEALTH, "diagnostics"], directory, "csv")
    paths = list(bundle.written)
    assert bundle.ok
    assert not bundle.errors
    assert len(paths) == 2
    assert len({path.name for path in paths}) == 2
    assert paths[0].name == "health_report_20261118_123456_2.csv"
    assert "health" in paths[0].read_text(encoding="utf-8-sig")
    assert "diag" in paths[1].read_text(encoding="utf-8-sig")
    assert all(path.parent == directory for path in paths)


def test_export_selected_returns_per_job_results_and_errors(tmp_path) -> None:
    def failing(path: Path, data: object | None, fmt: str) -> Path:
        raise ReportError("diagnostics unavailable")

    exporters = {
        ExportKind.HEALTH: _fake_exporter("health"),
        ExportKind.DIAGNOSTICS: failing,
        ExportKind.BENCHMARKS: _fake_exporter("bench"),
    }
    service = ExportCenterService(exporters=exporters, now=_now)
    bundle = service.export_selected(
        [ExportKind.HEALTH, ExportKind.DIAGNOSTICS, ExportKind.BENCHMARKS],
        tmp_path / "bundle",
        "csv",
    )

    assert not bundle.ok
    assert bundle.partial
    assert [result.kind for result in bundle.results] == [
        ExportKind.HEALTH,
        ExportKind.DIAGNOSTICS,
        ExportKind.BENCHMARKS,
    ]
    assert [result.ok for result in bundle.results] == [True, False, True]
    assert [result.kind for result in bundle.errors] == [ExportKind.DIAGNOSTICS]
    assert "diagnostics unavailable" in bundle.errors[0].error
    names = [path.name for path in bundle.written]
    assert any(name.startswith("health_report_") for name in names)
    assert any(name.startswith("benchmark_history_") for name in names)


def test_export_selected_preserves_written_files_after_failure(tmp_path) -> None:
    def failing(path: Path, data: object | None, fmt: str) -> Path:
        raise ReportError("disk full")

    service = ExportCenterService(
        exporters={
            ExportKind.HEALTH: _fake_exporter("health"),
            ExportKind.DIAGNOSTICS: failing,
        },
        now=_now,
    )
    bundle = service.export_selected(
        [ExportKind.HEALTH, ExportKind.DIAGNOSTICS], tmp_path / "bundle", "csv"
    )

    assert bundle.partial
    assert len(bundle.written) == 1
    written = bundle.written[0]
    assert written.exists()
    assert "health" in written.read_text(encoding="utf-8-sig")
    assert bundle.results[0].path == written
    assert bundle.results[1].path is None


def test_performance_history_exporter_uses_real_query(tmp_path) -> None:
    from app.history.service import HistorySample

    sample = HistorySample(
        ts=STAMP,
        cpu=55.5,
        ram=61.0,
        top_processes=(("chrome.exe", 512.0),),
    )
    history = _FakeHistory([sample])
    exporters = default_exporters(now=_now, history=history)
    assert set(exporters) == set(ExportKind)

    service = ExportCenterService(exporters=exporters, now=_now)
    json_path = tmp_path / "perf.json"
    service.export(ExportKind.PERFORMANCE_HISTORY, json_path, fmt="json")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert history.minutes == PERFORMANCE_HISTORY_MINUTES
    assert payload["count"] == 1
    assert payload["samples"][0]["cpu"] == 55.5
    assert payload["samples"][0]["top_processes"] == [["chrome.exe", 512.0]]

    csv_path = tmp_path / "perf.csv"
    service.export(ExportKind.PERFORMANCE_HISTORY, csv_path, fmt="csv")
    text = csv_path.read_text(encoding="utf-8-sig")
    assert text.splitlines()[0].startswith("Time,CPU %")
    assert "chrome.exe 512MB" in text

    empty = ExportCenterService(
        exporters=default_exporters(now=_now, history=_FakeHistory([])), now=_now
    )
    empty_path = tmp_path / "empty.csv"
    empty.export(ExportKind.PERFORMANCE_HISTORY, empty_path, fmt="csv")
    assert len(empty_path.read_text(encoding="utf-8-sig").strip().splitlines()) == 1


def test_system_report_exporter_uses_existing_builder(tmp_path) -> None:
    service = ExportCenterService(exporters=default_exporters(now=_now), now=_now)
    target = tmp_path / "system.html"
    service.export(
        ExportKind.SYSTEM_REPORT,
        target,
        data={"system": {"os_name": "Windows 11"}},
        fmt="html",
    )
    text = target.read_text(encoding="utf-8")
    assert "System" in text
    assert "Windows 11" in text


def test_export_center_pdf_uses_qt_renderer(qapp, tmp_path) -> None:
    service = ExportCenterService(exporters=default_exporters(now=_now), now=_now)
    target = tmp_path / "system.pdf"
    service.export(ExportKind.SYSTEM_REPORT, target, data="<h1>Export Center</h1>", fmt="pdf")
    assert target.read_bytes()[:5] == b"%PDF-"
    assert target.stat().st_size > 1000


def _page(tmp_path, exporters=None):
    chosen = exporters or {kind: _fake_exporter() for kind in ExportKind}
    service = ExportCenterService(exporters=chosen, now=_now)
    from app.ui.export_center import ExportCenterPage

    page = ExportCenterPage(service=service)
    page._dir_edit.setText(str(tmp_path))
    return page


def test_page_uses_com_task_with_parent(qapp, tmp_path, monkeypatch) -> None:
    import app.ui.export_center as export_center_module

    calls: list[tuple[object, bool]] = []

    class FakeTask(QObject):
        done = Signal(object)
        failed = Signal(str)
        finished = Signal()

        def __init__(self, fn, parent=None, *, com=False) -> None:
            super().__init__(parent)
            calls.append((parent, com))

        def start(self) -> None:
            return None

    monkeypatch.setattr(export_center_module, "Task", FakeTask)
    page = _page(tmp_path)
    page._checks[ExportKind.SYSTEM_REPORT].setChecked(False)
    page.start_export()

    assert calls == [(page, True)]
    assert page._task is not None
    assert page._task.parent() is page
    page._task.finished.emit()
    assert page._task is None
    assert page.export_button.isEnabled()


def test_page_reports_partial_success_and_keeps_written_files(qapp, tmp_path) -> None:
    written = tmp_path / "health_report.csv"
    write_report(written, "health\n", "csv")
    bundle = ExportBundle(
        (
            ExportResult(ExportKind.HEALTH, written),
            ExportResult(ExportKind.DIAGNOSTICS, error="boom"),
        )
    )
    page = _page(tmp_path)
    page._checks[ExportKind.SYSTEM_REPORT].setChecked(False)
    page._service.export_selected = lambda kinds, directory, fmt: bundle
    page.start_export()

    assert _wait_until(qapp, lambda: tr("export_center_partial") in page.status_label.text())
    assert "boom" in page.status_label.text()
    assert "1/2" in page.status_label.text()
    assert page._files == [written]
    assert written.name in page.preview.toPlainText()
    assert "boom" in page.preview.toPlainText()
    assert _wait_until(qapp, lambda: page._task is None)
    qapp.processEvents()


def test_page_builds_checklist_and_respects_availability(qapp, tmp_path) -> None:
    page = _page(tmp_path, exporters={ExportKind.HEALTH: _fake_exporter()})
    assert page.objectName() == "page"
    assert page._title.objectName() == "pageTitle"
    assert page._desc.objectName() == "pageDesc"
    assert len(page._checks) == 5
    assert page.format_combo.count() == 4
    assert page._checks[ExportKind.HEALTH].isEnabled()
    for kind in ExportKind:
        if kind is not ExportKind.HEALTH:
            check = page._checks[kind]
            assert not check.isEnabled()
            assert tr("export_center_unavailable") in check.toolTip()


def test_page_selection_calls_export_selected(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    page._checks[ExportKind.BENCHMARKS].setChecked(False)
    page._checks[ExportKind.PERFORMANCE_HISTORY].setChecked(False)
    page._checks[ExportKind.SYSTEM_REPORT].setChecked(False)
    expected = [ExportKind.HEALTH, ExportKind.DIAGNOSTICS]

    calls: list[tuple[list[ExportKind], str, str]] = []
    original = page._service.export_selected

    def tracked(kinds, directory, fmt):
        calls.append((list(kinds), directory, fmt))
        return original(kinds, directory, fmt)

    page._service.export_selected = tracked
    page.export_button.click()

    assert _wait_until(qapp, lambda: tr("export_center_done").split("{")[0] in page.status_label.text())
    assert _wait_until(qapp, lambda: page._task is None)
    qapp.processEvents()
    assert calls == [(expected, str(tmp_path), "csv")]
    assert len(page._files) == 2
    assert all(path.exists() for path in page._files)
    assert all(path.name in page.preview.toPlainText() for path in page._files)
    assert page._task is None
    assert page.export_button.isEnabled()


def test_page_busy_disables_controls(qapp, tmp_path) -> None:
    started = Event()
    release = Event()

    def blocking(kinds, directory, fmt):
        started.set()
        release.wait(5)
        return ExportBundle(())

    page = _page(tmp_path)
    page._checks[ExportKind.SYSTEM_REPORT].setChecked(False)
    page._service.export_selected = blocking
    try:
        page.start_export()
        assert _wait_until(qapp, started.is_set)
        assert not page.export_button.isEnabled()
        assert not page.format_combo.isEnabled()
        assert not page._browse_button.isEnabled()
        assert all(not check.isEnabled() for check in page._checks.values())
        release.set()
        assert _wait_until(qapp, lambda: page._task is None)
        assert page.export_button.isEnabled()
        assert all(page._checks[kind].isEnabled() for kind in ExportKind)
    finally:
        release.set()


def test_page_failure_path(qapp, tmp_path) -> None:
    def broken(kinds, directory, fmt):
        raise ReportError("export failed")

    page = _page(tmp_path)
    page._checks[ExportKind.SYSTEM_REPORT].setChecked(False)
    page._service.export_selected = broken
    page.start_export()
    assert _wait_until(qapp, lambda: "export failed" in page.status_label.text())
    assert page._task is None
    assert page.export_button.isEnabled()
    assert all(page._checks[kind].isEnabled() for kind in ExportKind)


def test_page_browse_and_retranslate(qapp, tmp_path) -> None:
    page = _page(tmp_path)
    chosen = tmp_path / "chosen"
    page._ask_directory = lambda: str(chosen)
    page._browse_button.click()
    assert page._dir_edit.text() == str(chosen)
    assert str(chosen) in page.preview.toPlainText()

    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert page._title.text() == tr("export_center_title")
        assert page._desc.text() == tr("export_center_desc")
        assert (
            page._jobs_card.title_label.text().lower() == tr("export_center_jobs").lower()
        )
        assert page.export_button.text() == tr("export_center_export")
        assert page._checks[ExportKind.HEALTH].text() == tr("export_kind_health")
        assert page.format_combo.itemText(0) == tr("export_fmt_csv")
        assert tr("export_center_preview_header") in page.preview.toPlainText()
    finally:
        I18nService.instance().set_language("EN", emit=False)


def test_pdf_preview_uses_qtpdf_when_available(qapp, tmp_path) -> None:
    pytest.importorskip("PySide6.QtPdf")
    from app.reports.pdf import render_pdf
    from app.ui.export_center import _pdf_pages

    pdf = render_pdf("<h1>Export Center</h1>", tmp_path / "preview.pdf")
    pages = _pdf_pages(pdf)
    if pages is None:
        pytest.skip("Qt PDF backend could not load the generated document")
    assert pages >= 1

    page = _page(tmp_path, exporters={ExportKind.SYSTEM_REPORT: _fake_exporter()})
    for kind in ExportKind:
        page._checks[kind].setChecked(kind is ExportKind.SYSTEM_REPORT)
    page.format_combo.setCurrentIndex(3)
    page.start_export()
    assert _wait_until(qapp, lambda: tr("export_center_done").split("{")[0] in page.status_label.text())
    assert _wait_until(qapp, lambda: page._task is None)
    qapp.processEvents()
    assert any(path.name in page.preview.toPlainText() for path in page._files)
