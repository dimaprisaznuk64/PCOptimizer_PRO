from __future__ import annotations

import json

REQUIRED = [
    "BG", "PANEL", "PANEL_ALT", "BORDER", "BORDER_HI", "TEXT", "TEXT_DIM",
    "ACCENT", "ACCENT_HOVER", "ACCENT_TINT", "ACCENT_PRESSED", "ON_ACCENT",
    "DANGER", "OK", "WARN", "SIDEBAR_TOP", "SIDEBAR_BOTTOM", "HOVER",
    "DANGER_BG", "DANGER_BORDER", "DANGER_BG_HOVER", "OK_BG", "WARN_BG",
    "HERO_TOP", "BRAND_A", "BRAND_B", "GLOW_A", "GLOW_B",
    "GLOW_ALPHA_A", "GLOW_ALPHA_B", "C1", "C2", "C3", "C4",
]

EXPECTED = {
    "GRAPHITE", "TRUE_BLACK", "SLATE", "TITANIUM", "FOREST", "BURGUNDY",
    "MIDNIGHT", "AUBERGINE", "DEEP_TEAL", "ESPRESSO", "ARCTIC", "IVORY",
    "MONO", "SAGE", "PERFORMANCE_RED", "CYBER", "INDUSTRIAL", "TACTICAL",
    "COBALT", "COPPER",
    # legacy themes restored from v1.2.2
    "DARK", "PURPLE", "GREEN", "LIGHT", "AMOLED",
    "MINIMAL_DARK",
    "NEON_PULSE",
    "NEXUS",
    "ELECTRIC",
}


def test_bundled_geist_fonts_register(qapp) -> None:
    from PySide6.QtGui import QFontDatabase

    from app.ui import theme as tract

    loaded = tract.load_fonts()
    assert "Geist-Regular.ttf" in loaded
    assert "GeistMono-Regular.ttf" in loaded
    families = QFontDatabase.families()
    assert "Geist" in families
    assert "Geist Mono" in families


def test_curated_themes_include_legacy():
    from app.ui import theme as tract

    assert len(tract.PALETTES) == 29
    assert set(tract.PALETTES) == EXPECTED


def test_every_palette_has_all_required_tokens():
    from app.ui import theme as tract

    for name, pal in tract.PALETTES.items():
        missing = [k for k in REQUIRED if k not in pal]
        assert not missing, f"{name} missing tokens: {missing}"


def test_labels_cover_all_palettes():
    from app.ui import theme as tract

    assert set(tract.THEME_LABELS) == set(tract.PALETTES)


def test_settings_choices_match_palettes():
    from app.settings import CHOICES, DEFAULTS
    from app.ui import theme as tract

    assert CHOICES["theme"] == tuple(tract.PALETTES)
    assert DEFAULTS["theme"] == tract.DEFAULT_THEME


def test_set_theme_updates_globals_and_resolves_aliases():
    from app.ui import theme as tract

    orig = tract.CURRENT_THEME
    try:
        assert tract.set_theme("FOREST") == "FOREST"
        assert tract.BG == tract.PALETTES["FOREST"]["BG"]
        assert tract.set_theme("DARK") == "DARK"
        assert tract.BG == tract.PALETTES["DARK"]["BG"]
        assert tract.set_theme("MATRIX") == "CYBER"
        assert tract.BG == tract.PALETTES["CYBER"]["BG"]
        assert tract.set_theme("bogus_name") == tract.DEFAULT_THEME
    finally:
        tract.set_theme(orig)


def test_saved_theme_aliases_migrate_old_names(tmp_path, monkeypatch):
    from app.ui import theme as tract

    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "NORD"}), encoding="utf-8")
    assert tract.saved_theme() == "MIDNIGHT"


def test_saved_theme_unknown_falls_back(tmp_path, monkeypatch):
    from app.ui import theme as tract

    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "NEON_XYZ"}), encoding="utf-8")
    assert tract.saved_theme() == tract.DEFAULT_THEME


