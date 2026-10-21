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