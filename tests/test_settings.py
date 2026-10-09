from __future__ import annotations

import json

import pytest

from app.settings import DEFAULTS, SettingsError, SettingsService


def test_defaults_when_file_missing(tmp_path) -> None:
    svc = SettingsService(tmp_path / "settings.json")
    assert svc.get("sample_interval_ms") == DEFAULTS["sample_interval_ms"]
    assert svc.get("minimize_to_tray") is True
    assert svc.get("log_level") == "INFO"


def test_save_and_reload(tmp_path) -> None:
    path = tmp_path / "settings.json"
    svc = SettingsService(path)
    svc.set("sample_interval_ms", 2000)
    svc.set("minimize_to_tray", False)
    svc.set("log_level", "debug")
    svc.save()

    assert path.exists()
    reloaded = SettingsService(path)
    assert reloaded.get("sample_interval_ms") == 2000
    assert reloaded.get("minimize_to_tray") is False
    assert reloaded.get("log_level") == "DEBUG"


def test_save_is_valid_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    svc = SettingsService(path)
    svc.set("start_minimized", True)
    svc.save()
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["start_minimized"] is True
    assert set(DEFAULTS) <= set(raw)


def test_unknown_key_raises(tmp_path) -> None:
    svc = SettingsService(tmp_path / "settings.json")
    with pytest.raises(SettingsError):
        svc.get("nope")
    with pytest.raises(SettingsError):
        svc.set("nope", 1)


@pytest.mark.parametrize(
    "key,value",
    [
        ("sample_interval_ms", 100),
        ("sample_interval_ms", 99999),
        ("sample_interval_ms", "fast"),
        ("sample_interval_ms", True),
        ("minimize_to_tray", "yes"),
        ("log_level", "LOUD"),
        (42, "x"),
    ],
)
def test_invalid_values_raise(tmp_path, key, value) -> None:
    svc = SettingsService(tmp_path / "settings.json")
    with pytest.raises(SettingsError):
        svc.set(key, value)


def test_load_ignores_corrupt_json(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{ not json", encoding="utf-8")
    svc = SettingsService(path)
    assert svc.get("log_level") == "INFO"


def test_load_ignores_invalid_entries(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps({"log_level": "LOUD", "sample_interval_ms": 5, "unknown": 1}),
        encoding="utf-8",
    )
    svc = SettingsService(path)
    assert svc.get("log_level") == "INFO"
    assert svc.get("sample_interval_ms") == DEFAULTS["sample_interval_ms"]


def test_reset_restores_defaults(tmp_path) -> None:
    svc = SettingsService(tmp_path / "settings.json")
    svc.set("sample_interval_ms", 5000)
    svc.set("tray_metrics", False)
    assert svc.is_customized()
    svc.reset()
    assert svc.get("sample_interval_ms") == DEFAULTS["sample_interval_ms"]
    assert svc.get("tray_metrics") is True
    assert not svc.is_customized()


def test_data_is_a_copy(tmp_path) -> None:
    svc = SettingsService(tmp_path / "settings.json")
    data = svc.data
    data["log_level"] = "ERROR"
    assert svc.get("log_level") == "INFO"
