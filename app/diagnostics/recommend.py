from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.diagnostics.service import DiagnosticsReport

EVENT_SEVERITIES = {
    "bsod": "critical",
    "kernel_power": "critical",
    "memory_error": "critical",
    "disk_error": "critical",
    "unexpected_shutdown": "warning",
    "service_fail": "warning",
    "app_crash": "warning",
    "app_hang": "warning",
    "update_error": "warning",
}
CRITICAL_EVENT_KINDS = frozenset(
    kind for kind, severity in EVENT_SEVERITIES.items() if severity == "critical"
)
DRIVER_SEVERITIES = {
    "no_driver": "critical",
    "not_working": "critical",
    "driver_corrupt": "critical",
    "reboot": "warning",
    "unknown": "warning",
}
DRIVER_TITLES = {
    "no_driver": "Devices without a driver",
    "not_working": "Devices not working correctly",
    "driver_corrupt": "Corrupt device drivers",
    "reboot": "Pending reboot for device changes",
    "unknown": "Unclassified device problems",
}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2, "ok": 3}


@dataclass(frozen=True, slots=True)
class Recommendation:
    severity: str = ""
    title: str = ""
    detail: str = ""
    source: str = ""


def build_recommendations(report: DiagnosticsReport) -> list[Recommendation]:
    items: list[Recommendation] = []
    for disk in report.disks:
        detail = disk.name or disk.serial or "unnamed drive"
        if disk.health == "unhealthy":
            items.append(Recommendation("critical", "Drive reports unhealthy state", detail, "disk_health"))
        elif disk.health == "warning":
            items.append(Recommendation("warning", "Drive reports warning state", detail, "disk_health"))
        if disk.wear_percent is not None and disk.wear_percent >= 90:
            items.append(
                Recommendation(
                    "warning",
                    "Drive wear is high",
                    f"{detail}: {disk.wear_percent}% endurance consumed",
                    "disk_wear",
                )
            )
        uncorrected = (
            disk.read_errors_uncorrected or 0
        ) + (disk.write_errors_uncorrected or 0)
        if uncorrected > 0:
            items.append(
                Recommendation(
                    "warning",
                    "Uncorrected disk errors reported",
                    f"{detail}: {uncorrected} uncorrected read/write errors",
                    "disk_smart",
                )
            )
    event_counts = Counter(event.kind for event in report.events if event.kind in EVENT_SEVERITIES)
    for kind, count in event_counts.items():
        latest = next(event for event in report.events if event.kind == kind)
        detail = f"{count} event(s), latest {latest.time} {latest.source} {latest.event_id}"
        items.append(
            Recommendation(
                EVENT_SEVERITIES[kind],
                f"Critical events: {kind}" if kind in CRITICAL_EVENT_KINDS else f"Events: {kind}",
                detail,
                "events",
            )
        )
    status = report.system_file
    if status is not None:
        if status.state == "issues":
            items.append(
                Recommendation("critical", "System file issues detected", status.detail, "system_files")
            )
        elif status.state == "requires_admin":
            items.append(
                Recommendation(
                    "info",
                    "Deeper system file checks need administrator rights",
                    status.detail,
                    "system_files",
                )
            )
        elif status.state in ("unavailable", "unknown"):
            items.append(
                Recommendation(
                    "warning",
                    "System file check was inconclusive" if status.state == "unknown" else "System file check unavailable",
                    status.detail,
                    "system_files",
                )
            )
    driver_counts = Counter(driver.kind for driver in report.drivers)
    for kind, count in driver_counts.items():
        names = ", ".join(driver.name or driver.device_id for driver in report.drivers if driver.kind == kind)
        items.append(
            Recommendation(
                DRIVER_SEVERITIES.get(kind, "warning"),
                DRIVER_TITLES.get(kind, "Device problems"),
                f"{count} device(s): {names}",
                "drivers",
            )
        )
    if report.unavailable:
        items.append(
            Recommendation(
                "warning",
                "Some diagnostics were unavailable",
                ", ".join(report.unavailable),
                "availability",
            )
        )
    if report.errors:
        items.append(
            Recommendation(
                "warning",
                "Diagnostics completed with errors",
                "; ".join(report.errors[:3]),
                "errors",
            )
        )
    disks_available = bool(report.disks) and all(disk.health != "unknown" for disk in report.disks)
    all_available = (
        disks_available
        and status is not None
        and status.state == "ok"
        and not report.unavailable
        and not report.errors
    )
    if all_available and not items:
        items.append(
            Recommendation(
                "ok",
                "No issues detected",
                "All diagnostics sources were available and no problems were found.",
                "summary",
            )
        )
    items.sort(key=lambda item: (_SEVERITY_ORDER.get(item.severity, 9), item.source, item.title, item.detail))
    return items
