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
from typing import TYPE_CHECKING, Any

from app.diagnostics.recommend import build_recommendations
from app.winpaths import POWERSHELL_PATH, PS_UTF8_PREFIX, decode_process_output

if TYPE_CHECKING:
    from app.diagnostics.recommend import Recommendation

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

# Well-known event patterns we can explain in plain words (classification is
# a best-effort read-only annotation — the raw event stays the source of truth).
_SERVICE_FAIL_IDS = {7000, 7001, 7009, 7011, 7022, 7023, 7024, 7026, 7031, 7034}
_DISK_SOURCES = {"disk", "ntfs", "stornvme", "storahci", "volmgr", "volsnap", "partmgr"}

DISK_LIST_SCRIPT = (
    "Get-PhysicalDisk | Select-Object DeviceId,FriendlyName,"
    "@{n='MediaType';e={$_.MediaType.ToString()}},Size,"
    "@{n='HealthStatus';e={$_.HealthStatus.ToString()}},SerialNumber | "
    "ConvertTo-Json -Compress"
)
RELIABILITY_SCRIPT = (
    "Get-PhysicalDisk | Get-StorageReliabilityCounter | Select-Object "
    "DeviceId,Temperature,TemperatureMax,TemperatureLifetime,Wear,PowerOnHours,"
    "ReadErrorsTotal,WriteErrorsTotal,ReadErrorsUncorrected,WriteErrorsUncorrected,"
    "StartStopCycleCount,LoadUnloadCycleCount | "
    "ConvertTo-Json -Compress"
)
SERVICING_EVENTS_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$ev = Get-WinEvent -FilterHashtable @{LogName='System';"
    "ProviderName=@('Microsoft-Windows-Servicing','Microsoft-Windows-ServicingStack',"
    "'Microsoft-Windows-WindowsUpdateClient','Servicing');Level=1,2} -MaxEvents 30;"
    "@($ev) | Select-Object "
    "@{n='Time';e={$_.TimeCreated.ToString('yyyy-MM-dd HH:mm:ss')}},"
    "Level,ProviderName,Id,Message | ConvertTo-Json -Depth 4 -Compress"
)
SYSTEM_EVENTS_SCRIPT = SERVICING_EVENTS_SCRIPT
SYSTEM_FILE_EVENTS_SCRIPT = SERVICING_EVENTS_SCRIPT
DISM_SCAN_SCRIPT = (
    "DISM /Online /Cleanup-Image /ScanHealth; Write-Output \"EXITCODE:$LASTEXITCODE\""
)
SFC_VERIFY_SCRIPT = "sfc.exe /verifyonly; Write-Output \"EXITCODE:$LASTEXITCODE\""
DRIVER_SCRIPT = (
    "Get-CimInstance Win32_PnPEntity -Filter "
    "\"Present=true AND ConfigManagerErrorCode!=0\" | "
    "Select-Object Name,DeviceID,ConfigManagerErrorCode,Status | ConvertTo-Json -Compress"
)
DRIVERS_SCRIPT = DRIVER_SCRIPT

SYSTEM_FILE_STATES = ("ok", "issues", "requires_admin", "unavailable", "unknown")
DRIVER_KINDS = {
    28: "no_driver",
    31: "not_working",
    39: "driver_corrupt",
    52: "reboot",
}
DISM_OK_MARKERS = (
    "no component store corruption detected",
    "пошкоджень сховища компонентів не виявлено",
    "сховище компонентів не пошкоджено",
)
DISM_ISSUE_MARKERS = (
    "the component store is repairable",
    "the component store is not repairable",
    "component store corruption detected",
    "сховище компонентів пошкоджено",
    "виявлено пошкодження сховища",
    "сховище компонентів потрібно відновити",
)
SFC_OK_MARKERS = (
    "windows resource protection did not find any integrity violations",
    "захист ресурсів windows не виявив жодних порушень цілісності",
)
SFC_ISSUE_MARKERS = (
    "windows resource protection found integrity violations",
    "windows resource protection found corrupt files",
    "захист ресурсів windows виявив порушення цілісності",
)
# Pending updates via the Windows Update Agent COM API (read-only search;
# no download/install — the app never touches the update pipeline itself).
UPDATE_SCRIPT = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$s = New-Object -ComObject Microsoft.Update.Session;"
    "$r = $s.CreateUpdateSearcher().Search("
    "\"IsInstalled=0 and IsHidden=0 and Type='Software'\");"
    "@($r.Updates) | ForEach-Object { [PSCustomObject]@{"
    "Title=$_.Title;Severity=$_.MsrcSeverity;"
    "Kb=($_.KBArticleIDs -join ', ')} } | ConvertTo-Json -Compress"
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
    temperature_max_c: int | None = None
    temperature_lifetime_c: int | None = None
    read_errors_uncorrected: int | None = None
    write_errors_uncorrected: int | None = None
    start_stop_cycles: int | None = None
    load_unload_cycles: int | None = None


