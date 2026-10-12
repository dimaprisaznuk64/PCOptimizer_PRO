from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "PCOptimizer_PRO"

DEFAULTS: dict[str, Any] = {
    "sample_interval_ms": 1000,
    "minimize_to_tray": True,
    "start_minimized": False,
    "tray_metrics": True,
    "log_level": "INFO",
    "theme": "DARK",
    "language": "UA",
}

CHOICES: dict[str, tuple[str, ...]] = {
    "log_level": ("DEBUG", "INFO", "WARNING", "ERROR"),
    "theme": ("DARK", "PURPLE", "GREEN", "LIGHT", "AMOLED"),
    "language": ("UA", "EN"),
}

RANGES: dict[str, tuple[int, int]] = {
    "sample_interval_ms": (250, 10000),
}


class SettingsError(ValueError):
    pass


def default_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / APP_NAME / "settings.json"


class SettingsService:
    def __init__(self, path: Path | str | None = None, data: dict[str, Any] | None = None) -> None:
        self._path = Path(path) if path is not None else default_path()
        self._data: dict[str, Any] = dict(DEFAULTS)
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
        try:
            raw = self._path.read_text(encoding="utf-8")
        except OSError:
            return self.data
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
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
