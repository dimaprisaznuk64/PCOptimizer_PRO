"""Tests for PCOptimizer_PRO i18n module."""

from __future__ import annotations

import ast
from pathlib import Path

from app.i18n import TRANSLATIONS, I18nService, tr


def test_translations_dictionary_keys_match() -> None:
    en_keys = set(TRANSLATIONS["EN"])
    uk_keys = set(TRANSLATIONS["UA"])
    assert len(en_keys) > 30
    assert len(uk_keys) > 30
    assert en_keys == uk_keys


def test_i18n_service_default_and_switch() -> None:
    service = I18nService.instance()
    service.set_language("UA", emit=False)
    assert service.current_language == "UA"
    assert tr("app_title") == "PCOptimizer PRO"
    assert tr("nav_dashboard") == "Панель керування"

    service.set_language("EN", emit=False)
    assert service.current_language == "EN"
    assert tr("nav_dashboard") == "Dashboard"

    service.set_language("UA", emit=False)


def test_i18n_toggle() -> None:
    service = I18nService.instance()
    service.set_language("UA", emit=False)
    next_lang = service.toggle_language()
    assert next_lang == "EN"
    assert service.current_language == "EN"
    next_lang = service.toggle_language()
    assert next_lang == "UA"
    assert service.current_language == "UA"


def test_i18n_interpolation() -> None:
    service = I18nService.instance()
    service.set_language("EN", emit=False)
    assert tr("proc_count", count=42) == "42 processes"
    assert tr("clean_freed", size="1.2GB") == "Freed 1.2GB"

    service.set_language("UA", emit=False)
    assert tr("proc_count", count=42) == "42 процесів"
    assert tr("clean_freed", size="1.2GB") == "Звільнено 1.2GB"


def test_stage2_translation_keys_are_resolved() -> None:
    root = Path(__file__).resolve().parents[1]
    files = (
        "app/benchmarks/hardware.py",
        "app/ui/hardware_benchmark.py",
        "app/temperature/service.py",
        "app/ui/temperature.py",
        "app/reports/center.py",
        "app/ui/export_center.py",
    )
    prefixes = (
        "hwb_",
        "temp_",
        "export_center_",
        "export_kind_",
        "export_fmt_",
        "nav_temperature",
        "nav_hardware_benchmark",
        "nav_export_center",
    )
    ignore = {"export_fmt_", "temp_status_", "temp_cpu", "temp_gpu"}
    keys: set[str] = set()
    for relative in files:
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and node.value.startswith(prefixes)
            ):
                keys.add(node.value)
    keys.update(f"export_fmt_{fmt}" for fmt in ("csv", "json", "html", "pdf"))
    keys.update(f"temp_status_{status}" for status in ("ok", "warn", "danger"))
    keys.difference_update(ignore)

    assert keys
    for key in sorted(keys):
        assert TRANSLATIONS["EN"].get(key), key
        assert TRANSLATIONS["UA"].get(key), key
        assert TRANSLATIONS["EN"][key] != key
        assert TRANSLATIONS["UA"][key] != key


def test_overlay_translation_keys_are_resolved() -> None:
    root = Path(__file__).parent.parent
    prefixes = ("overlay_", "tray_overlay", "set_overlay", "set_presentmon")
    keys: set[str] = set()
    for relative in ("app/overlay/widget.py", "app/ui/settings.py", "app/ui/tray.py"):
        tree = ast.parse((root / relative).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
            if name != "tr":
                continue
            arg = node.args[0]
            if (
                isinstance(arg, ast.Constant)
                and isinstance(arg.value, str)
                and arg.value.startswith(prefixes)
            ):
                keys.add(arg.value)
    assert keys
    for key in sorted(keys):
        assert TRANSLATIONS["EN"].get(key), key
        assert TRANSLATIONS["UA"].get(key), key
