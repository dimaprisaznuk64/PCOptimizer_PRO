from __future__ import annotations

import os
import time
from pathlib import Path

from app.changes import ChangeJournal
from app.recovery import RecoveryService


def test_scan_reports_stale_temp_and_quarantine(tmp_path: Path) -> None:
    now = time.time()
    stale = tmp_path / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    os.utime(stale, (now - 7200, now - 7200))
    fresh = tmp_path / "activity.jsonl.tmp"
    fresh.write_text("{}", encoding="utf-8")
    os.utime(fresh, (now, now))
    quarantine = tmp_path / "gaming_custom.json.corrupt-20261126"
    quarantine.write_text("broken", encoding="utf-8")

    report = RecoveryService(root=tmp_path, now=lambda: now).scan()

    assert {issue.kind for issue in report.issues} == {"quarantine", "temp"}
    assert report.cleanable == 1
    assert not report.ok
    assert fresh.exists()


def test_scan_includes_journal_integrity_error(tmp_path: Path) -> None:
    store = tmp_path / "changes.jsonl"
    store.write_text('{"bad": true}\n', encoding="utf-8")
    journal = ChangeJournal(store=store)

    report = RecoveryService(root=tmp_path, journal=journal, now=lambda: 0.0).scan()

    journal_issue = next(issue for issue in report.issues if issue.kind == "journal")
    assert "corrupt entry" in journal_issue.detail
    assert not journal_issue.cleanable


def test_clean_stale_removes_only_cleanable_files(tmp_path: Path) -> None:
    now = time.time()
    stale = tmp_path / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    os.utime(stale, (now - 7200, now - 7200))
    quarantine = tmp_path / "history.json.corrupt-20261126"
    quarantine.write_text("broken", encoding="utf-8")
    service = RecoveryService(root=tmp_path, now=lambda: now)

    removed, errors = service.clean_stale(service.scan())

    assert removed == 1
    assert errors == ()
    assert not stale.exists()
    assert quarantine.exists()


def test_fresh_temp_files_are_not_reported(tmp_path: Path) -> None:
    now = time.time()
    fresh = tmp_path / "settings.json.json.tmp"
    fresh.write_text("{}", encoding="utf-8")
    os.utime(fresh, (now, now))

    report = RecoveryService(root=tmp_path, now=lambda: now).scan()

    assert report.ok
    assert report.cleanable == 0


def test_clean_stale_skips_file_touched_after_scan(tmp_path: Path) -> None:
    now = time.time()
    stale = tmp_path / "settings.json.tmp"
    stale.write_text("{}", encoding="utf-8")
    os.utime(stale, (now - 7200, now - 7200))
    service = RecoveryService(root=tmp_path, now=lambda: now)
    report = service.scan()

    os.utime(stale, (now, now))
    removed, errors = service.clean_stale(report)

    assert removed == 0
    assert errors == ()
    assert stale.exists()
