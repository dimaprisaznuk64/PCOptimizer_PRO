from __future__ import annotations

import sys
from pathlib import Path

_LOADED = False
_FAMILIES: dict[str, str] = {}


def fonts_dir() -> Path:
    """Directory with the bundled TTF files (source tree or frozen bundle)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base) / "assets" / "fonts"
    return Path(__file__).resolve().parents[2] / "assets" / "fonts"


def load_bundled_fonts() -> dict[str, str]:
    """Register the bundled Inter / IBM Plex Mono TTFs with Qt.

    Returns a mapping like ``{"ui": "Inter", "mono": "IBM Plex Mono"}`` for the
    families that were actually registered. Safe to call more than once.
    """
    global _LOADED
    if _LOADED:
        return dict(_FAMILIES)

    from PySide6.QtGui import QFontDatabase

    directory = fonts_dir()
    families: set[str] = set()
    if directory.is_dir():
        for ttf in sorted(directory.glob("*.ttf")):
            font_id = QFontDatabase.addApplicationFont(str(ttf))
            if font_id != -1:
                families.update(QFontDatabase.applicationFontFamilies(font_id))

    mapping: dict[str, str] = {}
    if "Inter" in families:
        mapping["ui"] = "Inter"
        mapping["display"] = "Inter"
    if "IBM Plex Mono" in families:
        mapping["mono"] = "IBM Plex Mono"

    _FAMILIES.clear()
    _FAMILIES.update(mapping)
    _LOADED = True
    return dict(_FAMILIES)


def bundled_families() -> dict[str, str]:
    return dict(_FAMILIES)
