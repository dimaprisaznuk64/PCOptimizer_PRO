from __future__ import annotations

from app.ui.main_window import MainWindow
from app.ui.sidebar import NAV_ITEMS


def test_all_nav_keys_have_pages(qapp) -> None:
    window = MainWindow()
    assert set(window._index_by_key) == {key for key, _ in NAV_ITEMS}
    assert window.stack.count() == len(NAV_ITEMS)


def test_all_nav_keys_have_icon_drawer(qapp) -> None:
    from app.ui.icons import _DRAWERS
    from app.ui.sidebar import NAV_KEYS

    for key, _label in NAV_KEYS:
        assert key in _DRAWERS, f"nav item '{key}' has no icon drawer"


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


def _rect_in(widget, parent):
    from PySide6.QtCore import QPoint, QRect

    return QRect(widget.mapTo(parent, QPoint(0, 0)), widget.rect().size())


def test_sidebar_nav_is_scrollable(qapp) -> None:
    from PySide6.QtWidgets import QScrollArea

    window = MainWindow()
    sb = window.sidebar
    assert isinstance(sb.nav_scroll, QScrollArea)
    host = sb.nav_scroll.widget()
    assert host is not None
    for button in sb._buttons.values():
        assert button.parent() is host
    window.close()


def test_sidebar_layout_no_overlap(qapp) -> None:
    """Nav list, info card and status pill must never overlap at any height."""
    window = MainWindow()
    sb = window.sidebar
    for _name, w, h in [
        ("fullscreen", 1920, 1080),
        ("normal", 1280, 800),
        ("rail-min", 1200, 680),
        ("compact", 1024, 640),
    ]:
        window.resize(w, h)
        window.show()
        qapp.processEvents()

        rects = {
            "nav": _rect_in(sb.nav_scroll, sb),
            "card": _rect_in(sb.user_card, sb),
            "status": _rect_in(sb.status, sb),
        }
        # Hidden widgets keep a stale geometry - they cannot overlap anything.
        visible = dict(rects)
        for name, widget in (
            ("card", sb.user_card),
            ("status", sb.status),
        ):
            if not widget.isVisible():
                visible.pop(name, None)
        keys = list(visible)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                assert visible[a].intersected(visible[b]).isEmpty(), (w, h, a, b)
        for name, r in visible.items():
            assert r.top() >= 0 and r.bottom() <= sb.height(), (w, h, name)
    window.close()


def test_sidebar_collapses_to_icons_on_narrow_windows(qapp) -> None:
    """Under 1200 px the rail shows icons only and keeps the label as tooltip."""
    from app.ui.sidebar import SIDEBAR_COMPACT_WIDTH, SIDEBAR_WIDTH

    window = MainWindow()
    sb = window.sidebar

    window.resize(1440, 900)
    window.show()
    qapp.processEvents()
    assert sb.compact is False
    assert sb.width() == SIDEBAR_WIDTH
    assert sb._buttons["dashboard"].text().strip() != ""

    window.resize(1100, 700)
    qapp.processEvents()
    assert sb.compact is True
    assert sb.width() == SIDEBAR_COMPACT_WIDTH
    button = sb._buttons["dashboard"]
    assert button.text() == ""
    assert button.toolTip() != ""
    assert sb.user_card.isVisible() is False

    window.resize(1440, 900)
    qapp.processEvents()
    assert sb.compact is False
    assert sb.width() == SIDEBAR_WIDTH
    assert sb._buttons["dashboard"].text().strip() != ""
    window.close()


def test_sidebar_brand_not_clipped(qapp) -> None:
    from PySide6.QtWidgets import QLabel

    window = MainWindow()
    window.resize(1120, 680)
    window.show()
    qapp.processEvents()
    brand = window.sidebar.findChild(QLabel, "brand")
    assert brand is not None
    assert brand.width() >= brand.sizeHint().width()
    window.close()