@dataclass(frozen=True, slots=True)
class EventEntry:
    time: str = ""
    level: int = 0
    level_name: str = ""
    source: str = ""
    event_id: int = 0
    message: str = ""
    kind: str = ""  # pattern id from _classify(), e.g. "kernel_power"


@dataclass(frozen=True, slots=True)
class PendingUpdate:
    title: str = ""
    severity: str = ""  # lowercased MsrcSeverity: critical/important/... or ""
    kb: str = ""


@dataclass(frozen=True, slots=True)
class SystemFileStatus:
    source: str = ""
    state: str = "unknown"
    detail: str = ""


@dataclass(frozen=True, slots=True)
class DriverIssue:
    name: str = ""
    device_id: str = ""
    code: int = 0
    status: str = ""
    kind: str = "unknown"


@dataclass(frozen=True, slots=True)
class DiagnosticsReport:
    disks: tuple[DiskHealth, ...] = ()
    events: tuple[EventEntry, ...] = ()
    errors: tuple[str, ...] = field(default=())
    system_file: SystemFileStatus | None = None
    drivers: tuple[DriverIssue, ...] = ()
    recommendations: tuple[Recommendation, ...] = ()
    unavailable: tuple[str, ...] = ()


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


def parse_updates(output: str) -> list[PendingUpdate]:
    """Parse Windows Update Agent search JSON into pending updates."""
    entries: list[PendingUpdate] = []
    for row in _load_rows(output):
        entries.append(
            PendingUpdate(
                title=_text(row.get("Title")),
                severity=_text(row.get("Severity")).lower(),
                kb=_text(row.get("Kb")),
            )
        )
    return entries


def _classify(source: str, event_id: int, message: str) -> str:
    """Best-effort pattern id for a raw event ("" = no known pattern)."""
    src = source.lower()
    msg = message.lower()
    if src == "kernel-power" and event_id == 41:
        return "bsod" if "bugcheck" in msg else "kernel_power"
    if src in ("microsoft-windows-wer-systemerrorreporting", "bugcheck") or "bugcheck" in msg:
        return "bsod"
    if event_id == 6008:
        return "unexpected_shutdown"
    if src == "application error" and event_id == 1000:
        return "app_crash"
    if src == "application error" and event_id == 1002:
        return "app_hang"
    if src == "microsoft-windows-memorydiagnostics-service":
        return "memory_error"
    if src == "microsoft-windows-windowsupdateclient":
        return "update_error"
    if src in _DISK_SOURCES:
        return "disk_error"
    if src == "service control manager" and event_id in _SERVICE_FAIL_IDS:
        return "service_fail"
    return ""


def parse_events(output: str) -> list[EventEntry]:
    """Parse ``Get-WinEvent | ConvertTo-Json`` output into events."""
    entries: list[EventEntry] = []
    for row in _load_rows(output):
        level = _to_int(row.get("Level"))
        source = _text(row.get("ProviderName"))
        event_id = _to_int(row.get("Id"))
        entries.append(
            EventEntry(
                time=_text(row.get("Time")),
                level=level,
                level_name=LEVEL_NAMES.get(level, ""),
                source=source,
                event_id=event_id,
                message=_clean_message(_text(row.get("Message"))),
                kind=_classify(source, event_id, _text(row.get("Message"))),
            )
        )
    return entries


_EXIT_RE = re.compile(r"EXITCODE:(-?\d+)")


def _default_is_admin() -> bool:
    try:
        import ctypes

        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _admin_value(value: Callable[[], bool] | bool | None) -> bool:
    if value is None:
        return _default_is_admin()
    if callable(value):
        try:
            return bool(value())
        except Exception:
            return False
    return bool(value)


def _strip_exit(output: str) -> tuple[str, int | None]:
    match = _EXIT_RE.search(output)
    if match is None:
        return output, None
    return _EXIT_RE.sub("", output).strip(), int(match.group(1))


