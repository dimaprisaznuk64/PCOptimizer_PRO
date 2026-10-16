from __future__ import annotations

import os
import stat as stat_mod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

GB = 1024**3
DEFAULT_MIN_SIZE = 500 * 1024**2
DEFAULT_LIMIT = 200


class DiskError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DriveUsage:
    mount: str
    total: int
    used: int
    free: int
    percent: float


@dataclass(frozen=True, slots=True)
class ScanEntry:
    name: str
    path: str
    is_dir: bool
    size: int
    files: int


@dataclass(frozen=True, slots=True)
class ScanReport:
    root: str
    total: int
    file_count: int
    dir_count: int
    entries: tuple[ScanEntry, ...]
    errors: int


@dataclass(frozen=True, slots=True)
class LargeFile:
    path: str
    size: int
    modified: float


def _is_junction(path: Path) -> bool:
    method = getattr(path, "is_junction", None)
    if method is None:
        return False
    try:
        return bool(method())
    except OSError:
        return False


def _skip(path: Path) -> bool:
    try:
        return path.is_symlink() or _is_junction(path)
    except OSError:
        return True


class DiskAnalyzer:
    def __init__(
        self,
        *,
        partitions: Callable[[], Sequence] | None = None,
        usage: Callable[[str], object] | None = None,
    ) -> None:
        self._partitions = partitions or self._default_partitions
        self._usage = usage or self._default_usage

    # ---------- drives ----------

    def list_drives(self) -> list[DriveUsage]:
        drives: list[DriveUsage] = []
        for part in self._partitions():
            mount = getattr(part, "mountpoint", "") or ""
            opts = str(getattr(part, "opts", "") or "").lower()
            if not mount or "cdrom" in opts:
                continue
            try:
                u = self._usage(mount)
            except OSError:
                continue
            total = int(u.total)
            if total <= 0:
                continue
            drives.append(
                DriveUsage(
                    mount=mount,
                    total=total,
                    used=int(u.used),
                    free=int(u.free),
                    percent=round(100.0 * int(u.used) / total, 1),
                )
            )
        return drives

    # ---------- folder scan ----------

    def scan_directory(self, root: str) -> ScanReport:
        path = Path(root)
        if not path.is_dir():
            raise DiskError(f"not a directory: {root}")

        entries: list[ScanEntry] = []
        errors = 0
        try:
            children = list(os.scandir(path))
        except OSError as e:
            raise DiskError(f"cannot read {root}: {e}") from e

        for child in children:
            child_path = Path(child.path)
            if _skip(child_path):
                continue
            try:
                if child.is_dir(follow_symlinks=False):
                    size, files, scan_errors = self._dir_size(child_path)
                    errors += scan_errors
                    entries.append(ScanEntry(child.name, str(child_path), True, size, files))
                elif child.is_file(follow_symlinks=False):
                    size = child.stat(follow_symlinks=False).st_size
                    entries.append(ScanEntry(child.name, str(child_path), False, size, 1))
            except OSError:
                errors += 1

        entries.sort(key=lambda e: (-e.size, e.name.lower()))
        total = sum(e.size for e in entries)
        file_count = sum(e.files for e in entries)
        dir_count = sum(1 for e in entries if e.is_dir)
        return ScanReport(
            root=str(path),
            total=total,
            file_count=file_count,
            dir_count=dir_count,
            entries=tuple(entries),
            errors=errors,
        )

    def _dir_size(self, folder: Path) -> tuple[int, int, int]:
        size = 0
        files = 0
        errors = 0

        def _onerror(_error: OSError) -> None:
            nonlocal errors
            errors += 1

        for dirpath, dirnames, filenames in os.walk(folder, followlinks=False, onerror=_onerror):
            dirnames[:] = [d for d in dirnames if not _skip(Path(dirpath) / d)]
            for name in filenames:
                file_path = Path(dirpath) / name
                if _skip(file_path):
                    continue
                try:
                    st = file_path.stat()
                    if stat_mod.S_ISREG(st.st_mode):
                        size += st.st_size
                        files += 1
                except OSError:
                    errors += 1
        return size, files, errors

    # ---------- large files ----------

    def find_large_files(
        self,
        root: str,
        min_bytes: int = DEFAULT_MIN_SIZE,
        limit: int = DEFAULT_LIMIT,
        errors: list[str] | None = None,
    ) -> list[LargeFile]:
        path = Path(root)
        if not path.is_dir():
            raise DiskError(f"not a directory: {root}")

        def _onerror(error: OSError) -> None:
            if errors is not None:
                errors.append(str(error))

        found: list[LargeFile] = []
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False, onerror=_onerror):
            dirnames[:] = [d for d in dirnames if not _skip(Path(dirpath) / d)]
            for name in filenames:
                file_path = Path(dirpath) / name
                if _skip(file_path):
                    continue
                try:
                    st = file_path.stat()
                except OSError:
                    continue
                if not stat_mod.S_ISREG(st.st_mode):
                    continue
                if st.st_size >= min_bytes:
                    found.append(LargeFile(str(file_path), st.st_size, st.st_mtime))

        found.sort(key=lambda f: (-f.size, f.path.lower()))
        return found[:limit]

    # ---------- defaults ----------

    @staticmethod
    def _default_partitions():
        import psutil

        return psutil.disk_partitions(all=False)

    @staticmethod
    def _default_usage(mount: str):
        import psutil

        return psutil.disk_usage(mount)
