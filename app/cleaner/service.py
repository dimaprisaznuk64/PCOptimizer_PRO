from __future__ import annotations

import ctypes
import glob
import os
import subprocess
from dataclasses import dataclass
from typing import Sequence

RECYCLE_BIN_ID = "recycle_bin"


@dataclass(frozen=True, slots=True)
class CleanTarget:
    id: str
    name: str
    category: str
    kind: str = "files"
    paths: tuple[str, ...] = ()
    note: str = ""


@dataclass(frozen=True, slots=True)
class ScanResult:
    target_id: str
    files: int
    bytes: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CleanOutcome:
    target_id: str
    freed_bytes: int
    files_deleted: int
    files_skipped: int
    error: str | None = None


def _summarize(errors: list[str]) -> str | None:
    if not errors:
        return None
    unique = list(dict.fromkeys(errors))
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
        ),
        CleanTarget(
            "windows_update",
            "Windows Update downloads",
            "System",
            paths=(os.path.join(windir, "SoftwareDistribution", "Download"),),
            note="needs administrator for full access",
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
    ]

    existing: list[CleanTarget] = []
    for target in candidates:
        if target.paths and _expand(target.paths):
            existing.append(target)

    existing.append(
        CleanTarget(
            RECYCLE_BIN_ID,
            "Recycle Bin",
            "System",
            kind="recycle",
            note="empties the bin on all drives",
        )
    )
    return existing


class CleanerService:
    def __init__(self, targets: Sequence[CleanTarget] | None = None) -> None:
        self._targets = list(targets) if targets is not None else default_targets()

    @property
    def targets(self) -> list[CleanTarget]:
        return list(self._targets)

    def get(self, target_id: str) -> CleanTarget | None:
        for target in self._targets:
            if target.id == target_id:
                return target
        return None

    def scan(self, target: CleanTarget) -> ScanResult:
        if target.kind == "recycle":
            return self._scan_recycle(target)
        return self._scan_files(target)

    def scan_all(self) -> list[ScanResult]:
        return [self.scan(target) for target in self._targets]

    def clean(self, target: CleanTarget, known_bytes: int = 0) -> CleanOutcome:
        if target.kind == "recycle":
            return self._empty_recycle(target, known_bytes)
        return self._clean_files(target)

    def _scan_files(self, target: CleanTarget) -> ScanResult:
        total_files = 0
        total_bytes = 0
        errors: list[str] = []
        for root in _expand(target.paths):
            if not os.path.exists(root):
                continue
            if os.path.isfile(root):
                try:
                    total_bytes += os.stat(root, follow_symlinks=False).st_size
                    total_files += 1
                except OSError as e:
                    errors.append(str(e))
                continue
            for dirpath, _dirnames, filenames in os.walk(root, onerror=errors.append, followlinks=False):
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    try:
                        total_bytes += os.stat(path, follow_symlinks=False).st_size
                        total_files += 1
                    except OSError as e:
                        errors.append(str(e))
        return ScanResult(target.id, total_files, total_bytes, _summarize(errors))

    def _clean_files(self, target: CleanTarget) -> CleanOutcome:
        freed = 0
        deleted = 0
        skipped = 0
        errors: list[str] = []
        for root in _expand(target.paths):
            if not os.path.exists(root):
                continue
            if os.path.isfile(root):
                try:
                    st = os.stat(root, follow_symlinks=False)
                    os.unlink(root)
                except OSError as e:
                    skipped += 1
                    errors.append(str(e))
                else:
                    freed += st.st_size
                    deleted += 1
                continue
            for dirpath, _dirnames, filenames in os.walk(root, topdown=False, followlinks=False):
                for filename in filenames:
                    path = os.path.join(dirpath, filename)
                    try:
                        st = os.stat(path, follow_symlinks=False)
                        os.unlink(path)
                    except OSError as e:
                        skipped += 1
                        errors.append(str(e))
                    else:
                        freed += st.st_size
                        deleted += 1
                if dirpath != root:
                    try:
                        os.rmdir(dirpath)
                    except OSError:
                        pass
        error = None
        if skipped and not deleted:
            error = _summarize(errors) or "nothing could be deleted (access denied?)"
        elif skipped:
            error = None
        return CleanOutcome(target.id, freed, deleted, skipped, error)

    @staticmethod
    def _scan_recycle(target: CleanTarget) -> ScanResult:
        script = (
            "$rb=(New-Object -ComObject Shell.Application).NameSpace(0xA);"
            "$its=@($rb.Items());"
            "$sum=($its | Measure-Object -Property Size -Sum).Sum;"
            'Write-Output ("{0};{1}" -f $its.Count, [int64]$sum)'
        )
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=30,
            )
        except Exception as e:
            return ScanResult(target.id, 0, 0, str(e))
        if out.returncode != 0:
            return ScanResult(target.id, 0, 0, (out.stderr or "powershell failed").strip()[:200])
        line = (out.stdout.strip().splitlines() or [""])[-1]
        try:
            count_text, bytes_text = line.split(";")
            return ScanResult(target.id, int(count_text), int(bytes_text))
        except ValueError:
            return ScanResult(target.id, 0, 0, f"unexpected output: {line[:100]}")

    @staticmethod
    def _empty_recycle(target: CleanTarget, known_bytes: int) -> CleanOutcome:
        try:
            shell32 = ctypes.windll.shell32
            shell32.SHEmptyRecycleBinW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_uint]
            shell32.SHEmptyRecycleBinW.restype = ctypes.c_long
            rc = shell32.SHEmptyRecycleBinW(None, None, 0x1 | 0x2 | 0x4)
        except Exception as e:
            return CleanOutcome(target.id, 0, 0, 0, str(e))
        if rc < 0:
            return CleanOutcome(target.id, 0, 0, 0, f"SHEmptyRecycleBin failed (0x{rc & 0xFFFFFFFF:08X})")
        return CleanOutcome(target.id, known_bytes, 0, 0)
