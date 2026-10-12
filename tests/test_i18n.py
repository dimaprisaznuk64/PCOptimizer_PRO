"""Tests for PCOptimizer_PRO i18n module."""

from __future__ import annotations

import pytest

from app.i18n import I18nService, TRANSLATIONS, tr


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
