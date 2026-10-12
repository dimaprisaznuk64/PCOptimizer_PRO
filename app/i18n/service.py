"""PCOptimizer_PRO — Localization service with dynamic language switching."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from .translations import TRANSLATIONS


class I18nService(QObject):
    language_changed = Signal(str)

    _instance: I18nService | None = None

    def __init__(self, default_lang: str = "UA", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._current_lang = "UA"
        self.set_language(default_lang, emit=False)

    @classmethod
    def instance(cls) -> I18nService:
        if cls._instance is None:
            cls._instance = I18nService()
        return cls._instance

    @property
    def current_language(self) -> str:
        return self._current_lang

    def set_language(self, lang: str, emit: bool = True) -> None:
        normalized = lang.strip().upper() if isinstance(lang, str) else "UA"
        if normalized not in TRANSLATIONS:
            normalized = "UA"
        if normalized != self._current_lang or not emit:
            self._current_lang = normalized
            if emit:
                self.language_changed.emit(self._current_lang)

    def toggle_language(self) -> str:
        next_lang = "EN" if self._current_lang == "UA" else "UA"
        self.set_language(next_lang)
        return next_lang

    def t(self, key: str, **kwargs: Any) -> str:
        dictionary = TRANSLATIONS.get(self._current_lang, TRANSLATIONS["UA"])
        template = dictionary.get(key)
        if template is None:
            template = TRANSLATIONS["EN"].get(key, key)
        if kwargs:
            try:
                return template.format(**kwargs)
            except Exception:
                return template
        return template


def tr(key: str, **kwargs: Any) -> str:
    """Convenient translation helper."""
    return I18nService.instance().t(key, **kwargs)
