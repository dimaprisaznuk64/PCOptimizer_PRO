from __future__ import annotations

import ctypes
import sys
from collections.abc import Callable
from dataclasses import dataclass

StatusFn = Callable[[], tuple[int, int] | None]


@dataclass(frozen=True, slots=True)
class CommitCharge:
    limit: int
    available: int
    used: int


class _MemoryStatusEx(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _global_memory_status() -> tuple[int, int] | None:
    if sys.platform != "win32":
        return None
    win_dll = getattr(ctypes, "WinDLL", None)
    if win_dll is None:
        return None
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(status)
    kernel32 = win_dll("kernel32", use_last_error=True)
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return int(status.ullTotalPageFile), int(status.ullAvailPageFile)


def read_commit_charge(status_fn: StatusFn | None = None) -> CommitCharge | None:
    raw = (_global_memory_status if status_fn is None else status_fn)()
    if raw is None:
        return None
    limit, available = raw
    if limit <= 0:
        return None
    available = min(max(available, 0), limit)
    return CommitCharge(limit=limit, available=available, used=limit - available)
