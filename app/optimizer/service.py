from __future__ import annotations

import ctypes
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

GUID_BALANCED = "381b4222-f694-41f0-9685-ff5bb260df2e"
GUID_HIGH_PERF = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
GUID_ULTIMATE = "e9a42b02-d5df-448d-aa00-03f14749eb61"
GUID_POWER_SAVER = "9596fb26-9850-41fd-ac3e-f7c3c00afd4b"

PLAN_NAMES = {
    GUID_BALANCED: "Balanced",
    GUID_HIGH_PERF: "High performance",
    GUID_ULTIMATE: "Ultimate performance",
    GUID_POWER_SAVER: "Power saver",
}

GAMEMODE_KEY = r"Software\Microsoft\GameBar"
GAMEMODE_VALUE = "AutoGameModeEnabled"

HAGS_KEY = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
HAGS_VALUE = "HwSchMode"

VISUAL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Explorer\VisualEffects"
VISUAL_VALUE = "VisualFXSetting"

VISUAL_DEFAULT = 0
VISUAL_PERFORMANCE = 2
VISUAL_APPEARANCE = 3

VISUAL_NAMES = {
    VISUAL_DEFAULT: "Let Windows decide",
    VISUAL_PERFORMANCE: "Adjust for best performance",
    VISUAL_APPEARANCE: "Adjust for best appearance",
}

PROFILES: dict[str, dict[str, object]] = {
    "BALANCED": {
        "description": "Everyday profile: stock power plan and Windows defaults.",
        "power": GUID_BALANCED,
        "visual": VISUAL_DEFAULT,
    },
    "GAMING": {
        "description": "High performance power plan, Game Mode on, HAGS on.",
        "power": GUID_HIGH_PERF,
        "game_mode": True,
        "hags": True,
    },
    "PERFORMANCE": {
        "description": "High performance power plan and best-performance visual effects.",
        "power": GUID_HIGH_PERF,
        "visual": VISUAL_PERFORMANCE,
        "hags": True,
    },
}

