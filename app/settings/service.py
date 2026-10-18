from __future__ import annotations

import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

# NOTE: stdlib logging on purpose — importing app.logs here would create a
# circular import (app.logs.service already imports app.settings).
log = logging.getLogger("pcoptimizer.settings")

APP_NAME = "PCOptimizer_PRO"

DEFAULTS: dict[str, Any] = {
    "sample_interval_ms": 1000,
    "minimize_to_tray": True,
    "start_minimized": False,
    "tray_metrics": True,
    "log_level": "INFO",
    "theme": "GRAPHITE",
    "language": "UA",
    "temp_alerts_enabled": True,
    "temp_alert_cpu": 90,
    "temp_alert_gpu": 87,
}

CHOICES: dict[str, tuple[str, ...]] = {
    "log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
    "theme": ("GRAPHITE", "TRUE_BLACK", "SLATE", "TITANIUM", "FOREST", "BURGUNDY", "MIDNIGHT",
              "AUBERGINE", "DEEP_TEAL", "ESPRESSO", "ARCTIC", "IVORY", "MONO", "SAGE",
              "PERFORMANCE_RED", "CYBER", "INDUSTRIAL", "TACTICAL", "COBALT", "COPPER",
              "DARK", "PURPLE", "GREEN", "LIGHT", "AMOLED"),
    "language": ("UA", "EN"),
}

RANGES: dict[str, tuple[int, int]] = {
    "sample_interval_ms": (250, 10000),
    "temp_alert_cpu": (50, 110),
    "temp_alert_gpu": (50, 110),
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
    return root


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


_migrated_roots: set[str] = set()


def _migrate_legacy(root: Path) -> Path:
    """One-time copy of runtime data from the old %LOCALAPPDATA% location into `root`."""
    key = str(root)
    if key in _migrated_roots:
        return root
    _migrated_roots.add(key)
    legacy_base = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / APP_NAME
    if not legacy_base.exists():
        return root
    try:
        if not (root / "settings.json").exists():
            legacy_settings = legacy_base / "settings.json"
            if legacy_settings.exists():
                root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(legacy_settings, root / "settings.json")
        legacy_logs = legacy_base / "logs"
        if legacy_logs.exists() and not (root / "logs").exists():
            shutil.copytree(legacy_logs, root / "logs", dirs_exist_ok=True)
        for name in (
            "optimizer_backup.json",
            "gaming_custom.json",
            "gaming_favorites.json",
            "gaming_history.json",
        ):
            src = legacy_base / name
            dst = root / name
            if src.exists() and not dst.exists():
                root.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        legacy_startup = legacy_base / "startup_backup"
        if legacy_startup.exists() and not (root / "startup_backup").exists():
            shutil.copytree(legacy_startup, root / "startup_backup", dirs_exist_ok=True)
    except OSError:
        pass
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
            self._migrate_temp_split(parsed)
            self.merge(parsed)
        return self.data

    @staticmethod
    def _migrate_temp_split(parsed: dict[str, Any]) -> None:
        """Seed the new CPU threshold from the legacy single `temp_alert_celsius`."""
        legacy = parsed.get("temp_alert_celsius")
        if isinstance(legacy, int) and "temp_alert_cpu" not in parsed:
            parsed["temp_alert_cpu"] = legacy

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
