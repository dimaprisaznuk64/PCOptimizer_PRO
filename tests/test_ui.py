from __future__ import annotations

from app.ui.main_window import MainWindow
from app.ui.sidebar import NAV_ITEMS


def test_all_nav_keys_have_pages(qapp) -> None:
    window = MainWindow()
    assert set(window._index_by_key) == {key for key, _ in NAV_ITEMS}
    assert window.stack.count() == len(NAV_ITEMS)


def test_navigation_switches_pages(qapp) -> None:
    window = MainWindow()
    for key, _label in NAV_ITEMS:
        window.show_page(key)
        assert window.current_key == key
    window.close()


def test_sidebar_emits_navigation(qapp) -> None:
    window = MainWindow()
    window.sidebar.select("cleaner")
    assert window.current_key == "cleaner"
    window.sidebar.select("gpu")
    assert window.current_key == "gpu"
    window.close()


def test_initial_state_is_dashboard(qapp) -> None:
    window = MainWindow()
    assert window.current_key == "dashboard"
    assert window.sidebar._buttons["dashboard"].isChecked()
    window.close()


def test_unknown_key_is_ignored(qapp) -> None:
    window = MainWindow()
    before = window.current_key
    window.show_page("does-not-exist")
    assert window.current_key == before
    window.close()


def test_apply_theme_rebuilds_pages_and_preserves_state(qapp) -> None:
    from app.ui import theme as tract
    from app.ui.main_window import MainWindow

    orig = tract.CURRENT_THEME
    try:
        window = MainWindow()
        window.show_page("monitor")
        key_before = window.current_key

        window.apply_theme("CYBER")

        assert tract.CURRENT_THEME == "CYBER"
        assert tract.BG == tract.PALETTES["CYBER"]["BG"]
        assert window.stack.count() == len(NAV_ITEMS)
        assert set(window._index_by_key) == {key for key, _ in NAV_ITEMS}
        assert window.current_key == key_before
        assert window.page("settings")._on_theme_applied is not None
        window.close()
    finally:
        tract.set_theme(orig)


def test_settings_save_triggers_live_theme_apply(qapp, tmp_path, monkeypatch) -> None:
    import json

    from app.settings import SettingsService
    from app.ui.settings import SettingsPage

    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    calls: list[str] = []
    service = SettingsService()
    service.set("theme", "GRAPHITE")
    page = SettingsPage(
        service,
        log_directory=tmp_path / "logs",
        on_theme_applied=lambda name: calls.append(name),
    )
    page.load_values()
    page.theme_combo.setCurrentIndex(page.theme_combo.findData("FOREST"))
    page.save()

    assert calls == ["FOREST"]
    assert service.get("theme") == "FOREST"
    stored = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert stored["theme"] == "FOREST"
    page.close()
