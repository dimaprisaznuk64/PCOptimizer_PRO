from __future__ import annotations

import ctypes
import glob
import heapq
import os
import re
import subprocess
import time
from collections.abc import Sequence
from dataclasses import dataclass

from app.cleaner.whitelist import CleanerWhitelist
from app.winpaths import POWERSHELL_PATH, PS_UTF8_PREFIX, decode_process_output

RECYCLE_BIN_ID = "recycle_bin"
STANDBY_CACHE_ID = "standby_cache"

_DETAIL_LIMIT = 20
_FORBIDDEN_COMPONENTS = frozenset({"winsxs", "installer"})
_DRIVE_ROOT_RE = re.compile(r"^[a-zA-Z]:[\\/]?$")


def _protected_roots() -> set[str]:
    """Paths that must never be cleaned wholesale (drive/profile roots)."""
    env = os.environ
    system_root = env.get("SystemRoot") or env.get("WINDIR") or r"C:\Windows"
    candidates = [
        system_root,
        os.path.join(system_root, "System32"),
        env.get("ProgramFiles", r"C:\Program Files"),
        env.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        env.get("ProgramData", r"C:\ProgramData"),
        env.get("USERPROFILE", ""),
        env.get("LOCALAPPDATA", ""),
        env.get("APPDATA", ""),
        os.path.expanduser("~"),
    ]
    return {os.path.normcase(os.path.normpath(c)) for c in candidates if c}


def is_safe_root(path: str) -> bool:
    """Reject obviously dangerous cleanup roots.

    The cleaner deletes everything under a ``CleanTarget`` path, so a bad path
    (drive root, the whole user profile, an ``AppData`` root, a junction) must
    never be accepted — this is a safety net independent of the caller.
    """
    if not path:
        return False
    raw = str(path).strip()
    # Catch drive roots ("C:", "C:\", "C:/") before abspath resolves them to a
    # drive-relative current directory.
    if _DRIVE_ROOT_RE.match(raw):
        return False
    try:
        normalized = os.path.normcase(os.path.normpath(os.path.abspath(raw)))
    except (OSError, ValueError):
        return False
    drive, tail = os.path.splitdrive(normalized)
    if drive and tail in ("", os.sep):
        return False
    if normalized in _protected_roots():
        return False
    is_link = getattr(os.path, "islink", lambda _p: False)
    is_junction = getattr(os.path, "isjunction", lambda _p: False)
    try:
        if is_link(path) or is_junction(path):
            return False
    except OSError:
        return False
    return True


def _is_default_target_path(path: str) -> bool:
    normalized = os.path.normcase(os.path.normpath(path)).replace("/", os.sep)
    parts = {part for part in normalized.split(os.sep) if part}
    if parts & _FORBIDDEN_COMPONENTS:
        return False
    return is_safe_root(path)


@dataclass(frozen=True, slots=True)
class CleanTarget:
    id: str
    name: str
    category: str
    kind: str = "files"
    paths: tuple[str, ...] = ()
    note: str = ""
    selected_by_default: bool = True
    min_age_days: int = 0


@dataclass(frozen=True, slots=True)
class ScanDetail:
    path: str
    size: int
    modified: float


@dataclass(frozen=True, slots=True)
class ScanResult:
    target_id: str
    files: int
    bytes: int
    error: str | None = None
    details: tuple[ScanDetail, ...] = ()
    details_truncated: bool = False


@dataclass(frozen=True, slots=True)
class CleanOutcome:
    target_id: str
    freed_bytes: int
    files_deleted: int
    files_skipped: int
    error: str | None = None
    partial: bool = False


def _summarize(errors: list[str]) -> str | None:
    if not errors:
        return None
    unique = list(dict.fromkeys(str(e) for e in errors))
    head = "; ".join(unique[:3])
    extra = len(unique) - 3
    return f"{head} (+{extra} more)" if extra > 0 else head


def _expand(paths: Sequence[str]) -> list[str]:
    out: list[str] = []
    for path in paths:
        if any(ch in path for ch in "*?["):
            out.extend(glob.glob(path))
        else:
            out.append(path)
    return out


