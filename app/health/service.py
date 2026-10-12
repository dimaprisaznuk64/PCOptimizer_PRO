from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from app.cleaner import CleanerService, CleanOutcome, default_targets
from app.cleaner.service import RECYCLE_BIN_ID
from app.disk import DiskAnalyzer
from app.optimizer import OptimizerService
from app.sensors import SensorManager
from app.startup import StartupService

JUNK_WARNING = 1 * 1024**3
JUNK_CRITICAL = 5 * 1024**3

SEVERITY_PENALTY = {"critical": 30, "warning": 10, "info": 3, "ok": 0}

GRADES = ((90, "Excellent"), (75, "Good"), (50, "Fair"), (0, "Poor"))


class HealthError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class Finding:
    id: str
    category: str
    severity: str
    title: str
    detail: str
    fixable: bool = False
    fix_hint: str = ""


@dataclass(frozen=True, slots=True)
class HealthReport:
    score: int
    grade: str
    findings: tuple[Finding, ...]
    junk_bytes: int = 0
    junk_targets: int = 0
    generated: float = 0.0
    errors: tuple[str, ...] = ()

    @property
    def fixable_count(self) -> int:
        return sum(1 for f in self.findings if f.fixable)


@dataclass(frozen=True, slots=True)
class FixReport:
    applied: tuple[str, ...]
    errors: tuple[str, ...]
    reclaimed_bytes: int
    files_deleted: int


def grade_for(score: int) -> str:
    for threshold, name in GRADES:
        if score >= threshold:
            return name
    return "Poor"


def score_from(findings) -> int:
    penalty = sum(SEVERITY_PENALTY.get(f.severity, 0) for f in findings)
    return max(0, min(100, 100 - penalty))