def _marker_state(output: str, ok_markers: Sequence[str], issue_markers: Sequence[str]) -> str:
    lowered = output.lower()
    ok_found = [marker for marker in ok_markers if marker in lowered]
    remaining = lowered
    for marker in ok_found:
        remaining = remaining.replace(marker, " ")
    issue_found = [marker for marker in issue_markers if marker in remaining]
    if ok_found and issue_found:
        return "unknown"
    if issue_found:
        return "issues"
    if ok_found:
        return "ok"
    return "unknown"


def _fold_system_status(statuses: Sequence[SystemFileStatus]) -> SystemFileStatus:
    if not statuses:
        return SystemFileStatus(source="all", state="unavailable", detail="No system file checks were run")
    if all(status.state == "ok" for status in statuses):
        return SystemFileStatus(
            source="all",
            state="ok",
            detail="No servicing, component store or system file issues detected",
        )
    for state in ("issues", "unknown", "unavailable", "requires_admin"):
        for status in statuses:
            if status.state == state:
                return status
    for status in statuses:
        if status.state == "ok":
            return status
    return SystemFileStatus(source="all", state="unknown", detail="System file check result unclear")


def parse_drivers(output: str) -> list[DriverIssue]:
    issues: list[DriverIssue] = []
    for row in _load_rows(output):
        code = _to_int(row.get("ConfigManagerErrorCode"))
        if code in (0, 22):
            continue
        issues.append(
            DriverIssue(
                name=_text(row.get("Name")),
                device_id=_text(row.get("DeviceID")) or _text(row.get("DeviceId")),
                code=code,
                status=_text(row.get("Status")),
                kind=DRIVER_KINDS.get(code, "unknown"),
            )
        )
    return issues


# ---------- defaults ----------


_decode_output = decode_process_output


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
    return [POWERSHELL_PATH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script]