def default_targets() -> list[CleanTarget]:
    env = os.environ
    local = env.get("LOCALAPPDATA", "")
    temp = env.get("TEMP", "")
    windir = env.get("WINDIR", r"C:\Windows")

    candidates: list[CleanTarget] = [
        CleanTarget(
            "user_temp",
            "User temp files",
            "System",
            paths=(temp,),
            note="%TEMP%",
        ),
        CleanTarget(
            "windows_temp",
            "Windows temp files",
            "System",
            paths=(os.path.join(windir, "Temp"),),
            note="needs administrator for full access",
            selected_by_default=False,
        ),
        CleanTarget(
            "windows_update",
            "Windows Update downloads",
            "System",
            paths=(os.path.join(windir, "SoftwareDistribution", "Download"),),
            note="needs administrator for full access",
            selected_by_default=False,
        ),
        CleanTarget(
            "chrome_cache",
            "Google Chrome cache",
            "Browser",
            paths=(
                os.path.join(local, "Google", "Chrome", "User Data", "Default", "Cache"),
                os.path.join(local, "Google", "Chrome", "User Data", "Default", "Code Cache"),
                os.path.join(local, "Google", "Chrome", "User Data", "Default", "GPUCache"),
                os.path.join(local, "Google", "Chrome", "User Data", "Profile *", "Cache"),
                os.path.join(local, "Google", "Chrome", "User Data", "Profile *", "Code Cache"),
            ),
        ),
        CleanTarget(
            "edge_cache",
            "Microsoft Edge cache",
            "Browser",
            paths=(
                os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Cache"),
                os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "Code Cache"),
                os.path.join(local, "Microsoft", "Edge", "User Data", "Default", "GPUCache"),
                os.path.join(local, "Microsoft", "Edge", "User Data", "Profile *", "Cache"),
                os.path.join(local, "Microsoft", "Edge", "User Data", "Profile *", "Code Cache"),
            ),
        ),
        CleanTarget(
            "firefox_cache",
            "Mozilla Firefox cache",
            "Browser",
            paths=(os.path.join(local, "Mozilla", "Firefox", "Profiles", "*", "cache2"),),
        ),
        CleanTarget(
            "shader_cache",
            "GPU shader caches",
            "GPU",
            paths=(
                os.path.join(local, "NVIDIA", "DXCache"),
                os.path.join(local, "NVIDIA", "GLCache"),
                os.path.join(local, "NVIDIA", "NV_Cache"),
                os.path.join(local, "AMD", "DxCache"),
                os.path.join(local, "AMD", "GLCache"),
                os.path.join(local, "D3DSCache"),
            ),
            note="games/apps rebuild them automatically",
        ),
        CleanTarget(
            "thumbnail_cache",
            "Thumbnail cache",
            "System",
            paths=(os.path.join(local, "Microsoft", "Windows", "Explorer", "thumbcache_*.db"),),
            note="locked while Explorer is running",
        ),
        CleanTarget(
            "wer_reports",
            "Windows Error Reporting cache",
            "System",
            paths=(
                os.path.join(local, "Microsoft", "Windows", "WER", "ReportQueue"),
                os.path.join(local, "Microsoft", "Windows", "WER", "ReportArchive"),
            ),
            note="cached crash reports only",
        ),
        CleanTarget(
            "crash_dumps",
            "Crash dumps",
            "System",
            paths=(os.path.join(local, "CrashDumps"),),
            note="process crash dump files",
        ),
        CleanTarget(
            "pip_cache",
            "pip cache",
            "Development",
            paths=(os.path.join(local, "pip", "Cache"),),
            note="downloaded package cache",
        ),
        CleanTarget(
            "npm_cache",
            "npm cache",
            "Development",
            paths=(
                os.path.join(local, "npm-cache", "_cacache"),
                os.path.join(env.get("APPDATA", ""), "npm-cache", "_cacache"),
            ),
            note="npm content-addressable cache",
        ),
    ]

    existing: list[CleanTarget] = []
    for target in candidates:
        if any(_is_default_target_path(path) for path in _expand(target.paths)):
            existing.append(target)

    existing.append(
        CleanTarget(
            RECYCLE_BIN_ID,
            "Recycle Bin",
            "System",
            kind="recycle",
            note="empties the bin on all drives",
            selected_by_default=False,
        )
    )
    existing.append(
        CleanTarget(
            STANDBY_CACHE_ID,
            "Standby RAM cache",
            "Memory",
            kind="memory",
            note="clears cached memory used by Windows for speed",
            selected_by_default=False,
        )
    )
    return existing


