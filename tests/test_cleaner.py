from __future__ import annotations

import os
import time

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog

from app.changes import ChangeJournal
from app.cleaner import (
    STANDBY_CACHE_ID,
    CleanerScheduler,
    CleanerService,
    CleanerWhitelist,
    CleanTarget,
    ScanDetail,
    default_targets,
    make_large_files_target,
    scan_large_files,
)
from app.cleaner.service import RECYCLE_BIN_ID, _summarize, is_safe_root
from app.i18n import tr
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
    assert outcome.partial is False
    assert root.exists()
    assert not (root / "a.txt").exists()
    assert not (root / "sub").exists()


def test_clean_records_outcome_in_change_journal(cache_target, tmp_path) -> None:
    target, _root = cache_target
    journal = ChangeJournal(store=tmp_path / "changes.jsonl")
    service = CleanerService([target], journal=journal)

    outcome = service.clean(target, known_bytes=3048)
    assert outcome.freed_bytes == 3048

    entry = journal.entries(limit=1)[0]
    assert entry.operation == "cleaner.clean"
    assert entry.outcome == "ok"
    assert entry.source == "cleaner"
    assert target.id in entry.detail


def test_clean_reports_partial_result_on_walk_error(tmp_path, monkeypatch) -> None:
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
    outcome = CleanerService([target]).clean(target)
    # The reachable file is still cleaned, but the result is flagged partial.
    assert outcome.files_deleted == 1
    assert outcome.error is not None
    assert "some folders were skipped" in outcome.error
    assert "access denied" in outcome.error
    assert outcome.partial is True


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
        assert outcome.partial is True  # some files freed, some locked
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


# ---------- path safety (defense in depth) ----------


def test_is_safe_root_allows_temp_subdir(tmp_path) -> None:
    assert is_safe_root(str(tmp_path / "cache"))
    assert is_safe_root(str(tmp_path / "cache" / "sub"))


def test_is_safe_root_rejects_dangerous_roots() -> None:
    home = os.path.expanduser("~")
    assert not is_safe_root(home)
    assert not is_safe_root("")
    # Drive root, e.g. "C:\" / "C:"
    root = os.path.splitdrive(os.path.abspath(os.sep))[0] + os.sep
    assert not is_safe_root(root)
    assert not is_safe_root(os.path.splitdrive(os.path.abspath(os.sep))[0])


def test_clean_refuses_drive_root(tmp_path) -> None:
    root = os.path.splitdrive(os.path.abspath(os.sep))[0] + os.sep
    target = CleanTarget("bad", "Bad", "System", paths=(root,))
    outcome = CleanerService([target]).clean(target)
    assert outcome.freed_bytes == 0
    assert outcome.files_deleted == 0
    assert outcome.error is not None and "refused unsafe" in outcome.error
    assert outcome.partial is True


def test_clean_refuses_home_root() -> None:
    home = os.path.expanduser("~")
    target = CleanTarget("home", "Home", "System", paths=(home,))
    outcome = CleanerService([target]).clean(target)
    assert outcome.freed_bytes == 0
    assert outcome.files_deleted == 0
    assert outcome.error is not None and "refused unsafe" in outcome.error


def test_scan_refuses_unsafe_path() -> None:
    home = os.path.expanduser("~")
    target = CleanTarget("home", "Home", "System", paths=(home,))
    result = CleanerService([target]).scan(target)
    assert result.files == 0
    assert result.bytes == 0
    assert result.error is not None and "refusing unsafe" in result.error


def test_is_safe_root_rejects_filesystem_root() -> None:
    assert not is_safe_root(os.sep)
    assert not is_safe_root(os.path.abspath(os.sep))


