"""PCOptimizer_PRO — Windows System Restore helper.

Creates restore points reliably:
- elevates the ``Checkpoint-Computer`` call in a single UAC prompt (the app
  itself runs non-elevated);
- temporarily lifts the Windows "one restore point per 24 h" throttle
  (``SystemRestorePointCreationFrequency``) and restores the old value;
- verifies the point actually appeared, so we never report a silent no-op as
  success.
"""

from __future__ import annotations

import base64
import ctypes
import subprocess
import time
from dataclasses import dataclass
from typing import Callable, Sequence

# Status codes returned in RestoreResult.status
STATUS_CREATED = "created"
STATUS_SKIPPED = "skipped"
STATUS_DISABLED = "disabled"
STATUS_CANCELLED = "cancelled"
STATUS_ERROR = "error"

RESTORE_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore"
FREQUENCY_VALUE = "SystemRestorePointCreationFrequency"

UAC_CANCELLED_CODE = 1223

_DISABLED_MARKERS = (
    "disabled",
    "not enabled",
    "turned off",
    "system protection",
    "захист системи",
    "вимкнено",
    "отключен",
)


@dataclass(frozen=True, slots=True)
class RestorePoint:
    sequence: int
    description: str


@dataclass(frozen=True, slots=True)
class RestoreResult:
    ok: bool
    status: str
    message: str = ""
    label: str | None = None
    sequence: int | None = None


class RestoreError(Exception):
    pass


def _b64(script: str) -> str:
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


class RestorePointService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
        is_admin: Callable[[], bool] | None = None,
        powershell: str = "powershell",
    ) -> None:
        self._run = run or self._default_run
        self._is_admin = is_admin or self._default_is_admin
        self._ps = powershell

    # ---------- public ----------

    def list_points(self) -> list[RestorePoint]:
        out = self._run_ps(self._list_script(), 60.0)
        if out is None:
            return []
        code, text = out
        if code != 0:
            return []
        points: list[RestorePoint] = []
        for line in text.splitlines():
            line = line.strip()
            if "\t" not in line:
                continue
            seq_raw, desc = line.split("\t", 1)
            try:
                points.append(RestorePoint(int(seq_raw.strip()), desc.strip()))
            except ValueError:
                continue
        return points

    def create(self, label: str, *, force: bool = True) -> RestoreResult:
        label = (label or "").strip() or "PCOptimizer PRO"
        before = {p.sequence for p in self.list_points()}
        script = self._build_create_script(label, force)
        result = self._invoke(script, 240.0)
        if result is None:
            return RestoreResult(False, STATUS_CANCELLED, "cancelled at the UAC prompt", label=label)

        code, text = result
        after_points = self.list_points()
        new = {p.sequence for p in after_points} - before
        if new:
            seq = max(new)
            detail = next((p.description for p in after_points if p.sequence == seq), label)
            return RestoreResult(True, STATUS_CREATED, detail, label=label, sequence=seq)

        lowered = text.lower()
        if any(marker in lowered for marker in _DISABLED_MARKERS):
            return RestoreResult(False, STATUS_DISABLED, text.strip(), label=label)
        if code == UAC_CANCELLED_CODE:
            return RestoreResult(False, STATUS_CANCELLED, text.strip(), label=label)
        if code == 0:
            return RestoreResult(False, STATUS_SKIPPED, text.strip() or "no new restore point", label=label)
        return RestoreResult(False, STATUS_ERROR, text.strip() or f"exit {code}", label=label)

    def enable_protection(self, drive: str = "C:") -> RestoreResult:
        letter = drive.rstrip("\\")
        script = (
            "$ErrorActionPreference='Stop'; "
            f"Enable-ComputerRestore -Drive '{letter}\\'; "
            "Write-Output 'OK'"
        )
        result = self._invoke(script, 120.0)
        if result is None:
            return RestoreResult(False, STATUS_CANCELLED, "cancelled at the UAC prompt")
        code, text = result
        if code == 0:
            return RestoreResult(True, STATUS_CREATED, "system protection enabled")
        return RestoreResult(False, STATUS_ERROR, text.strip() or f"exit {code}")

    # ---------- scripts ----------

    @staticmethod
    def _list_script() -> str:
        return (
            "Get-ComputerRestorePoint | "
            'ForEach-Object { "$($_.SequenceNumber)`t$($_.Description)" }'
        )

    @staticmethod
    def _build_create_script(label: str, force: bool) -> str:
        safe = label.replace("'", "''")
        force_lit = "$true" if force else "$false"
        return (
            "$ErrorActionPreference='Stop'\n"
            f"$key=Join-Path 'HKLM:\\' '{RESTORE_KEY}'\n"
            "$had=$false; $old=$null\n"
            f"try {{ $old=(Get-ItemProperty -Path $key -Name {FREQUENCY_VALUE} -ErrorAction Stop).{FREQUENCY_VALUE}; $had=$true }} catch {{}}\n"
            "try {\n"
            f"  if ({force_lit}) {{ New-ItemProperty -Path $key -Name {FREQUENCY_VALUE} -PropertyType DWord -Value 0 -Force | Out-Null }}\n"
            f"  Checkpoint-Computer -Description '{safe}' -RestorePointType MODIFY_SETTINGS\n"
            "  Write-Output 'OK'\n"
            "  exit 0\n"
            "} catch {\n"
            "  Write-Output $_.Exception.Message\n"
            "  exit 1\n"
            "} finally {\n"
            f"  if ({force_lit}) {{ if ($had) {{ Set-ItemProperty -Path $key -Name {FREQUENCY_VALUE} -Value $old -ErrorAction SilentlyContinue }} "
            f"else {{ Remove-ItemProperty -Path $key -Name {FREQUENCY_VALUE} -ErrorAction SilentlyContinue }} }}\n"
            "}"
        )

    def _elevated_script(self, script: str) -> str:
        encoded = _b64(script)
        return (
            "$ErrorActionPreference='Stop'; "
            "try { "
            "$p=Start-Process -FilePath 'powershell' -Verb RunAs -Wait -WindowStyle Hidden "
            f"-ArgumentList @('-NoProfile','-ExecutionPolicy','Bypass','-EncodedCommand','{encoded}') -PassThru; "
            "exit $p.ExitCode "
            f"}} catch {{ Write-Error $_.Exception.Message; exit {UAC_CANCELLED_CODE} }}"
        )

    def _invoke(self, script: str, timeout: float) -> tuple[int, str] | None:
        """Run *script* (elevated if needed). Returns (code, output) or None if UAC cancelled."""
        if self._is_admin():
            code, out = self._run(
                (self._ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-EncodedCommand", _b64(script)),
                timeout,
            )
            return code, out

        code, out = self._run(
            (self._ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", self._elevated_script(script)),
            timeout,
        )
        if code == UAC_CANCELLED_CODE or "cancel" in out.lower():
            return None
        return code, out

    # ---------- primitives ----------

    def _run_ps(self, script: str, timeout: float) -> tuple[int, str] | None:
        try:
            return self._run((self._ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script), timeout)
        except Exception:
            return None

    @staticmethod
    def _default_run(args: Sequence[str], timeout: float) -> tuple[int, str]:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return 1, str(e)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    @staticmethod
    def _default_is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False


# Reusable helper for the UI: create a timestamped point with a readable label.
def make_label(prefix: str = "PCOptimizer_PRO") -> str:
    return f"{prefix} {time.strftime('%Y-%m-%d %H:%M:%S')}"
