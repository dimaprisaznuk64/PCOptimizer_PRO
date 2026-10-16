from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from app.disk import (
    DEFAULT_MIN_SIZE,
    DiskAnalyzer,
    DiskError,
    DriveUsage,
    LargeFile,
    ScanReport,
)
from app.ui.disk import DiskPage


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------- drives ----------


def _analyzer(parts, usage_map) -> DiskAnalyzer:
    return DiskAnalyzer(
        partitions=lambda: parts,
        usage=lambda mount: usage_map[mount],
    )


def test_list_drives_skips_cdrom_and_missing_usage() -> None:
    parts = [
        SimpleNamespace(mountpoint="C:\\", fstype="NTFS", opts="fixed"),
        SimpleNamespace(mountpoint="D:\\", fstype="NTFS", opts="fixed"),
        SimpleNamespace(mountpoint="E:\\", fstype="", opts="cdrom"),
    ]
    usage = {
        "C:\\": SimpleNamespace(total=1000, used=250, free=750),
        "D:\\": SimpleNamespace(total=2000, used=1000, free=1000),
    }
    drives = _analyzer(parts, usage).list_drives()
    assert [d.mount for d in drives] == ["C:\\", "D:\\"]
    assert drives[0].percent == 25.0
    assert drives[1].percent == 50.0


def test_list_drives_usage_error_skipped() -> None:
    parts = [
        SimpleNamespace(mountpoint="X:\\", fstype="NTFS", opts="fixed"),
        SimpleNamespace(mountpoint="C:\\", fstype="NTFS", opts="fixed"),
    ]

    def usage(mount):
        if mount.startswith("X"):
            raise OSError("not ready")
        return SimpleNamespace(total=100, used=50, free=50)

    drives = DiskAnalyzer(partitions=lambda: parts, usage=usage).list_drives()
    assert [d.mount for d in drives] == ["C:\\"]


# ---------- folder scan (real tmp filesystem) ----------


@pytest.fixture()
def sample_tree(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "a.txt").write_bytes(b"a" * 100)
    (tmp_path / "docs" / "b.txt").write_bytes(b"b" * 200)
    (tmp_path / "docs" / "sub").mkdir()
    (tmp_path / "docs" / "sub" / "c.bin").write_bytes(b"c" * 700)
    (tmp_path / "video.mp4").write_bytes(b"v" * 5000)
    (tmp_path / "notes.txt").write_bytes(b"n" * 50)
    return tmp_path


def test_scan_directory_sizes_and_sorting(sample_tree) -> None:
    report = DiskAnalyzer().scan_directory(str(sample_tree))
    assert isinstance(report, ScanReport)
    by_name = {e.name: e for e in report.entries}
    assert by_name["video.mp4"].size == 5000
    assert by_name["video.mp4"].is_dir is False
    assert by_name["docs"].is_dir is True
    assert by_name["docs"].size == 100 + 200 + 700
    assert by_name["docs"].files == 3
    assert by_name["notes.txt"].size == 50

    sizes = [e.size for e in report.entries]
    assert sizes == sorted(sizes, reverse=True)
    assert report.total == 5000 + 50 + 100 + 200 + 700
    assert report.file_count == 5
    assert report.dir_count == 1
    assert report.errors == 0


def test_scan_directory_missing_raises(tmp_path) -> None:
    with pytest.raises(DiskError):
        DiskAnalyzer().scan_directory(str(tmp_path / "nope"))


def test_scan_directory_file_root_raises(tmp_path) -> None:
    target = tmp_path / "f.txt"
    target.write_bytes(b"x")
    with pytest.raises(DiskError):
        DiskAnalyzer().scan_directory(str(target))


# ---------- large files ----------


def test_find_large_files_threshold_and_limit(sample_tree, tmp_path) -> None:
    big = tmp_path / "big.iso"
    big.write_bytes(b"x" * 4096)
    analyzer = DiskAnalyzer()

    files = analyzer.find_large_files(str(sample_tree), min_bytes=4000, limit=10)
    paths = [f.path for f in files]
    assert str(big) in paths
    assert str(sample_tree / "video.mp4") in paths
    sizes = [f.size for f in files]
    assert sizes == sorted(sizes, reverse=True)

    limited = analyzer.find_large_files(str(sample_tree), min_bytes=1, limit=2)
    assert len(limited) == 2
    assert limited[0].size >= limited[1].size


def test_find_large_files_default_threshold_excludes_small(sample_tree) -> None:
    files = DiskAnalyzer().find_large_files(str(sample_tree), min_bytes=DEFAULT_MIN_SIZE)
    assert files == []


def test_find_large_files_missing_dir_raises(tmp_path) -> None:
    with pytest.raises(DiskError):
        DiskAnalyzer().find_large_files(str(tmp_path / "nope"))


# ---------- UI ----------


