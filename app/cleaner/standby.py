from __future__ import annotations

import ctypes
from ctypes import wintypes

from app.logs import get_logger

log = get_logger("cleaner.standby")

_SYSTEM_MEMORY_LIST_INFORMATION = 80
_MEMORY_PURGE_STANDBY_LIST = 4


class _SystemMemoryListCommand(ctypes.Structure):
    _fields_ = [("Command", ctypes.c_ulong)]


class StandbyListError(Exception):
    """Raised when the standby memory list cannot be purged."""


def purge_standby_list() -> bool:
    """Clear the standby memory list using Win32 API."""
    try:
        ntdll = ctypes.WinDLL("ntdll", use_last_error=True)
        ntdll.NtSetSystemInformation.restype = wintypes.LONG
        ntdll.NtSetSystemInformation.argtypes = [
            wintypes.LONG,
            ctypes.c_void_p,
            wintypes.ULONG,
        ]
        cmd = _SystemMemoryListCommand(_MEMORY_PURGE_STANDBY_LIST)
        rc = ntdll.NtSetSystemInformation(
            _SYSTEM_MEMORY_LIST_INFORMATION,
            ctypes.byref(cmd),
            ctypes.sizeof(cmd),
        )
        if rc != 0:
            raise StandbyListError(f"NtSetSystemInformation failed (0x{rc & 0xFFFFFFFF:08X})")
        log.info("standby memory list purged")
        return True
    except StandbyListError:
        raise
    except Exception as exc:
        raise StandbyListError(str(exc)) from exc
