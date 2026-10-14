from __future__ import annotations

import os
import time

import pytest
from PySide6.QtCore import Qt

from app.cleaner import CleanerService, CleanTarget, default_targets
from app.cleaner.service import RECYCLE_BIN_ID, _summarize
from app.ui.cleaner import CleanerPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture()
def cache_target(tmp_path):
    root = tmp_path / "cache"
    (root / "sub").mkdir(parents=True)
    (root / "a.txt").write_bytes(b"x" * 1000)
    (root / "sub" / "b.bin").write_bytes(b"y" * 2048)
    target = CleanTarget("t1", "Test cache", "System", paths=(str(root),))
    return target, root


def test_scan_counts_files_and_bytes(cache_target) -> None:
    target, _root = cache_target
    service = CleanerService([target])
    result = service.scan(target)
    assert result.files == 2
    assert result.bytes == 3048
    assert result.error is None


def test_scan_missing_path_is_empty(tmp_path) -> None:
    target = CleanTarget("gone", "Gone", "System", paths=(str(tmp_path / "nope"),))
    result = CleanerService([target]).scan(target)
    assert result.files == 0
    assert result.bytes == 0
    assert result.error is None


def test_summarize_accepts_exception_objects() -> None:
    summary = _summarize([PermissionError(13, "access denied")])
    assert summary is not None and "access denied" in summary


def test_scan_survives_walk_error(tmp_path, monkeypatch) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    (root / "ok.txt").write_bytes(b"x" * 64)
    target = CleanTarget("walk", "Walk", "System", paths=(str(root),))
    real_walk = os.walk

    def flaky_walk(top, *args, **kwargs):
        onerror = kwargs.get("onerror")
        if onerror is not None:
            onerror(PermissionError(13, "access denied"))
        yield from real_walk(top, *args, **kwargs)

    monkeypatch.setattr(os, "walk", flaky_walk)
    result = CleanerService([target]).scan(target)
    assert result.files == 1
    assert result.bytes == 64
    assert "access denied" in (result.error or "")


def test_clean_removes_files_and_empty_dirs(cache_target) -> None:
    target, root = cache_target
    service = CleanerService([target])
    outcome = service.clean(target, known_bytes=3048)
    assert outcome.freed_bytes == 3048
    assert outcome.files_deleted == 2
    assert outcome.files_skipped == 0
    assert outcome.error is None
    assert root.exists()
    assert not (root / "a.txt").exists()
    assert not (root / "sub").exists()


def test_clean_skips_locked_files(tmp_path) -> None:
    root = tmp_path / "locked"
    root.mkdir()
    locked = root / "busy.txt"
    locked.write_bytes(b"z" * 4096)
    loose = root / "loose.txt"
    loose.write_bytes(b"w" * 128)
    target = CleanTarget("locked", "Locked", "System", paths=(str(root),))

    handle = locked.open("rb")
    try:
        outcome = CleanerService([target]).clean(target)
        assert outcome.files_skipped >= 1
        assert outcome.freed_bytes == 128
        assert locked.exists()
        assert not loose.exists()
    finally:
        handle.close()

    outcome = CleanerService([target]).clean(target)
    assert outcome.files_deleted == 1
    assert not locked.exists()


def test_scan_follows_glob_patterns(tmp_path) -> None:
    explorer = tmp_path / "Explorer"
    explorer.mkdir()
    (explorer / "thumbcache_32.db").write_bytes(b"a" * 100)
    (explorer / "thumbcache_96.db").write_bytes(b"b" * 200)
    target = CleanTarget("thumbs", "Thumbs", "System", paths=(str(explorer / "thumbcache_*.db"),))
    result = CleanerService([target]).scan(target)
    assert result.files == 2
    assert result.bytes == 300


def test_default_targets_have_unique_ids_and_recycle_bin() -> None:
    targets = default_targets()
    ids = [t.id for t in targets]
    assert len(ids) == len(set(ids))
    assert RECYCLE_BIN_ID in ids
    assert all(t.paths for t in targets if t.kind == "files")


def test_default_service_scan_runs() -> None:
    service = CleanerService()
    results = service.scan_all()
    assert [r.target_id for r in results] == [t.id for t in service.targets]
    assert all(r.bytes >= 0 for r in results)


class InteractiveCleaner(CleanerPage):
    def __init__(self, service) -> None:
        super().__init__(service=service)
        self.confirms: list[tuple[int, int]] = []

    def _ask_confirm(self, targets: int, total_bytes: int) -> bool:
        self.confirms.append((targets, total_bytes))
        return True


def _two_target_service(tmp_path) -> CleanerService:
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "1.bin").write_bytes(b"1" * 1024)
    (b / "2.bin").write_bytes(b"2" * 2048)
    return CleanerService(
        [
            CleanTarget("a", "Target A", "System", paths=(str(a),)),
            CleanTarget("b", "Target B", "Browser", paths=(str(b),)),
        ]
    )


def test_page_scan_populates_table(qapp, tmp_path) -> None:
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service)
    page._apply_scan(service.scan_all())
    assert page.table.rowCount() == 2
    assert page.table.item(0, 3).text() == "1.0KB"
    assert page.table.item(1, 3).text() == "2.0KB"
    assert page.table.item(0, 4).text() == "ready"
    assert "2 of 2" in page.summary.text()
    assert page.clean_button.isEnabled()


def test_page_checkbox_updates_summary(qapp, tmp_path) -> None:
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service)
    page._apply_scan(service.scan_all())
    page.table.item(0, 0).setCheckState(Qt.CheckState.Unchecked)
    assert "1 of 2" in page.summary.text()
    assert "1.0KB" in page.summary.text() or "2.0KB" in page.summary.text()


def test_page_clean_flow_deletes_and_reports(qapp, tmp_path) -> None:
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service)
    page._apply_scan(service.scan_all())
    page.start_clean()
    assert page.confirms and page.confirms[0][0] == 2
    assert _wait_until(qapp, lambda: page._task is None)
    assert "Freed" in page.status_label.text()
    assert not list((tmp_path / "a").iterdir())
    assert not list((tmp_path / "b").iterdir())
    assert page._outcomes["a"].freed_bytes == 1024
    assert page.table.item(0, 4).text().startswith("freed")


def test_page_async_scan_via_task(qapp, tmp_path) -> None:
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service)
    page.start_scan()
    assert page._task is not None
    assert _wait_until(qapp, lambda: page._task is None)
    assert "Scan complete" in page.status_label.text()
    assert page.table.item(0, 3).text() == "1.0KB"
