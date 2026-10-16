"""Diagnostics: read-only drive health (SMART-style) and Windows event log.

Drive data is read with PowerShell (``Get-PhysicalDisk`` +
``Get-StorageReliabilityCounter``), which works for a standard user and exposes
temperature/wear where the raw WMI storage classes often return nothing.
Windows events come from ``Get-WinEvent`` parsed from JSON. The subprocess
``run`` callable is injectable so the module can be unit-tested without touching
the real machine.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

HEALTH_NAMES = {
    "healthy": "healthy",
    "warning": "warning",
    "unhealthy": "unhealthy",
}

LEVEL_NAMES = {
    1: "critical",
    2: "error",
    3: "warning",
    4: "information",
    5: "verbose",
}

DEFAULT_LOG = "System"
DEFAULT_LEVELS = (1, 2)
DEFAULT_LIMIT = 40
ALLOWED_LOGS = ("System", "Application")

# PowerShell 5.1 writes console output in the OEM code page (cp866/cp1251 for
# Cyrillic locales). Force UTF-8 so non-ASCII event messages survive the pipe.
PS_UTF8_PREFIX = "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"

DISK_LIST_SCRIPT = (
    "Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,"
    "@{n='MediaType';e={$_.MediaType.ToString()}},Size,"
    "@{n='HealthStatus';e={$_.HealthStatus.ToString()}},SerialNumber | "
    "ConvertTo-Json -Compress"
)
RELIABILITY_SCRIPT = (
    "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object "
    "DeviceId,Temperature,Wear,PowerOnHours,ReadErrorsTotal,WriteErrorsTotal | "
    "ConvertTo-Json -Compress"
)

_WS_RE = re.compile(r"\s+")


class DiagnosticsError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DiskHealth:
    name: str = ""
    media: str = ""
    size_bytes: int = 0
    health: str = "unknown"
    temperature_c: int | None = None
    wear_percent: int | None = None
    power_on_hours: int | None = None
    read_errors: int | None = None
    write_errors: int | None = None
    serial: str = ""


@dataclass(frozen=True, slots=True)
class EventEntry:
    time: str = ""
    level: int = 0
    level_name: str = ""
    source: str = ""
    event_id: int = 0
    message: str = ""


@dataclass(frozen=True, slots=True)
class DiagnosticsReport:
    disks: tuple[DiskHealth, ...] = ()
    events: tuple[EventEntry, ...] = ()
    errors: tuple[str, ...] = field(default=())


# ---------- helpers ----------


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _positive_int(value: Any) -> int | None:
    """Int or ``None`` for missing values; 0/negative is treated as "unknown"."""
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _counter_int(value: Any) -> int | None:
    """Like :func:`_positive_int` but keeps a genuine 0 (e.g. zero errors)."""
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _health(value: Any) -> str:
    return HEALTH_NAMES.get(_text(value).lower(), "unknown")


def _clean_message(text: str, limit: int = 400) -> str:
    collapsed = _WS_RE.sub(" ", text).strip()
    if len(collapsed) > limit:
        return collapsed[: limit - 1].rstrip() + "…"
    return collapsed


def _load_rows(output: str) -> list[dict[str, Any]]:
    """Parse a ``ConvertTo-Json`` payload that may be an object, array or empty."""
    text = output.strip().lstrip("\ufeff")
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def parse_events(output: str) -> list[EventEntry]:
    """Parse ``Get-WinEvent | ConvertTo-Json`` output into events."""
    entries: list[EventEntry] = []
    for row in _load_rows(output):
        level = _to_int(row.get("Level"))
        entries.append(
            EventEntry(
                time=_text(row.get("Time")),
                level=level,
                level_name=LEVEL_NAMES.get(level, ""),
                source=_text(row.get("ProviderName")),
                event_id=_to_int(row.get("Id")),
                message=_clean_message(_text(row.get("Message"))),
            )
        )
    return entries


# ---------- defaults ----------


def _decode_output(raw: bytes) -> str:
    """Decode captured PowerShell bytes: UTF-8 first (we force UTF-8 console),
    then the OEM console code page (cp866 on Cyrillic Windows) and cp1251 as a
    safety net. cp866 is tried before cp1251 because a redirected PowerShell
    console emits the OEM, not the ANSI, code page."""
    if not raw:
        return ""
    import locale

    candidates = ["utf-8", "cp866", "cp1251", locale.getpreferredencoding(False)]
    seen: set[str] = set()
    for enc in candidates:
        if not enc or enc.lower() in seen:
            continue
        seen.add(enc.lower())
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _default_run(args: Sequence[str], timeout: float) -> tuple[int, str]:
    import subprocess

    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        proc = subprocess.run(
            list(args),
            capture_output=True,
            timeout=timeout,
            creationflags=creationflags,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, str(e)
    raw = (proc.stdout or b"") + (proc.stderr or b"")
    return proc.returncode, _decode_output(raw)


def _event_script(log_name: str, levels: Sequence[int], limit: int) -> list[str]:
    """PowerShell command that dumps matching events as JSON."""
    level_arg = ",".join(str(int(lv)) for lv in levels)
    script = (
        PS_UTF8_PREFIX
        + "$ErrorActionPreference='SilentlyContinue';"
        "$ev = Get-WinEvent -FilterHashtable "
        f"@{{LogName='{log_name}';Level={level_arg}}} -MaxEvents {limit};"
        "@($ev) | Select-Object "
        "@{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},"
        "Level,ProviderName,Id,Message | ConvertTo-Json -Depth 4 -Compress"
    )
    return ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


class DiagnosticsService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
    ) -> None:
        self._run = run or _default_run

    # ---------- public ----------

    def report(
        self,
        log_name: str = DEFAULT_LOG,
        levels: Sequence[int] = DEFAULT_LEVELS,
        limit: int = DEFAULT_LIMIT,
    ) -> DiagnosticsReport:
        errors: list[str] = []
        return DiagnosticsReport(
            disks=tuple(self.disk_health(errors)),
            events=tuple(self.events(log_name, levels, limit, errors)),
            errors=tuple(errors),
        )

    def disk_health(self, errors: list[str] | None = None) -> list[DiskHealth]:
        bucket = errors if errors is not None else []
        counters: dict[str, dict[str, Any]] = {}
        for row in self._rows(bucket, "Reliability", RELIABILITY_SCRIPT):
            device_id = _text(row.get("DeviceId"))
            if device_id:
                counters[device_id] = row
        disks: list[DiskHealth] = []
        for row in self._rows(bucket, "Drives", DISK_LIST_SCRIPT):
            counter = counters.get(_text(row.get("DeviceId")), {})
            disks.append(
                DiskHealth(
                    name=_text(row.get("FriendlyName")),
                    media=_text(row.get("MediaType")),
                    size_bytes=_to_int(row.get("Size")),
                    health=_health(row.get("HealthStatus")),
                    temperature_c=_positive_int(counter.get("Temperature")),
                    wear_percent=_counter_int(counter.get("Wear")),
                    power_on_hours=_positive_int(counter.get("PowerOnHours")),
                    read_errors=_counter_int(counter.get("ReadErrorsTotal")),
                    write_errors=_counter_int(counter.get("WriteErrorsTotal")),
                    serial=_text(row.get("SerialNumber")),
                )
            )
        return disks

    def events(
        self,
        log_name: str = DEFAULT_LOG,
        levels: Sequence[int] = DEFAULT_LEVELS,
        limit: int = DEFAULT_LIMIT,
        errors: list[str] | None = None,
    ) -> list[EventEntry]:
        bucket = errors if errors is not None else []
        log = log_name if log_name in ALLOWED_LOGS else DEFAULT_LOG
        level_list = [int(lv) for lv in levels] or list(DEFAULT_LEVELS)
        max_events = int(limit) if int(limit) > 0 else DEFAULT_LIMIT
        code, out = self._run(_event_script(log, level_list, max_events), 40.0)
        if code != 0 and not out.strip():
            bucket.append(f"Events: exit {code}")
            return []
        return parse_events(out)

    # ---------- internals ----------

    def _rows(self, errors: list[str], label: str, script: str) -> list[dict[str, Any]]:
        try:
            code, out = self._run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS_UTF8_PREFIX + script],
                40.0,
            )
        except Exception as e:  # noqa: BLE001 - collected, never fatal
            errors.append(f"{label}: {e}")
            return []
        if code != 0 and not out.strip():
            errors.append(f"{label}: exit {code}")
            return []
        rows = _load_rows(out)
        if not rows and out.strip() and code != 0:
            errors.append(f"{label}: exit {code}")
        return rows
