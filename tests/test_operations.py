from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMainWindow

from app.changes import ChangeEntry, ChangeJournal
from app.i18n import I18nService, tr
from app.recovery import RecoveryService
from app.ui.activity import ActivityLog, Entry
from app.ui.main_window import MainWindow
from app.ui.operations import (
    OperationsPage,
    change_to_entry,
    filter_operations,
    operations_to_csv,
    operations_to_json,
)


def _entries(now: float) -> list[Entry]:
    return [
        Entry(now - 3 * 86400, "error", "Scan failed", "access denied", "health"),
        Entry(now - 20, "warn", "Optimizer partial", "one tweak skipped", "optimizer"),
        Entry(now - 10, "ok", "Cleaned cache", "1 GB freed", "cleaner"),
    ]


def test_filter_operations_by_level_query_and_age() -> None:
    now = time.time()
    entries = _entries(now)
    assert [e.title for e in filter_operations(entries)] == [e.title for e in entries]
    assert [e.title for e in filter_operations(entries, level="error")] == ["Scan failed"]
    assert [e.title for e in filter_operations(entries, query="OPTIMIZER partial")] == [
        "Optimizer partial"
    ]
    assert [e.title for e in filter_operations(entries, max_age_s=3600, now=now)] == [
        "Optimizer partial",
        "Cleaned cache",
    ]


def test_export_helpers_include_localized_details(tmp_path: Path) -> None:
    entries = _entries(time.time())
    csv_text = operations_to_csv(entries, header=("Time", "Level", "Operation", "Details", "Source"))
    assert "Scan failed" in csv_text.splitlines()[1]
    assert "access denied" in csv_text.splitlines()[1]

    data = json.loads(operations_to_json(entries))
    assert len(data) == 3
    assert data[0] == {
        "time": data[0]["time"],
        "level": "error",
        "operation": "Scan failed",
        "details": "access denied",
        "source": "health",
    }
    assert data[0]["time"][:4].isdigit()


def test_entry_source_survives_restart() -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    ActivityLog._instance = None
    fresh = ActivityLog.instance()
    assert fresh.entries(limit=1)[0].source == "cleaner"
    fresh.clear()