class CleanerService:
    def __init__(
        self,
        targets: Sequence[CleanTarget] | None = None,
        whitelist: CleanerWhitelist | None = None,
    ) -> None:
        self._targets = list(targets) if targets is not None else default_targets()
        self.whitelist = whitelist if whitelist is not None else CleanerWhitelist()

    @property
    def targets(self) -> list[CleanTarget]:
        return list(self._targets)

    def get(self, target_id: str) -> CleanTarget | None:
        for target in self._targets:
            if target.id == target_id:
                return target
        return None

    @staticmethod
    def _too_recent(st: os.stat_result, min_age_days: int) -> bool:
        return min_age_days > 0 and time.time() - st.st_mtime < min_age_days * 86400

    def scan(self, target: CleanTarget) -> ScanResult:
        if target.kind == "recycle":
            return self._scan_recycle(target)
        return self._scan_files(target)

    def scan_all(self) -> list[ScanResult]:
        return [self.scan(target) for target in self._targets]

    def clean(self, target: CleanTarget, known_bytes: int = 0, known_files: int = 0) -> CleanOutcome:
        if target.kind == "preview":
            return CleanOutcome(target.id, 0, 0, 0, "preview-only target", False)
        if target.kind == "recycle":
            return self._empty_recycle(target, known_bytes, known_files)
        if target.kind == "memory":
            return self._purge_memory(target)
        return self._clean_files(target)

    def _scan_files(self, target: CleanTarget) -> ScanResult:
        total_files = 0
        total_bytes = 0
        errors: list[str] = []
        largest: list[tuple[int, str, float]] = []

        def consider(path: str, st: os.stat_result) -> None:
            nonlocal total_files, total_bytes
            total_files += 1
            total_bytes += st.st_size
            item = (st.st_size, path, st.st_mtime)
            if len(largest) < _DETAIL_LIMIT:
                heapq.heappush(largest, item)
            elif item > largest[0]:
                heapq.heapreplace(largest, item)

        for root in _expand(target.paths):
            if not is_safe_root(root):
                errors.append(f"refusing unsafe path: {root}")
                continue
            if self.whitelist.is_excluded(root):
                continue
            if not os.path.exists(root):
                continue
            if os.path.isfile(root):
                try:
                    st = os.stat(root, follow_symlinks=False)
                except OSError as e:
                    errors.append(str(e))
                    continue
                if not self._too_recent(st, target.min_age_days):
                    consider(root, st)
                continue
            for dirpath, dirnames, filenames in os.walk(
                root,
                onerror=lambda e: errors.append(str(e)),
                followlinks=False,
            ):
                dirnames[:] = [
                    name
                    for name in dirnames
                    if not self.whitelist.is_excluded(os.path.join(dirpath, name))
                ]
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    if self.whitelist.is_excluded(path):
                        continue
                    try:
                        st = os.stat(path, follow_symlinks=False)
                    except OSError as e:
                        errors.append(str(e))
                        continue
                    if not self._too_recent(st, target.min_age_days):
                        consider(path, st)
        details = tuple(ScanDetail(path, size, modified) for size, path, modified in sorted(largest, reverse=True))
        return ScanResult(
            target.id,
            total_files,
            total_bytes,
            _summarize(errors),
            details,
            total_files > len(details),
        )

    def _clean_files(self, target: CleanTarget) -> CleanOutcome:
        freed = 0
        deleted = 0
        skipped = 0
        rule_skipped = 0
        errors: list[str] = []
        walk_errors: list[str] = []
        refused: list[str] = []
        for root in _expand(target.paths):
            if not is_safe_root(root):
                refused.append(root)
                continue
            if self.whitelist.is_excluded(root):
                continue
            if not os.path.exists(root):
                continue
            if os.path.isfile(root):
                try:
                    st = os.stat(root, follow_symlinks=False)
                except OSError as e:
                    skipped += 1
                    errors.append(str(e))
                    continue
                if self._too_recent(st, target.min_age_days) or self.whitelist.is_excluded(root):
                    skipped += 1
                    rule_skipped += 1
                    continue
                try:
                    os.unlink(root)
                except OSError as e:
                    skipped += 1
                    errors.append(str(e))
                else:
                    freed += st.st_size
                    deleted += 1
                continue
            for dirpath, _dirnames, filenames in os.walk(
                root,
                topdown=False,
                onerror=lambda e: walk_errors.append(str(e)),
                followlinks=False,
            ):
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    try:
                        st = os.stat(path, follow_symlinks=False)
                    except OSError as e:
                        skipped += 1
                        errors.append(str(e))
                        continue
                    if self._too_recent(st, target.min_age_days) or self.whitelist.is_excluded(path):
                        skipped += 1
                        rule_skipped += 1
                        continue
                    try:
                        os.unlink(path)
                    except OSError as e:
                        skipped += 1
                        errors.append(str(e))
                    else:
                        freed += st.st_size
                        deleted += 1
                if dirpath != root and not self.whitelist.is_excluded(dirpath):
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass
        error = None
        if skipped and not deleted:
            if errors:
                error = _summarize(errors)
            elif rule_skipped:
                error = "nothing could be deleted (excluded by age or whitelist)"
            else:
                error = "nothing could be deleted (access denied?)"
        elif skipped:
            error = None
        if refused:
            note = f"refused unsafe paths: {_summarize(refused)}"
            error = f"{error}; {note}" if error else note
        if walk_errors:
            # Some directories could not be traversed — the result is partial
            # and the user must know some files were never checked.
            note = f"some folders were skipped: {_summarize(walk_errors)}"
            error = f"{error}; {note}" if error else note
        # A partial clean (something left unchecked) is not a hard failure, but
        # the caller must be able to tell the result was incomplete — this
        # includes walk errors even when nothing at all could be deleted.
        partial = bool(walk_errors) or bool(refused) or (deleted > 0 and skipped > 0) or bool(rule_skipped)
        return CleanOutcome(target.id, freed, deleted, skipped, error, partial)

    @staticmethod
    def _scan_recycle(target: CleanTarget) -> ScanResult:
        script = PS_UTF8_PREFIX + (
            "$rb=(New-Object -ComObject Shell.Application).NameSpace(0xA);"
            "$its=@($rb.Items());"
            "$sum=($its | Measure-Object -Property Size -Sum).Sum;"
            'Write-Output ("{0};{1}" -f $its.Count, [int64]$sum)'
        )
        try:
            out = subprocess.run(
                [POWERSHELL_PATH, "-NoProfile", "-Command", script],
                capture_output=True,
                text=False,
                timeout=30,
            )
        except Exception as e:
            return ScanResult(target.id, 0, 0, str(e))
        if out.returncode != 0:
            stderr = decode_process_output(out.stderr or b"")
            return ScanResult(target.id, 0, 0, (stderr or "powershell failed").strip()[:200])
        stdout = decode_process_output(out.stdout or b"")
        line = (stdout.strip().splitlines() or [""])[-1]
        try:
            count_text, bytes_text = line.split(";")
            return ScanResult(target.id, int(count_text), int(bytes_text))
        except ValueError:
            return ScanResult(target.id, 0, 0, f"unexpected output: {line[:100]}")

    @staticmethod
    def _purge_memory(target: CleanTarget) -> CleanOutcome:
        from app.cleaner.standby import StandbyListError, purge_standby_list
        try:
            purge_standby_list()
            return CleanOutcome(target.id, 0, 0, 0, error=None, partial=False)
        except StandbyListError as e:
            return CleanOutcome(target.id, 0, 0, 0, error=str(e), partial=False)

    @staticmethod
    def _empty_recycle(target: CleanTarget, known_bytes: int, known_files: int = 0) -> CleanOutcome:
        try:
            shell32 = ctypes.windll.shell32
            shell32.SHEmptyRecycleBinW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
            shell32.SHEmptyRecycleBinW.restype = ctypes.c_long
            rc = shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
        except Exception as e:
            return CleanOutcome(target.id, 0, 0, 0, str(e))
        if rc < 0:
            return CleanOutcome(target.id, 0, 0, 0, f"SHEmptyRecycleBin failed (0x{rc & 0xFFFFFFFF:08X})")
        # The API reports no counts, so we surface the pre-scan estimate (the
        # bin was emptied, but the exact deleted count is not confirmable).
        return CleanOutcome(target.id, known_bytes, known_files, 0)
