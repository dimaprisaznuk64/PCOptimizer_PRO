from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path
from typing import Any

# NOTE: stdlib logging on purpose — importing app.logs here would create a
# circular import (app.logs.service already imports app.settings).
log = logging.getLogger("pcoptimizer.settings")

APP_NAME = "PCOptimizer_PRO"

DEFAULTS: dict[str, Any] = {
    "monitor_profile": "BALANCED",
    "sample_interval_ms": 1000,
    "minimize_to_tray": True,
    "start_minimized": False,
    "tray_metrics": True,
    "update_check_enabled": True,
    "log_level": "INFO",
    "theme": "TITANIUM",
    "ui_scale": 100,
    "language": "UA",
    "temp_alerts_enabled": True,
    "alerts_quiet_during_games": True,
    "usage_alerts_enabled": True,
    "first_run_completed": True,
    "dashboard_hidden": "",
    "overlay_enabled": False,
    "overlay_position": "",
    "presentmon_csv_path": "",
}

CHOICES: dict[str, tuple[str, ...]] = {
    "log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
    "monitor_profile": ("ECO", "BALANCED", "PERFORMANCE"),
    "theme": ("GRAPHITE", "TRUE_BLACK", "TITANIUM", "FOREST", "BURGUNDY", "MIDNIGHT",
              "AUBERGINE", "ESPRESSO", "ARCTIC", "IVORY", "MONO", "SAGE", "CYBER",
              "INDUSTRIAL", "TACTICAL", "PURPLE", "GREEN", "AMOLED"),
    "language": ("UA", "EN"),
}

RANGES: dict[str, tuple[int, int]] = {
    "sample_interval_ms": (250, 10000),
    "ui_scale": (100, 150),
}


class SettingsError(ValueError):
    pass


def data_root() -> Path:
    """Directory that holds settings, logs and other runtime data.

    Resolution order:
      1. PCOPTIMIZER_DATA env var (explicit override), e.g. D:\\...\\PCOptimizer_PRO\\data
      2. <executable dir>/data — for the frozen app (portable/next-to-exe, keeps data on the same drive as the app)
      3. <project root>/data — when running from source

    A one-time migration copies settings/logs from the legacy %LOCALAPPDATA%\\PCOptimizer_PRO
    folder so nothing is lost when switching to the new location.
    """
    env = os.environ.get("PCOPTIMIZER_DATA")
    if env:
        root = Path(env).expanduser()
        return _migrate_legacy(root)
    if getattr(sys, "frozen", False):
        root = Path(sys.executable).resolve().parent / "data"
        if _is_writable(root):
            return _migrate_legacy(root)
        # Installed under Program Files — exe folder is not writable without admin.
        root = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
        return _migrate_legacy(root)
    root = Path(__file__).resolve().parents[2] / "data"
    return _migrate_legacy(root)


