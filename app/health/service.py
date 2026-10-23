from __future__ import annotations

import time
from dataclasses import dataclass

from app.cleaner import CleanerService, CleanOutcome, default_targets
from app.cleaner.service import RECYCLE_BIN_ID
from app.disk import DiskAnalyzer
from app.optimizer import OptimizerService
from app.sensors import SensorManager
from app.startup import StartupService

JUNK_WARNING = 1 * 1024**3
JUNK_CRITICAL = 5 * 1024**3

SEVERITY_PENALTY = {"critical": 30, "warning": 10, "info": 3, "ok": 0}

GRADES = ((95, "Excellent"), (75, "Good"), (50, "Fair"), (0, "Poor"))


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
        else:
            findings.append(Finding(
                "memory_missing", "Memory", "info", "RAM data unavailable",
                "The sensor did not report memory usage, so it is not scored",
            ))

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
        else:
            findings.append(Finding(
                "thermal_missing", "Thermal", "info", "Temperature data unavailable",
                "No thermal sensor reported temperatures, so they are not scored",
            ))

        if snapshot.cpu is not None and snapshot.cpu.percent >= 90:
            findings.append(Finding(
                "cpu_load", "CPU", "info", "CPU load is high right now",
                f"{snapshot.cpu.percent:.0f}% — may be a background task",
            ))

        # GPU: NVML temperature and load count too (laptops throttle near 85-90 C).
        # Ignore stale GPUs (they might be stuck in a hot state).
        active_gpus = [g for g in snapshot.gpus if not g.stale]
        gpu_temps = [g.temperature for g in active_gpus if g.temperature is not None]
        if gpu_temps:
            gpu_temp = max(gpu_temps)
            if gpu_temp >= 90:
                findings.append(Finding(
                    "thermal_gpu", "Thermal", "critical", "Very high GPU temperature",
                    f"{gpu_temp:.0f}C — GPU is close to throttling",
                    fix_hint="Clean fans, improve airflow, lower in-game quality",
                ))
            elif gpu_temp >= 80:
                findings.append(Finding(
                    "thermal_gpu", "Thermal", "warning", "High GPU temperature",
                    f"{gpu_temp:.0f}C — normal while gaming, not at idle",
                ))
        gpu_utils = [g.utilization for g in active_gpus]
        if gpu_utils and max(gpu_utils) >= 90:
            findings.append(Finding(
                "gpu_load", "GPU", "info", "GPU load is high right now",
                f"{max(gpu_utils):.0f}% — normal in games, check temperatures if constant",
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

    def fix_finding(self, finding: Finding) -> FixReport:
        """Fix a single finding chosen by the user (never applied without their confirmation)."""
        if finding.id == "junk":
            return self.fix_all()
        if finding.id == "power":
            return self._fix_power()
        if finding.id == "startup":
            return self._fix_startup()
        raise HealthError(f"finding '{finding.id}' cannot be fixed automatically")

    def _fix_power(self) -> FixReport:
        # No restore point here: Windows throttles them (1/24h) and the UAC prompt
        # would block a one-click fix — the JSON backup still makes this revertible.
        try:
            report = self._optimizer.apply_profile("BALANCED", with_restore_point=False)
        except Exception as e:
            return FixReport(applied=(), errors=(str(e),), reclaimed_bytes=0, files_deleted=0)
        return FixReport(
            applied=tuple(report.applied),
            errors=tuple(report.errors),
            reclaimed_bytes=0,
            files_deleted=0,
        )

    def _fix_startup(self) -> FixReport:
        applied: list[str] = []
        errors: list[str] = []
        try:
            items, list_errors = self._startup.list_items()
        except Exception as e:
            return FixReport(applied=(), errors=(str(e),), reclaimed_bytes=0, files_deleted=0)
        errors.extend(f"startup: {e}" for e in list_errors)
        for item in items:
            if not (item.enabled and item.impact == "High"):
                continue
            try:
                self._startup.set_enabled(item, False)
            except Exception as e:
                errors.append(f"{item.name}: {e}")
                continue
            applied.append(item.name)
        return FixReport(
            applied=tuple(applied),
            errors=tuple(errors),
            reclaimed_bytes=0,
            files_deleted=0,
        )

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
            elif outcome.partial:
                errors.append(f"{target.name}: partially cleaned ({outcome.files_skipped} locked)")
            reclaimed += outcome.freed_bytes
            deleted += outcome.files_deleted
            if outcome.freed_bytes > 0 or outcome.files_deleted > 0:
                applied.append(f"{target.name}: {outcome.freed_bytes / 1024**2:.0f} MB")

        return FixReport(
            applied=tuple(applied),
            errors=tuple(errors),
            reclaimed_bytes=reclaimed,
            files_deleted=deleted,
        )