class FakeDiskAnalyzer(DiskAnalyzer):
    def __init__(self) -> None:
        super().__init__(partitions=lambda: [], usage=lambda m: None)
        self.drives = [
            DriveUsage(mount="C:\\", total=1000, used=250, free=750, percent=25.0),
        ]
        self.scan_calls: list[str] = []
        self.large_calls: list[tuple[str, int]] = []
        self.report = ScanReport(
            root="C:/test",
            total=12345,
            file_count=3,
            dir_count=1,
            entries=(),
            errors=1,
        )
        self.large = [
            LargeFile(path="C:/test/huge.bin", size=9 * 1024**3, modified=1700000000.0),
        ]

    def list_drives(self):
        return list(self.drives)

    def scan_directory(self, root: str) -> ScanReport:
        self.scan_calls.append(root)
        from app.disk.service import ScanEntry

        report = ScanReport(
            root=self.report.root,
            total=self.report.total,
            file_count=self.report.file_count,
            dir_count=self.report.dir_count,
            entries=(
                ScanEntry("sub", "C:/test/sub", True, 1000, 2),
                ScanEntry("file.bin", "C:/test/file.bin", False, 500, 1),
            ),
            errors=self.report.errors,
        )
        return report

    def find_large_files(self, root, min_bytes=DEFAULT_MIN_SIZE, limit=200, errors=None):
        self.large_calls.append((root, min_bytes))
        if errors is not None:
            errors.append("cannot read C:/test/locked")
        return list(self.large)


def test_disk_page_renders_drives(qapp) -> None:
    page = DiskPage(analyzer=FakeDiskAnalyzer())
    assert page.drives_row.count() == 2  # drive + stretch
    frame = page.drives_row.itemAt(0).widget()
    assert frame is not None


def test_disk_page_scan(qapp) -> None:
    analyzer = FakeDiskAnalyzer()
    page = DiskPage(analyzer=analyzer)
    page.path_input.setText("C:/test")
    page.start_scan()
    assert _wait_until(qapp, lambda: page.scan_table.rowCount() == 2)
    assert analyzer.scan_calls == ["C:/test"]
    assert page.scan_table.item(0, 0).text() == "sub"
    assert page.scan_table.item(0, 1).text() == "Folder"
    assert "1 inaccessible" in page.scan_summary.text()
    assert "3 files" in page.scan_summary.text()
    assert page.scan_button.isEnabled()


def test_disk_page_scan_double_click_navigates(qapp) -> None:
    analyzer = FakeDiskAnalyzer()
    page = DiskPage(analyzer=analyzer)
    page.path_input.setText("C:/test")
    page.start_scan()
    assert _wait_until(qapp, lambda: page.scan_table.rowCount() == 2)

    folder_item = page.scan_table.item(0, 0)
    page.scan_table.itemDoubleClicked.emit(folder_item)
    assert _wait_until(qapp, lambda: analyzer.scan_calls == ["C:/test", "C:/test/sub"])
    assert page.path_input.text() == "C:/test/sub"


def test_disk_page_large_files(qapp) -> None:
    analyzer = FakeDiskAnalyzer()
    page = DiskPage(analyzer=analyzer)
    page.path_input.setText("C:/test")
    page.threshold_combo.setCurrentIndex(0)  # 100 MB
    page.start_large_files()
    assert _wait_until(qapp, lambda: page.large_table.rowCount() == 1)
    assert analyzer.large_calls == [("C:/test", 100 * 1024**2)]
    assert page.large_table.item(0, 0).text() == "9.00GB"
    assert "1 files" in page.large_summary.text()
    assert page.large_button.isEnabled()


def test_disk_page_busy_disables_controls(qapp) -> None:
    analyzer = FakeDiskAnalyzer()
    page = DiskPage(analyzer=analyzer)
    page.path_input.setText("C:/test")
    page.start_scan()
    assert not page.scan_button.isEnabled()
    assert not page.large_button.isEnabled()
    assert not page.browse_button.isEnabled()
    assert not page.path_input.isEnabled()
    assert _wait_until(qapp, lambda: page.scan_table.rowCount() == 2)
    assert page.scan_button.isEnabled()
    assert page.path_input.isEnabled()


# ---------- walk errors ----------


def test_dir_size_counts_walk_errors(tmp_path, monkeypatch) -> None:
    import os

    root = tmp_path / "folder"
    root.mkdir()
    (root / "a.bin").write_bytes(b"x" * 32)

    real_walk = os.walk

    def flaky_walk(top, *args, **kwargs):
        onerror = kwargs.get("onerror")
        if onerror is not None:
            onerror(PermissionError(13, "access denied"))
        yield from real_walk(top, *args, **kwargs)

    monkeypatch.setattr(os, "walk", flaky_walk)
    analyzer = DiskAnalyzer(partitions=lambda: [], usage=lambda m: None)
    size, files, errors = analyzer._dir_size(root)
    assert files == 1
    assert size == 32
    assert errors >= 1  # the unreadable folder is counted, not silently dropped


def test_find_large_files_reports_walk_errors(tmp_path, monkeypatch) -> None:
    import os

    root = tmp_path / "folder"
    root.mkdir()
    (root / "huge.bin").write_bytes(b"x" * 64)

    real_walk = os.walk

    def flaky_walk(top, *args, **kwargs):
        onerror = kwargs.get("onerror")
        if onerror is not None:
            onerror(PermissionError(13, "access denied"))
        yield from real_walk(top, *args, **kwargs)

    monkeypatch.setattr(os, "walk", flaky_walk)
    errors: list[str] = []
    analyzer = DiskAnalyzer(partitions=lambda: [], usage=lambda m: None)
    found = analyzer.find_large_files(str(root), min_bytes=1, limit=10, errors=errors)
    assert found
    assert errors  # the skipped folder is reported to the caller
