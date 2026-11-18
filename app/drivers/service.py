from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from app.winpaths import POWERSHELL_PATH, PS_UTF8_PREFIX, decode_process_output

DRIVER_SCRIPT = (
    "Get-CimInstance Win32_PnPSignedDriver | "
    "Select-Object Name,DeviceClass,Manufacturer,DriverVersion,DriverDate,ProviderName,Status | "
    "ConvertTo-Json -Compress"
)

TIMEOUT = 40.0


@dataclass(frozen=True, slots=True)
class DriverInfo:
    device: str = ""
    device_class: str = ""
    vendor: str = ""
    driver_version: str = ""
    driver_date: str = ""
    provider: str = ""
    status: str = ""


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _load_rows(text: str) -> list[dict[str, Any]]:
    payload = text.strip().lstrip("\ufeff")
    if not payload:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data] if data else []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    return []


def parse_drivers(text: str) -> tuple[DriverInfo, ...]:
    drivers: list[DriverInfo] = []
    keys = ("Name", "DeviceClass", "Manufacturer", "DriverVersion", "DriverDate", "ProviderName", "Status")
    for row in _load_rows(text):
        values = tuple(_text(row.get(key)) for key in keys)
        if not any(values):
            continue
        drivers.append(DriverInfo(*values))
    return tuple(drivers)


def _default_run(args: Sequence[str], timeout: float) -> tuple[int, str]:
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
    return proc.returncode, decode_process_output(raw)


class DriverService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
    ) -> None:
        self._run = run or _default_run

    def list_drivers(self) -> tuple[tuple[DriverInfo, ...], tuple[str, ...]]:
        errors: list[str] = []
        args = [
            POWERSHELL_PATH,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            PS_UTF8_PREFIX + DRIVER_SCRIPT,
        ]
        try:
            code, out = self._run(args, TIMEOUT)
        except Exception as e:
            errors.append(f"Drivers: {e}")
            return (), tuple(errors)
        if code != 0 and not out.strip():
            errors.append(f"Drivers: exit {code}")
            return (), tuple(errors)
        drivers = parse_drivers(out)
        if not drivers and out.strip() and code != 0:
            errors.append(f"Drivers: exit {code}")
        return drivers, tuple(errors)


__all__ = ["DRIVER_SCRIPT", "DriverInfo", "DriverService", "TIMEOUT", "parse_drivers"]