def test_saved_theme_honors_kept_name(tmp_path, monkeypatch):
    from app.ui import theme as tract

    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    (tmp_path / "settings.json").write_text(json.dumps({"theme": "COBALT"}), encoding="utf-8")
    assert tract.saved_theme() == "COBALT"


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a: str, b: str) -> float:
    la, lb = _luminance(a), _luminance(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def test_ui_scale_updates_type_scale_and_stylesheet():
    from app.ui import theme as tract

    original = tract.UI_SCALE
    try:
        base_body = tract.T_BODY
        base_pad = tract.CARD_PADDING
        base_margin = tract.PAGE_MARGINS
        base_topbar = tract.TOPBAR_HEIGHT
        base_sidebar = tract.SIDEBAR_WIDTH
        base_radius = tract.RADIUS_LG
        assert tract.set_ui_scale(150) == 150
        assert tract.UI_SCALE == 150
        assert tract.T_BODY > base_body
        assert tract.BASE_FONT_PX == round(13 * tract.FONT_SCALE)
        assert tract.LAYOUT_SCALE > 1
        assert tract.CARD_PADDING > base_pad
        assert all(
            new >= old
            for new, old in zip(tract.PAGE_MARGINS, base_margin, strict=False)
        )
        assert tract.TOPBAR_HEIGHT > base_topbar
        assert tract.SIDEBAR_WIDTH > base_sidebar
        assert tract.RADIUS_LG > base_radius
        stylesheet = tract.build_stylesheet()
        assert f"font-size: {tract.T_BODY}px" in stylesheet
        assert f"padding: {tract.TOPBAR_ICON_PAD}px" in stylesheet

        assert tract.set_ui_scale(200) == 150
        assert tract.set_ui_scale(50) == 100
        assert tract.T_BODY == base_body
        assert tract.CARD_PADDING == base_pad
        assert tract.PAGE_MARGINS == base_margin
        assert tract.TOPBAR_HEIGHT == base_topbar
        assert tract.SIDEBAR_WIDTH == base_sidebar
        assert tract.RADIUS_LG == base_radius
    finally:
        tract.set_ui_scale(original)


def test_ui_scale_survives_module_reload():
    import importlib

    from app.ui import theme as tract

    original = tract.UI_SCALE
    try:
        tract.set_ui_scale(130)
        importlib.reload(tract)
        assert tract.UI_SCALE == 130
        assert tract.T_BODY == tract.fs(13)
    finally:
        tract.set_ui_scale(original)
        importlib.reload(tract)


def test_ui_scale_reads_startup_environment(monkeypatch):
    import importlib

    from app.ui import theme as tract

    original = tract.UI_SCALE
    monkeypatch.setenv("PCOPTIMIZER_UI_SCALE", "135")
    monkeypatch.delattr(tract, "UI_SCALE", raising=False)
    try:
        importlib.reload(tract)
        assert tract.UI_SCALE == 135
        assert tract.T_BODY == tract.fs(13)
        assert tract.SIDEBAR_WIDTH == tract.ls(238)
    finally:
        tract.set_ui_scale(original)


def test_secondary_text_uses_readable_ui_font():
    import re

    from app.ui import theme as tract

    stylesheet = tract.build_stylesheet()
    for selector in ("QLabel#cardSub", "QLabel#cardRow"):
        match = re.search(re.escape(selector) + r"\s*\{([^}]+)\}", stylesheet)
        assert match is not None, f"{selector} missing from stylesheet"
        block = match.group(1)
        assert tract.FONT_UI in block
        assert "font-weight: 500" in block
        assert "letter-spacing" in block


def test_all_palettes_have_readable_text_and_status_colors():
    from app.ui import theme as tract

    for name, pal in tract.PALETTES.items():
        for fg in ("TEXT", "TEXT_DIM", "ACCENT", "OK", "WARN", "DANGER"):
            for surface in ("BG", "PANEL", "PANEL_ALT"):
                assert _contrast(pal[fg], pal[surface]) >= 4.5, (name, fg, surface)
        assert _contrast(pal["ON_ACCENT"], pal["ACCENT"]) >= 4.5, name


def test_light_palettes_keep_dim_text_readable():
    from app.ui import theme as tract

    checked = 0
    for pal in tract.PALETTES.values():
        if _luminance(pal["BG"]) < 0.3:
            continue
        checked += 1
        for surface in ("PANEL", "PANEL_ALT"):
            assert _contrast(pal["TEXT"], pal[surface]) >= 4.5
            assert _contrast(pal["TEXT_DIM"], pal[surface]) >= 4.5
    assert checked >= 5