def _is_writable(directory: Path) -> bool:
    """True if we can create/write files in *directory* (creating it if needed)."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def _atomic_copy_file(src: Path, dst: Path) -> None:
    """Copy a file through a temp name so a crash cannot leave a partial dst."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    try:
        shutil.copy2(src, tmp)
        with tmp.open("r+b") as f:
            os.fsync(f.fileno())
        tmp.replace(dst)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def _atomic_copytree(src: Path, dst: Path) -> None:
    """Stage a directory copy, then swap it in atomically."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(f".{dst.name}.{os.getpid()}.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    try:
        shutil.copytree(src, tmp, dirs_exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        tmp.replace(dst)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def _valid_json_file(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        json.loads(path.read_text(encoding="utf-8"))
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def _quarantine_file(path: Path) -> Path | None:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    target = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        path.replace(target)
        return target
    except OSError:
        return None


_migrated_roots: set[str] = set()


def _migrate_legacy(root: Path) -> Path:
    """One-time copy of runtime data from the old %LOCALAPPDATA% location into `root`.

    Copies are staged through temp names: a crash or disk-full must never leave
    a partial destination that later runs would skip because it "exists".
    """
    key = str(root)
    if key in _migrated_roots:
        return root
    legacy_base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
    if not legacy_base.exists():
        return root
    try:
        settings_dst = root / "settings.json"
        if not _valid_json_file(settings_dst):
            if settings_dst.exists():
                _quarantine_file(settings_dst)
            legacy_settings = legacy_base / "settings.json"
            if _valid_json_file(legacy_settings):
                _atomic_copy_file(legacy_settings, settings_dst)

        legacy_logs = legacy_base / "logs"
        if legacy_logs.exists() and not (root / "logs").exists():
            _atomic_copytree(legacy_logs, root / "logs")

        for name in (
            "optimizer_backup.json",
            "gaming_custom.json",
            "gaming_favorites.json",
            "gaming_history.json",
        ):
            src = legacy_base / name
            dst = root / name
            if _valid_json_file(dst):
                continue
            if dst.exists():
                _quarantine_file(dst)
            if _valid_json_file(src):
                _atomic_copy_file(src, dst)

        legacy_startup = legacy_base / "startup_backup"
        if legacy_startup.exists() and not (root / "startup_backup").exists():
            _atomic_copytree(legacy_startup, root / "startup_backup")
    except OSError as e:
        # Do not mark the root migrated: the next launch should retry.
        log.warning("legacy data migration failed for %s: %s", root, e)
        return root
    _migrated_roots.add(key)
    return root


def default_path() -> Path:
    return data_root() / "settings.json"


class SettingsService:
    def __init__(self, path: Path | str | None = None, data: dict[str, Any] | None = None) -> None:
        self._path = Path(path) if path is not None else default_path()
        self._data: dict[str, Any] = dict(DEFAULTS)
        self.load_error: str | None = None
        if data is not None:
            self.merge(data)
        else:
            self.load()

    @property
    def path(self) -> Path:
        return self._path

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._data)

    def load(self) -> dict[str, Any]:
        self._data = dict(DEFAULTS)
        self.load_error = None
        try:
            raw = self._path.read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            self.load_error = f"settings file is not valid UTF-8, defaults restored: {e}"
            log.warning("%s (%s)", self.load_error, self._path)
            return self.data
        except OSError:
            return self.data
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            # Keep the defaults running, but never swallow the problem.
            self.load_error = f"settings file is corrupt, defaults restored: {e}"
            log.warning("%s (%s)", self.load_error, self._path)
            return self.data
        if isinstance(parsed, dict):
            self.merge(parsed)
        return self.data

    def merge(self, values: dict[str, Any]) -> None:
        for key, value in values.items():
            if key in DEFAULTS:
                try:
                    self.set(key, value)
                except SettingsError:
                    continue

    def get(self, key: str) -> Any:
        if key not in DEFAULTS:
            raise SettingsError(f"unknown setting: {key}")
        return self._data[key]

    def set(self, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise SettingsError(f"unknown setting: {key}")
        self._data[key] = self._validate(key, value)

    def save(self) -> Path:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path)
        return self._path

    def reset(self) -> None:
        self._data = dict(DEFAULTS)

    def is_customized(self) -> bool:
        return any(self._data.get(k) != v for k, v in DEFAULTS.items())

    @staticmethod
    def _validate(key: str, value: Any) -> Any:
        default = DEFAULTS[key]
        if key in CHOICES:
            if not isinstance(value, str):
                raise SettingsError(f"{key} must be one of {CHOICES[key]}")
            normalized = value.strip().upper()
            if normalized not in CHOICES[key]:
                raise SettingsError(f"{key} must be one of {CHOICES[key]}")
            return normalized
        if isinstance(default, bool):
            if not isinstance(value, bool):
                raise SettingsError(f"{key} must be a bool")
            return value
        if isinstance(default, int):
            if isinstance(value, bool) or not isinstance(value, int):
                raise SettingsError(f"{key} must be an int")
            low, high = RANGES.get(key, (-(2**31), 2**31 - 1))
            if not low <= value <= high:
                raise SettingsError(f"{key} must be between {low} and {high}")
            return value
        if isinstance(default, str):
            if not isinstance(value, str):
                raise SettingsError(f"{key} must be a str")
            return value
        raise SettingsError(f"cannot validate {key}")