def test_page_renders_filters_and_shows_details(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log._items.extend(_entries(time.time()))

    page = OperationsPage(log=log)
    assert page.table.rowCount() == 3
    assert page.detail_label.text() == tr("ops_detail_hint")

    page.search.setText("access denied")
    assert page.table.rowCount() == 1
    assert page.table.item(0, 2).text() == "Scan failed"

    page.search.clear()
    page.level_combo.setCurrentIndex(3)  # errors only
    assert page.table.rowCount() == 1
    page.level_combo.setCurrentIndex(0)
    page.range_combo.setCurrentIndex(1)  # last 24 h
    assert page.table.rowCount() == 2

    page.table.selectRow(0)
    assert "Cleaned cache" in page.detail_label.text()
    assert page.open_button.isEnabled()
    page.close()  # newest entries are first, so row 0 is the cache cleanup


def test_operations_log_fills_available_height(qapp) -> None:
    window = QMainWindow()
    window.resize(1440, 860)
    page = OperationsPage()
    window.setCentralWidget(page)
    window.show()
    qapp.processEvents()

    assert page.log_card.body.stretch(0) == 1
    assert page.log_card._layout.stretch(1) == 1
    assert page.table.height() > 400
    assert page.table.height() > page.detail_label.height() * 4
    window.close()


def test_page_navigates_to_selected_source(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    log.record("Old entry", "no source")
    page = OperationsPage(log=log)
    targets: list[str] = []
    page.navigate.connect(targets.append)

    page.table.selectRow(0)
    assert not page.open_button.isEnabled()  # the newest entry has no source

    page.table.selectRow(1)
    page.open_button.click()
    assert targets == ["cleaner"]
    assert log.unread_count() == 1  # the opened entry was marked read
    page.close()


def test_page_context_menu_opens_source(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    log.record("Old entry", "no source")
    page = OperationsPage(log=log)
    targets: list[str] = []
    page.navigate.connect(targets.append)

    actions = page._context_menu.build_menu(1).actions()
    open_action = next(action for action in actions if action.text() == tr("ctx_open_page"))
    assert open_action.isEnabled()
    open_action.trigger()
    assert targets == ["cleaner"]
    assert log.unread_count() == 1
    page.close()


def test_change_entry_projection_includes_audit_fields() -> None:
    entry = ChangeEntry(
        id="0" * 32,
        ts=1_700_000_000.0,
        operation="optimizer.apply",
        outcome="ok",
        detail="BALANCED applied",
        source="optimizer",
        target="BALANCED",
        backup="C:\\backup.json",
        backup_sha256="a" * 64,
        restore_point="512",
    )

    projected = change_to_entry(entry)
    assert projected.level == "ok"
    assert projected.title == "optimizer.apply"
    assert projected.source == "optimizer"
    assert "BALANCED applied" in projected.detail
    assert "restore point: 512" in projected.detail
    assert "sha256: " + "a" * 64 in projected.detail


def test_page_shows_system_change_feed_and_keeps_it_read_only(qapp, tmp_path: Path) -> None:
    journal = ChangeJournal(store=tmp_path / "changes.jsonl")
    journal.record(
        operation="optimizer.apply",
        outcome="ok",
        detail="BALANCED applied",
        source="optimizer",
        target="BALANCED",
    )
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")

    page = OperationsPage(log=log, journal=journal)
    assert page.feed_combo.count() == 2
    page.feed_combo.setCurrentIndex(1)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 2).text() == "optimizer.apply"
    assert not page.clear_button.isEnabled()
    assert not page.mark_button.isEnabled()
    assert "intact" in page.status_label.text()

    page.clear_button.click()
    assert len(journal.entries()) == 1

    page.feed_combo.setCurrentIndex(0)
    assert page.table.rowCount() == 1
    assert page.table.item(0, 2).text() == "Cleaned cache"
    page.close()


def test_page_exports_visible_rows(tmp_path: Path, qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    page = OperationsPage(log=log)
    path = tmp_path / "ops.csv"
    monkeypatch.setattr(OperationsPage, "_ask_save_path", staticmethod(lambda name: (str(path), "CSV")))
    page.export_button.click()
    assert path.exists()
    text = path.read_text(encoding="utf-8-sig")
    assert "Operation" in text and "Cleaned cache" in text
    assert "Exported to" in page.status_label.text()
    page.close()


def test_page_clear_requires_confirmation(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    page = OperationsPage(log=log)
    monkeypatch.setattr(OperationsPage, "_ask_confirm", staticmethod(lambda: False))
    page.clear_button.click()
    assert len(log.entries(limit=None)) == 1

    monkeypatch.setattr(OperationsPage, "_ask_confirm", staticmethod(lambda: True))
    page.clear_button.click()
    assert log.entries(limit=None) == []
    assert tr("ops_cleared") == page.status_label.text()
    page.close()


def test_page_recovery_status_and_cleanup(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    stale = root / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    log = ActivityLog.instance()
    log.clear()

    page = OperationsPage(log=log, recovery=RecoveryService(root=root))
    assert page.clean_recovery_button.isEnabled()
    assert "settings.json.tmp" in page.recovery_label.text()

    monkeypatch.setattr(OperationsPage, "_ask_clean_recovery", staticmethod(lambda: True))
    page.clean_recovery_button.click()

    assert not stale.exists()
    assert page.recovery_label.text() == tr("ops_recovery_ok")
    assert not page.clean_recovery_button.isEnabled()
    assert tr("ops_recovery_cleaned", count=1) in page.status_label.text()
    page.close()


def test_page_recovery_status_refreshes_after_external_cleanup(
    qapp, tmp_path: Path
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    stale = root / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    log = ActivityLog.instance()
    log.clear()

    page = OperationsPage(log=log, recovery=RecoveryService(root=root))
    assert page.clean_recovery_button.isEnabled()
    assert "settings.json.tmp" in page.recovery_label.text()

    stale.unlink()
    log.record("Cleaned temp file", "removed", source="cleaner")
    assert page.recovery_label.text() == tr("ops_recovery_ok")
    assert not page.clean_recovery_button.isEnabled()
    page.close()


def test_page_recovery_cancel_keeps_files(
    qapp, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "data"
    root.mkdir()
    stale = root / "settings.json.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    log = ActivityLog.instance()
    log.clear()

    page = OperationsPage(log=log, recovery=RecoveryService(root=root))
    monkeypatch.setattr(OperationsPage, "_ask_clean_recovery", staticmethod(lambda: False))
    page.clean_recovery_button.click()

    assert stale.exists()
    assert page.clean_recovery_button.isEnabled()
    page.close()


def test_deferred_operations_page_loads_on_first_show(qapp) -> None:
    from app.recovery import RecoveryReport

    class _CountingRecovery:
        def __init__(self) -> None:
            self.calls = 0

        def scan(self) -> RecoveryReport:
            self.calls += 1
            return RecoveryReport(())

    recovery = _CountingRecovery()
    page = OperationsPage(log=ActivityLog.instance(), recovery=recovery, defer_load=True)
    page.retranslate()  # language changes must not trigger hidden I/O
    assert recovery.calls == 0
    page.ensure_loaded()
    assert recovery.calls == 1
    page.ensure_loaded()
    assert recovery.calls == 1
    page.close()


def test_retranslate_updates_recovery_button(qapp, tmp_path: Path) -> None:
    root = tmp_path / "data"
    root.mkdir()
    stale = root / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    old = time.time() - 7200
    os.utime(stale, (old, old))
    log = ActivityLog.instance()
    log.clear()

    page = OperationsPage(log=log, recovery=RecoveryService(root=root))
    I18nService.instance().set_language("UA")
    page.retranslate()

    assert page.clean_recovery_button.text() == tr("ops_recovery_clean")
    assert "Цілісність даних" in page.recovery_label.text()
    page.close()


def test_retranslate_keeps_filters_and_live_rows(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB", source="cleaner")
    page = OperationsPage(log=log)
    page.level_combo.setCurrentIndex(3)
    I18nService.instance().set_language("UA")
    page.retranslate()
    assert "Останні операції" in page.title_label.text()
    assert page.table.horizontalHeaderItem(2).text() == "Операція"
    assert page.level_combo.currentIndex() == 3
    assert page.table.rowCount() == 0  # no error-level records
    page.level_combo.setCurrentIndex(0)
    assert page.table.rowCount() == 1
    page.close()


def test_main_window_registers_operations_page(qapp) -> None:
    window = MainWindow()
    page = window.page("operations")
    assert type(page).__name__ == OperationsPage.__name__
    window.show_page("operations")
    assert window.current_key == "operations"
    assert window.topbar.title.text() == tr("nav_operations")
    window.close()