_GUID_RE = re.compile(
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


class OptimizerError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class OptimizerState:
    power_guid: str | None
    power_name: str
    game_mode: bool | None
    hags: bool | None
    visual_fx: int | None
    visual_name: str
    is_admin: bool
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ApplyReport:
    applied: tuple[str, ...]
    errors: tuple[str, ...]
    restore_point: str | None = None


def parse_active_guid(output: str) -> str | None:
    match = _GUID_RE.search(output)
    return match.group(1).lower() if match else None


class OptimizerService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
        elevate: Callable[[Sequence[str]], bool] | None = None,
        is_admin: Callable[[], bool] | None = None,
        reg_get: Callable[[str, str, str], int] | None = None,
        reg_set: Callable[[str, str, str, int], None] | None = None,
        backup_path: str | Path | None = None,
    ) -> None:
        self._run = run or self._default_run
        self._elevate = elevate or self._default_elevate
        self._is_admin = is_admin or self._default_is_admin
        self._reg_get = reg_get or self._default_reg_get
        self._reg_set = reg_set or self._default_reg_set
        local = os.environ.get("LOCALAPPDATA", "")
        self.backup_path = Path(backup_path) if backup_path else (
            Path(local) / "PCOptimizer_PRO" / "optimizer_backup.json"
        )

    # ---------- state ----------

    def state(self) -> OptimizerState:
        errors: list[str] = []
        power_guid = self._active_power_guid()
        if power_guid is None:
            errors.append("cannot read active power plan")
        game_mode, game_err = self._reg_get_dword("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE)
        if game_err:
            errors.append(game_err)
        game_mode_bool = None if game_mode is None else bool(game_mode)
        hags_raw, hags_err = self._reg_get_dword("HKLM", HAGS_KEY, HAGS_VALUE)
        if hags_err:
            errors.append(hags_err)
        hags = None if hags_raw is None else hags_raw == 2
        visual, visual_err = self._reg_get_dword("HKCU", VISUAL_KEY, VISUAL_VALUE)
        if visual_err:
            errors.append(visual_err)
        return OptimizerState(
            power_guid=power_guid,
            power_name=PLAN_NAMES.get(power_guid or "", "Unknown"),
            game_mode=game_mode_bool,
            hags=hags,
            visual_fx=visual,
            visual_name=VISUAL_NAMES.get(visual if visual is not None else VISUAL_DEFAULT, "Custom"),
            is_admin=self._is_admin(),
            errors=tuple(errors),
        )

    def _active_power_guid(self) -> str | None:
        code, out = self._run(("powercfg", "/getactivescheme"), 15.0)
        if code != 0:
            return None
        return parse_active_guid(out)

    # ---------- apply ----------

    def apply_profile(self, profile: str, *, with_restore_point: bool = True) -> ApplyReport:
        spec = PROFILES.get(profile.upper())
        if spec is None:
            raise OptimizerError(f"unknown profile {profile}")

        restore_label: str | None = None
        if with_restore_point:
            try:
                restore_label = self.create_restore_point(f"PCOptimizer_PRO {profile}")
            except OptimizerError as e:
                return ApplyReport(applied=(), errors=(f"restore point failed: {e}",))

        self._save_backup()

        applied: list[str] = []
        errors: list[str] = []

        if "power" in spec:
            guid = str(spec["power"])
            code, out = self._run(("powercfg", "/setactive", guid), 15.0)
            if code == 0:
                applied.append(f"power plan → {PLAN_NAMES.get(guid, guid)}")
            else:
                errors.append(f"powercfg failed: {out.strip() or code}")

        if "game_mode" in spec:
            target = bool(spec["game_mode"])
            try:
                self._reg_set_dword("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE, 1 if target else 0)
                applied.append(f"Game Mode → {'on' if target else 'off'}")
            except OptimizerError as e:
                errors.append(str(e))

        if "hags" in spec:
            target = bool(spec["hags"])
            try:
                self._set_hags(target)
                applied.append(f"hardware-accelerated GPU scheduling → {'on' if target else 'off'}")
            except OptimizerError as e:
                errors.append(str(e))

        if "visual" in spec:
            target = int(spec["visual"])
            try:
                self._reg_set_dword("HKCU", VISUAL_KEY, VISUAL_VALUE, target)
                applied.append(f"visual effects → {VISUAL_NAMES.get(target, target)}")
            except OptimizerError as e:
                errors.append(str(e))

        return ApplyReport(applied=tuple(applied), errors=tuple(errors), restore_point=restore_label)

    def revert(self) -> ApplyReport:
        backup = self._load_backup()
        if backup is None:
            raise OptimizerError("no backup available — nothing to revert")
        applied: list[str] = []
        errors: list[str] = []

        guid = backup.get("power_guid")
        if guid:
            code, out = self._run(("powercfg", "/setactive", str(guid)), 15.0)
            if code == 0:
                applied.append(f"power plan → {PLAN_NAMES.get(str(guid), str(guid))}")
            else:
                errors.append(f"powercfg failed: {out.strip() or code}")

        game_mode = backup.get("game_mode")
        if isinstance(game_mode, bool):
            try:
                self._reg_set_dword("HKCU", GAMEMODE_KEY, GAMEMODE_VALUE, 1 if game_mode else 0)
                applied.append(f"Game Mode → {'on' if game_mode else 'off'}")
            except OptimizerError as e:
                errors.append(str(e))

        hags = backup.get("hags")
        if isinstance(hags, bool):
            try:
                self._set_hags(hags)
                applied.append(f"hardware-accelerated GPU scheduling → {'on' if hags else 'off'}")
            except OptimizerError as e:
                errors.append(str(e))

        visual = backup.get("visual_fx")
        if isinstance(visual, int):
            try:
                self._reg_set_dword("HKCU", VISUAL_KEY, VISUAL_VALUE, visual)
                applied.append(f"visual effects → {VISUAL_NAMES.get(visual, visual)}")
            except OptimizerError as e:
                errors.append(str(e))

        return ApplyReport(applied=tuple(applied), errors=tuple(errors))

    def create_restore_point(self, description: str) -> str:
        label = f"{description} {time.strftime('%Y-%m-%d %H:%M:%S')}"
        script = (
            "Checkpoint-Computer "
            f"-Description '{label}' -RestorePointType MODIFY_SETTINGS"
        )
        code, out = self._run(
            ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script),
            300.0,
        )
        if code != 0:
            raise OptimizerError(out.strip() or f"exit {code}")
        return label

    def backup_exists(self) -> bool:
        return self.backup_path.exists()

    # ---------- backup ----------

    def _save_backup(self) -> None:
        state = self.state()
        data = {
            "ts": time.time(),
            "power_guid": state.power_guid,
            "game_mode": state.game_mode,
            "hags": state.hags,
            "visual_fx": state.visual_fx,
        }
        self.backup_path.parent.mkdir(parents=True, exist_ok=True)
        self.backup_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_backup(self) -> dict | None:
        if not self.backup_path.exists():
            return None
        try:
            data = json.loads(self.backup_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    # ---------- primitives ----------

    def _set_hags(self, enabled: bool) -> None:
        value = 2 if enabled else 1
        if self._is_admin():
            self._reg_set_dword("HKLM", HAGS_KEY, HAGS_VALUE, value)
            return
        script = (
            f"Set-ItemProperty -Path 'HKLM:{os.sep}{HAGS_KEY}' "
            f"-Name {HAGS_VALUE} -Value {value}"
        )
        ok = self._elevate(
            ("powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script)
        )
        if not ok:
            raise OptimizerError(f"HAGS change was cancelled at the UAC prompt")

    def _reg_get_dword(self, hive: str, key: str, name: str) -> tuple[int | None, str | None]:
        try:
            return int(self._reg_get(hive, key, name)), None
        except FileNotFoundError:
            return None, None
        except OSError as e:
            return None, f"cannot read {name}: {e}"

    def _reg_set_dword(self, hive: str, key: str, name: str, value: int) -> None:
        try:
            self._reg_set(hive, key, name, int(value))
        except OSError as e:
            raise OptimizerError(f"cannot write {name}: {e}") from e

    @staticmethod
    def _default_reg_get(hive: str, key: str, name: str) -> int:
        import winreg

        root = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(root, key, 0, winreg.KEY_READ) as handle:
            data, _vtype = winreg.QueryValueEx(handle, name)
        return int(data)

    @staticmethod
    def _default_reg_set(hive: str, key: str, name: str, value: int) -> None:
        import winreg

        root = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        with winreg.CreateKeyEx(root, key, 0, winreg.KEY_SET_VALUE) as handle:
            winreg.SetValueEx(handle, name, 0, winreg.REG_DWORD, int(value))

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
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out

    @staticmethod
    def _default_elevate(args: Sequence[str]) -> bool:
        execute = ctypes.windll.shell32.ShellExecuteW
        result = execute(None, "runas", str(args[0]), " ".join(f'"{a}"' for a in args[1:]), None, 1)
        return int(result) > 32

    @staticmethod
    def _default_is_admin() -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