def test_scan_and_clean_do_not_follow_symlinked_directory(tmp_path) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    (root / "keep.txt").write_bytes(b"k" * 16)
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_bytes(b"s" * 4096)
    linked = root / "linked"
    try:
        os.symlink(outside, linked, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable here: {exc}")

    target = CleanTarget("link", "Link", "System", paths=(str(root),))
    service = CleanerService([target])
    scanned = service.scan(target)
    assert scanned.files == 1
    assert scanned.bytes == 16

    outcome = service.clean(target)
    assert outcome.files_deleted == 1
    assert not (root / "keep.txt").exists()
    assert (outside / "secret.txt").exists()


def test_scan_and_clean_do_not_follow_junction(tmp_path, monkeypatch) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    (root / "keep.txt").write_bytes(b"k" * 16)
    linked = root / "linked"
    linked.mkdir()
    (linked / "secret.txt").write_bytes(b"s" * 4096)
    monkeypatch.setattr(
        os.path,
        "isjunction",
        lambda p: os.path.normcase(str(p)) == os.path.normcase(str(linked)),
        raising=False,
    )

    target = CleanTarget("junction", "Junction", "System", paths=(str(root),))
    service = CleanerService([target])
    scanned = service.scan(target)
    assert scanned.files == 1
    assert scanned.bytes == 16

    outcome = service.clean(target)
    assert outcome.files_deleted == 1
    assert not (root / "keep.txt").exists()
    assert (linked / "secret.txt").exists()


def test_clean_partial_when_walk_error_and_nothing_deleted(tmp_path, monkeypatch) -> None:
    root = tmp_path / "cache"
    root.mkdir()
    target = CleanTarget("walk", "Walk", "System", paths=(str(root),))

    def flaky_walk(top, *args, **kwargs):
        onerror = kwargs.get("onerror")
        if onerror is not None:
            onerror(PermissionError(13, "access denied"))
        yield from ()

    monkeypatch.setattr(os, "walk", flaky_walk)
    outcome = CleanerService([target]).clean(target)
    # Nothing was deleted, yet the walk was incomplete -> still partial.
    assert outcome.files_deleted == 0
    assert outcome.partial is True
    assert outcome.error is not None
    assert "some folders were skipped" in outcome.error


def test_recycle_reports_scanned_counts(monkeypatch) -> None:
    import types

    shell32 = types.SimpleNamespace()

    def fake_empty(*_args):
        return 0

    shell32.SHEmptyRecycleBinW = fake_empty
    monkeypatch.setattr("app.cleaner.service.ctypes.windll.shell32", shell32, raising=False)
    target = CleanTarget(RECYCLE_BIN_ID, "Recycle Bin", "System", kind="recycle")
    outcome = CleanerService([target]).clean(target, known_bytes=1234, known_files=7)
    assert outcome.freed_bytes == 1234
    assert outcome.files_deleted == 7
    assert outcome.error is None


def test_recycle_scan_clamps_negative_size(monkeypatch) -> None:
    import types

    seen: dict[str, object] = {}

    def fake_run(args, **kwargs):
        seen["args"] = args
        return types.SimpleNamespace(returncode=0, stdout=b"4;-1429090185\n", stderr=b"")

    monkeypatch.setattr("app.cleaner.service.subprocess.run", fake_run)
    target = CleanTarget(RECYCLE_BIN_ID, "Recycle Bin", "System", kind="recycle")
    result = CleanerService([target]).scan(target)
    assert result.files == 4
    assert result.bytes == 0
    assert result.error is None
    script = seen["args"][-1]
    assert isinstance(script, str)
    assert "Get-Item -LiteralPath $p" in script
    assert "Measure-Object" not in script


def test_default_service_scan_runs() -> None:
    service = CleanerService()
    results = service.scan_all()
    assert [r.target_id for r in results] == [t.id for t in service.targets]
    assert all(r.bytes >= 0 for r in results)


class InteractiveCleaner(CleanerPage):
    def __init__(self, service, **kwargs) -> None:
        super().__init__(service=service, **kwargs)
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


def test_page_context_menu_selects_all_and_copies_path(qapp, tmp_path) -> None:
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service)
    page._apply_scan(service.scan_all())

    actions = page._context_menu.build_menu(0).actions()
    by_text = {action.text(): action for action in actions}
    by_text[tr("ctx_deselect_all")].trigger()
    assert "0 of 2" in page.summary.text()
    by_text[tr("ctx_select_all")].trigger()
    assert "2 of 2" in page.summary.text()
    by_text[tr("ctx_copy_path")].trigger()
    assert QGuiApplication.clipboard().text() == str(tmp_path / "a")


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