class DiagnosticsService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
        is_admin: Callable[[], bool] | bool | None = None,
    ) -> None:
        self._run = run or _default_run
        self._is_admin = is_admin

    # ---------- public ----------

    def report(
        self,
        log_name: str = DEFAULT_LOG,
        levels: Sequence[int] = DEFAULT_LEVELS,
        limit: int = DEFAULT_LIMIT,
        *,
        extended: bool = False,
    ) -> DiagnosticsReport:
        errors: list[str] = []
        base = DiagnosticsReport(
            disks=tuple(self.disk_health(errors)),
            events=tuple(self.events(log_name, levels, limit, errors)),
            errors=tuple(errors),
        )
        if not extended:
            return base
        system_file = self.system_files(errors)
        drivers = tuple(self.driver_issues(errors))
        unavailable = self._unavailable_sources(errors, system_file)
        candidate = DiagnosticsReport(
            disks=base.disks,
            events=base.events,
            errors=tuple(errors),
            system_file=system_file,
            drivers=drivers,
            unavailable=unavailable,
        )
        return DiagnosticsReport(
            disks=candidate.disks,
            events=candidate.events,
            errors=candidate.errors,
            system_file=candidate.system_file,
            drivers=candidate.drivers,
            recommendations=tuple(build_recommendations(candidate)),
            unavailable=candidate.unavailable,
        )

    def full_report(
        self,
        log_name: str = DEFAULT_LOG,
        levels: Sequence[int] = DEFAULT_LEVELS,
        limit: int = DEFAULT_LIMIT,
    ) -> DiagnosticsReport:
        return self.report(log_name, levels, limit, extended=True)

    def system_files(self, errors: list[str] | None = None) -> SystemFileStatus:
        bucket = errors if errors is not None else []
        statuses: list[SystemFileStatus] = []
        code, out = self._script_output(bucket, "System files", SERVICING_EVENTS_SCRIPT, 40.0)
        if code != 0 and not out.strip():
            statuses.append(
                SystemFileStatus("servicing", "unavailable", f"Servicing event query failed (exit {code})")
            )
        else:
            events = parse_events(out)
            if events:
                latest = events[0]
                detail = _clean_message(
                    f"{latest.source} {latest.event_id}: {latest.message}", 240
                )
                statuses.append(SystemFileStatus("servicing", "issues", detail))
            else:
                statuses.append(SystemFileStatus("servicing", "ok", "No servicing or update errors found"))
        if not _admin_value(self._is_admin):
            statuses.append(
                SystemFileStatus(
                    "dism",
                    "requires_admin",
                    "Component store and system file verification requires administrator rights",
                )
            )
            return _fold_system_status(statuses)
        code, out = self._script_output(bucket, "DISM", DISM_SCAN_SCRIPT, 240.0)
        text, exit_code = _strip_exit(out)
        if (code != 0 and not text.strip()) or (exit_code is not None and exit_code != 0):
            failed_code = exit_code if exit_code not in (None, 0) else code
            bucket.append(f"DISM: exit {failed_code}")
            statuses.append(SystemFileStatus("dism", "unavailable", f"DISM scan failed (exit {failed_code})"))
        else:
            status = _marker_state(text, DISM_OK_MARKERS, DISM_ISSUE_MARKERS)
            statuses.append(
                SystemFileStatus("dism", status, _clean_message(text, 240) or "DISM returned no output")
            )
        code, out = self._script_output(bucket, "SFC", SFC_VERIFY_SCRIPT, 180.0)
        text, exit_code = _strip_exit(out)
        if (code != 0 and not text.strip()) or (exit_code is not None and exit_code != 0):
            failed_code = exit_code if exit_code not in (None, 0) else code
            bucket.append(f"SFC: exit {failed_code}")
            statuses.append(SystemFileStatus("sfc", "unavailable", f"SFC verification failed (exit {failed_code})"))
        else:
            status = _marker_state(text, SFC_OK_MARKERS, SFC_ISSUE_MARKERS)
            statuses.append(
                SystemFileStatus("sfc", status, _clean_message(text, 240) or "SFC returned no output")
            )
        return _fold_system_status(statuses)

    def driver_issues(self, errors: list[str] | None = None) -> list[DriverIssue]:
        bucket = errors if errors is not None else []
        code, out = self._script_output(bucket, "Drivers", DRIVER_SCRIPT, 40.0)
        if code != 0 and not out.strip():
            bucket.append(f"Drivers: exit {code}")
            return []
        return parse_drivers(out)

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
                    temperature_max_c=_positive_int(counter.get("TemperatureMax")),
                    temperature_lifetime_c=_positive_int(counter.get("TemperatureLifetime")),
                    read_errors_uncorrected=_counter_int(counter.get("ReadErrorsUncorrected")),
                    write_errors_uncorrected=_counter_int(counter.get("WriteErrorsUncorrected")),
                    start_stop_cycles=_counter_int(counter.get("StartStopCycleCount")),
                    load_unload_cycles=_counter_int(counter.get("LoadUnloadCycleCount")),
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

    def windows_updates(self, errors: list[str] | None = None) -> list[PendingUpdate]:
        """Search Windows Update for not-installed software updates (read-only).

        The WUA search can take a while (talks to the update service), so the
        caller should run this off the UI thread; the timeout is generous.
        """
        bucket = errors if errors is not None else []
        try:
            code, out = self._run(
                [
                    POWERSHELL_PATH,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    PS_UTF8_PREFIX + UPDATE_SCRIPT,
                ],
                180.0,
            )
        except Exception as e:  # noqa: BLE001 - collected, never fatal
            bucket.append(f"Windows Update: {e}")
            return []
        if code != 0 and not out.strip():
            bucket.append(f"Windows Update: exit {code}")
            return []
        return parse_updates(out)

    # ---------- internals ----------

    @staticmethod
    def _unavailable_sources(
        errors: Sequence[str], system_file: SystemFileStatus | None
    ) -> tuple[str, ...]:
        names: list[str] = []
        prefixes = (
            ("Drives", "disks"),
            ("Reliability", "disks"),
            ("Events", "events"),
            ("Drivers", "drivers"),
            ("System files", "system_files"),
            ("DISM", "system_files"),
            ("SFC", "system_files"),
        )
        for prefix, name in prefixes:
            if any(prefix in item for item in errors) and name not in names:
                names.append(name)
        if system_file is not None and system_file.state in ("unavailable", "unknown"):
            if "system_files" not in names:
                names.append("system_files")
        return tuple(names)

    def _script_output(
        self, errors: list[str], label: str, script: str, timeout: float
    ) -> tuple[int, str]:
        try:
            code, out = self._run(
                [
                    POWERSHELL_PATH,
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    PS_UTF8_PREFIX + script,
                ],
                timeout,
            )
        except Exception as e:  # noqa: BLE001 - collected, never fatal
            errors.append(f"{label}: {e}")
            return 1, ""
        return code, out

    def _rows(self, errors: list[str], label: str, script: str) -> list[dict[str, Any]]:
        try:
            code, out = self._run(
                [POWERSHELL_PATH, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", PS_UTF8_PREFIX + script],
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