class HealthService:
    def __init__(
        self,
        *,
        sensors: SensorManager | None = None,
        disks: DiskAnalyzer | None = None,
        cleaner: CleanerService | None = None,
        startup: StartupService | None = None,
        optimizer: OptimizerService | None = None,
    ) -> None:
        self._sensors = sensors if sensors is not None else SensorManager.with_defaults()
        self._disks = disks or DiskAnalyzer()
        self._cleaner = cleaner or CleanerService()
        self._startup = startup or StartupService()
        self._optimizer = optimizer or OptimizerService()
        self.last_report: HealthReport | None = None

    # ---------- scan ----------

    def scan(self, *, include_junk: bool = True) -> HealthReport:
        findings: list[Finding] = []
        errors: list[str] = []
        junk_bytes = 0
        junk_targets = 0

        self._check_sensors(findings, errors)
        self._check_disks(findings, errors)
        self._check_startup(findings, errors)
        self._check_power(findings, errors)
        if include_junk:
            junk_bytes, junk_targets = self._check_junk(findings, errors)

        score = score_from(findings)
        report = HealthReport(
            score=score,
            grade=grade_for(score),
            findings=tuple(findings),
            junk_bytes=junk_bytes,
            junk_targets=junk_targets,
            generated=time.time(),
            errors=tuple(errors),
        )
        self.last_report = report
        return report

    def _check_sensors(self, findings: list[Finding], errors: list[str]) -> None:
        try:
            snapshot = self._sensors.snapshot()
        except Exception as e:
            errors.append(f"sensors: {e}")
            return

        if snapshot.memory is not None:
            percent = snapshot.memory.percent
            if percent >= 95:
                findings.append(Finding(
                    "memory", "Memory", "critical", "RAM almost full",
                    f"{percent:.0f}% of RAM in use — close heavy apps", fix_hint="Close unused applications",
                ))
            elif percent >= 85:
                findings.append(Finding(
                    "memory", "Memory", "warning", "High RAM usage",
                    f"{percent:.0f}% of RAM in use",
                ))
            else:
                findings.append(Finding("memory", "Memory", "ok", "RAM usage healthy", f"{percent:.0f}% used"))

        temp = self._max_temperature(snapshot)
        if temp is not None:
            if temp >= 95:
                findings.append(Finding(
                    "thermal", "Thermal", "critical", "Very high CPU temperature",
                    f"{temp:.0f}C — check cooling / dust", fix_hint="Clean fans, improve airflow",
                ))
            elif temp >= 85:
                findings.append(Finding(
                    "thermal", "Thermal", "warning", "High CPU temperature", f"{temp:.0f}C",
                ))
            else:
                findings.append(Finding("thermal", "Thermal", "ok", "Temperatures normal", f"{temp:.0f}C"))

        if snapshot.cpu is not None and snapshot.cpu.percent >= 90:
            findings.append(Finding(
                "cpu_load", "CPU", "info", "CPU load is high right now",
                f"{snapshot.cpu.percent:.0f}% — may be a background task",
            ))

    @staticmethod
    def _max_temperature(snapshot):
        thermal = snapshot.thermal
        if thermal is None or not thermal.temperatures:
            return None
        return max(value for _name, value in thermal.temperatures)

    def _check_disks(self, findings: list[Finding], errors: list[str]) -> None:
        try:
            drives = self._disks.list_drives()
        except Exception as e:
            errors.append(f"disks: {e}")
            return
        for drive in drives:
            if drive.percent >= 97:
                findings.append(Finding(
                    f"disk:{drive.mount}", "Storage", "critical", f"{drive.mount} nearly full",
                    f"{drive.percent:.0f}% used — free space now",
                    fix_hint="Run the Cleaner or remove large files",
                ))
            elif drive.percent >= 90:
                findings.append(Finding(
                    f"disk:{drive.mount}", "Storage", "warning", f"{drive.mount} running low",
                    f"{drive.percent:.0f}% used",
                ))

    def _check_startup(self, findings: list[Finding], errors: list[str]) -> None:
        try:
            items, list_errors = self._startup.list_items()
        except Exception as e:
            errors.append(f"startup: {e}")
            return
        errors.extend(f"startup: {e}" for e in list_errors)
        heavy = [i for i in items if i.enabled and i.impact == "High"]
        if len(heavy) >= 8:
            findings.append(Finding(
                "startup", "Startup", "warning", f"{len(heavy)} heavy startup apps",
                "They slow down logon and consume RAM",
                fix_hint="Disable unneeded entries in the Startup page",
            ))
        elif len(heavy) >= 4:
            findings.append(Finding(
                "startup", "Startup", "info", f"{len(heavy)} heavy startup apps",
                "Consider disabling the ones you do not need",
            ))

    def _check_power(self, findings: list[Finding], errors: list[str]) -> None:
        try:
            state = self._optimizer.state()
        except Exception as e:
            errors.append(f"optimizer: {e}")
            return
        if state.power_name == "Power saver":
            findings.append(Finding(
                "power", "Power", "info", "Power saver plan is active",
                "Switch to Balanced or the Gaming profile for more performance",
            ))

    def _check_junk(self, findings: list[Finding], errors: list[str]) -> tuple[int, int]:
        targets = default_targets()
        total = 0
        counted = 0
        for target in targets:
            if target.id == RECYCLE_BIN_ID:
                continue
            try:
                result = self._cleaner.scan(target)
            except Exception as e:
                errors.append(f"cleaner {target.name}: {e}")
                continue
            if result.error:
                errors.append(f"cleaner {target.name}: {result.error}")
                continue
            total += result.bytes
            if result.bytes > 0:
                counted += 1

        if total >= JUNK_CRITICAL:
            findings.append(Finding(
                "junk", "Cleanup", "critical", "Lots of temporary files",
                f"{total / 1024**3:.1f} GB across {counted} locations",
                fixable=True, fix_hint="Clean them now",
            ))
        elif total >= JUNK_WARNING:
            findings.append(Finding(
                "junk", "Cleanup", "warning", "Temporary files found",
                f"{total / 1024**3:.1f} GB across {counted} locations",
                fixable=True, fix_hint="Clean them now",
            ))
        else:
            findings.append(Finding(
                "junk", "Cleanup", "ok", "Little temporary clutter",
                f"{total / 1024**2:.0f} MB found",
            ))
        return total, counted

    # ---------- fix ----------

    def fix_all(self, *, include_recycle_bin: bool = False) -> FixReport:
        targets = default_targets()
        applied: list[str] = []
        errors: list[str] = []
        reclaimed = 0
        deleted = 0

        for target in targets:
            if target.id == RECYCLE_BIN_ID and not include_recycle_bin:
                continue
            try:
                scan = self._cleaner.scan(target)
            except Exception as e:
                errors.append(f"{target.name}: {e}")
                continue
            if scan.error:
                errors.append(f"{target.name}: {scan.error}")
                continue
            if scan.bytes <= 0:
                continue
            try:
                outcome: CleanOutcome = self._cleaner.clean(target, known_bytes=scan.bytes)
            except Exception as e:
                errors.append(f"{target.name}: {e}")
                continue
            if outcome.error:
                errors.append(f"{target.name}: {outcome.error}")
                continue
            reclaimed += outcome.freed_bytes
            deleted += outcome.files_deleted
            applied.append(f"{target.name}: {outcome.freed_bytes / 1024**2:.0f} MB")

        return FixReport(
            applied=tuple(applied),
            errors=tuple(errors),
            reclaimed_bytes=reclaimed,
            files_deleted=deleted,
        )