def test_default_targets_include_safe_cache_only_targets(monkeypatch, tmp_path) -> None:
    local = tmp_path / "LOCALAPPDATA"
    appdata = tmp_path / "APPDATA"
    windir = tmp_path / "Windows"
    temp = tmp_path / "Temp"
    paths = (
        local / "Microsoft" / "Windows" / "WER" / "ReportQueue",
        local / "Microsoft" / "Windows" / "WER" / "ReportArchive",
        local / "CrashDumps",
        local / "pip" / "Cache",
        local / "npm-cache" / "_cacache",
        appdata / "npm-cache" / "_cacache",
        windir / "Temp",
        windir / "SoftwareDistribution" / "Download",
        temp,
    )
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.setenv("WINDIR", str(windir))
    monkeypatch.setenv("TEMP", str(temp))

    targets = default_targets()
    by_id = {target.id: target for target in targets}
    assert {"wer_reports", "crash_dumps", "pip_cache", "npm_cache"} <= set(by_id)
    assert all(
        part not in {"winsxs", "installer"}
        for target in targets
        for path in target.paths
        for part in os.path.normpath(path).lower().split(os.sep)
    )
    assert by_id["windows_temp"].selected_by_default is False
    assert by_id["windows_update"].selected_by_default is False
    assert by_id[RECYCLE_BIN_ID].selected_by_default is False
    assert by_id[STANDBY_CACHE_ID].selected_by_default is False
    assert by_id["user_temp"].selected_by_default is True


def test_scan_collects_largest_details_and_truncation(tmp_path) -> None:
    root = tmp_path / "details"
    root.mkdir()
    for size in range(1, 22):
        (root / f"{size:02}.bin").write_bytes(b"x" * size)
    target = CleanTarget("details", "Details", "System", paths=(str(root),))

    result = CleanerService([target]).scan(target)

    assert result.files == 21
    assert result.bytes == sum(range(1, 22))
    assert len(result.details) == 20
    assert result.details_truncated is True
    assert result.details[0].size == 21
    assert result.details[-1].size == 2
    assert all(isinstance(detail, ScanDetail) for detail in result.details)


def test_scan_respects_min_age_days(tmp_path) -> None:
    root = tmp_path / "aged"
    root.mkdir()
    old = root / "old.bin"
    new = root / "new.bin"
    old.write_bytes(b"o" * 100)
    new.write_bytes(b"n" * 200)
    old_time = time.time() - 3 * 86400
    os.utime(old, (old_time, old_time))
    target = CleanTarget("aged", "Aged", "System", paths=(str(root),), min_age_days=2)

    result = CleanerService([target]).scan(target)

    assert result.files == 1
    assert result.bytes == 100
    assert [detail.path for detail in result.details] == [str(old)]


def test_clean_respects_min_age_days(tmp_path) -> None:
    root = tmp_path / "aged"
    root.mkdir()
    old = root / "old.bin"
    new = root / "new.bin"
    old.write_bytes(b"o" * 100)
    new.write_bytes(b"n" * 200)
    old_time = time.time() - 3 * 86400
    os.utime(old, (old_time, old_time))
    target = CleanTarget("aged", "Aged", "System", paths=(str(root),), min_age_days=2)

    outcome = CleanerService([target]).clean(target)

    assert outcome.files_deleted == 1
    assert outcome.files_skipped == 1
    assert outcome.freed_bytes == 100
    assert outcome.partial is True
    assert not old.exists()
    assert new.exists()


def test_scan_and_clean_skip_whitelisted_paths(tmp_path) -> None:
    root = tmp_path / "whitelisted"
    root.mkdir()
    keep = root / "keep.bin"
    drop = root / "drop.bin"
    keep.write_bytes(b"k" * 64)
    drop.write_bytes(b"d" * 128)
    whitelist = CleanerWhitelist(store=tmp_path / "whitelist.json")
    assert whitelist.add(str(keep)) is True
    target = CleanTarget("cached", "Cached", "System", paths=(str(root),))
    service = CleanerService([target], whitelist)

    result = service.scan(target)
    assert result.files == 1
    assert result.bytes == 128
    assert [detail.path for detail in result.details] == [str(drop)]

    outcome = service.clean(target)
    assert outcome.files_deleted == 1
    assert outcome.files_skipped == 1
    assert keep.exists()
    assert not drop.exists()


