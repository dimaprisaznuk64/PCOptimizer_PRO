from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from app.changes import ChangeJournal
from app.recovery import CrashTracker, RecoveryService


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


def _marker(tmp_path: Path, *, pid: int = 4242, heartbeat: float = 100.0) -> Path:
    path = tmp_path / "session.json"
    path.write_text(
        json.dumps(
            {"pid": pid, "started": 50.0, "heartbeat": heartbeat, "version": "2.1.5"}
        ),
        encoding="utf-8",
    )
    return path


def test_first_start_claims_marker_without_crash(tmp_path: Path) -> None:
    tracker = CrashTracker(tmp_path, now=lambda: 1000.0, pid=10, version="2.2.0")

    assert tracker.start() is None
    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert payload == {
        "pid": 10,
        "started": 1000.0,
        "heartbeat": 1000.0,
        "version": "2.2.0",
    }
    assert not (tmp_path / "session.json.tmp").exists()


def test_stale_dead_marker_reports_unclean_exit_and_is_replaced(tmp_path: Path) -> None:
    _marker(tmp_path)
    tracker = CrashTracker(
        tmp_path, now=lambda: 1000.0, pid=10, alive=lambda pid: False
    )

    crash = tracker.start()

    assert crash is not None
    assert (crash.pid, crash.heartbeat, crash.version) == (4242, 100.0, "2.1.5")
    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert payload["pid"] == 10
    assert payload["started"] == 50.0


def test_fresh_or_live_marker_is_not_a_crash(tmp_path: Path) -> None:
    fresh = CrashTracker(
        tmp_path, now=lambda: 200.0, pid=10, alive=lambda pid: False
    )
    _marker(tmp_path)
    assert fresh.start() is None

    _marker(tmp_path)
    live = CrashTracker(tmp_path, now=lambda: 1000.0, pid=10, alive=lambda pid: True)
    assert live.start() is None


def test_corrupt_marker_is_quarantined_and_reported(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text("{broken", encoding="utf-8")
    tracker = CrashTracker(tmp_path, now=lambda: 1000.0, pid=10)

    assert tracker.start() is None
    quarantine = [p for p in tmp_path.iterdir() if ".corrupt-" in p.name]
    assert len(quarantine) == 1
    assert any(issue.kind == "quarantine" for issue in RecoveryService(tmp_path).scan().issues)


def test_heartbeat_refreshes_marker_and_is_throttled(tmp_path: Path) -> None:
    clock = [1000.0]
    tracker = CrashTracker(
        tmp_path, now=lambda: clock[0], pid=10, heartbeat_every_s=30.0
    )
    tracker.start()
    clock[0] += 10.0
    tracker.heartbeat()
    assert json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))["heartbeat"] == 1000.0

    clock[0] += 25.0
    tracker.heartbeat()
    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert payload["heartbeat"] == 1035.0
    assert payload["pid"] == 10


def test_heartbeat_retries_after_failed_marker_write(tmp_path: Path, monkeypatch) -> None:
    clock = [1000.0]
    tracker = CrashTracker(tmp_path, now=lambda: clock[0], pid=10, heartbeat_every_s=30.0)
    tracker.start()
    original_write = Path.write_text
    fail_next = [True]

    def flaky_write(self: Path, *args: object, **kwargs: object) -> int:
        if fail_next[0] and self.name == "session.json.tmp":
            fail_next[0] = False
            raise OSError("disk full")
        return original_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", flaky_write)
    clock[0] += 40.0
    with pytest.raises(OSError):
        tracker.heartbeat()

    monkeypatch.undo()
    clock[0] += 1.0
    tracker.heartbeat()
    payload = json.loads((tmp_path / "session.json").read_text(encoding="utf-8"))
    assert payload["heartbeat"] == 1041.0


def test_finish_removes_own_marker_but_not_another_session(tmp_path: Path) -> None:
    tracker = CrashTracker(tmp_path, now=lambda: 1000.0, pid=10)
    tracker.start()
    assert tracker.finish() is True
    assert not (tmp_path / "session.json").exists()

    _marker(tmp_path, pid=9999)
    assert tracker.finish() is False
    assert (tmp_path / "session.json").exists()