def test_large_files_wrapper_and_preview_target(tmp_path) -> None:
    folder = tmp_path / "large"
    folder.mkdir()
    big = folder / "big.bin"
    small = folder / "small.bin"
    big.write_bytes(b"x" * 1024)
    small.write_bytes(b"x" * 10)

    found = scan_large_files(folder, 100, 10)

    assert [item.path for item in found] == [str(big)]
    assert found[0].size == 1024
    target = make_large_files_target(folder, 100, 10)
    assert target.kind == "preview"
    assert target.selected_by_default is False
    assert target.paths == (str(folder),)
    outcome = CleanerService([target]).clean(target)
    assert outcome.files_deleted == 0
    assert outcome.error is not None and "preview-only" in outcome.error
    assert big.exists()


def test_page_default_selection_follows_target_flag(qapp, tmp_path) -> None:
    target_a = CleanTarget("a", "A", "System", selected_by_default=False)
    target_b = CleanTarget("b", "B", "System")
    page = InteractiveCleaner(CleanerService([target_a, target_b]))
    assert page.table.item(0, 0).checkState() == Qt.CheckState.Unchecked
    assert page.table.item(1, 0).checkState() == Qt.CheckState.Checked


def test_page_whitelist_action_saves_patterns(qapp, tmp_path, monkeypatch) -> None:
    whitelist = CleanerWhitelist(tmp_path / "whitelist.json")
    whitelist.add("old")

    class FakeDialog:
        def __init__(self, _whitelist, _parent=None) -> None:
            self.patterns = ["new"]

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.ui.cleaner._WhitelistDialog", FakeDialog)
    page = InteractiveCleaner(CleanerService(), whitelist=whitelist)
    page.open_whitelist()
    assert whitelist.patterns == ("new",)


def test_page_schedule_action_saves_selected_targets(qapp, tmp_path, monkeypatch) -> None:
    scheduler = CleanerScheduler(tmp_path / "schedule.json")

    class FakeDialog:
        def __init__(self, _schedule, _parent=None) -> None:
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self) -> tuple[bool, str]:
            return True, "daily"

    monkeypatch.setattr("app.ui.cleaner._ScheduleDialog", FakeDialog)
    service = _two_target_service(tmp_path)
    page = InteractiveCleaner(service, scheduler=scheduler)
    page.table.item(1, 0).setCheckState(Qt.CheckState.Unchecked)
    page.open_schedule()
    assert scheduler.enabled is True
    assert scheduler.cadence == "daily"
    assert scheduler.target_ids == ("a",)


def test_page_leftovers_action_adds_targets(qapp, tmp_path, monkeypatch) -> None:
    target = CleanTarget("leftover", "Cache", "Leftovers", selected_by_default=False)
    monkeypatch.setattr("app.ui.cleaner.list_leftover_candidates", lambda: [target])
    page = InteractiveCleaner(_two_target_service(tmp_path))
    page.start_leftovers()
    assert _wait_until(qapp, lambda: page._task is None)
    assert page.table.rowCount() == 3
    assert page.table.item(2, 0).text() == "Cache"


def test_page_shows_age_and_scan_details(qapp, tmp_path) -> None:
    folder = tmp_path / "cache"
    folder.mkdir()
    big = folder / "big.bin"
    big.write_bytes(b"x" * 1024)
    old = time.time() - 4 * 86400
    os.utime(big, (old, old))
    target = CleanTarget("aged", "Aged", "System", paths=(str(folder),), min_age_days=3)
    service = CleanerService([target])
    result = service.scan(target)
    page = InteractiveCleaner(service)
    page._apply_scan([result])
    assert "3" in page.table.item(0, 0).toolTip()
    details = page.table.item(0, 2).toolTip()
    assert str(big) in details
