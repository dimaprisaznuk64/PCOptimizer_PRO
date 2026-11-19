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


def test_back_button_disabled_on_root_page(qapp) -> None:
    window = MainWindow()
    assert window.current_key == "dashboard"
    assert window.topbar.back_button.isEnabled() is False
    window.close()


def test_back_button_returns_to_previous_page(qapp) -> None:
    window = MainWindow()
    window.show_page("monitor")
    window.show_page("gpu")
    assert window.topbar.back_button.isEnabled() is True

    window.topbar.back_button.click()
    assert window.current_key == "monitor"
    assert window.topbar.back_button.isEnabled() is True

    window.topbar.back_button.click()
    assert window.current_key == "dashboard"
    assert window.topbar.back_button.isEnabled() is False
    window.close()


def test_repeated_page_does_not_grow_history(qapp) -> None:
    window = MainWindow()
    window.show_page("monitor")
    window.show_page("monitor")
    window.go_back()
    assert window.current_key == "dashboard"
    assert window.topbar.back_button.isEnabled() is False
    window.close()


def test_back_navigation_survives_theme_rebuild(qapp) -> None:
    window = MainWindow()
    window.show_page("monitor")
    window.show_page("gpu")
    window.apply_theme("CYBER")
    assert window.current_key == "gpu"
    assert window.topbar.back_button.isEnabled() is True
    window.topbar.back_button.click()
    assert window.current_key == "monitor"
    window.close()


def test_alt_left_shortcut_goes_back(qapp) -> None:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = MainWindow()
    window.show()
    window.show_page("monitor")
    window.show_page("gpu")
    qapp.processEvents()
    QTest.keyClick(window, Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    qapp.processEvents()
    assert window.current_key == "monitor"
    window.close()


def test_nav_groups_cover_all_keys_once(qapp) -> None:
    from app.ui.sidebar import NAV_GROUPS, NAV_KEYS

    grouped = [key for _group, _tr, keys in NAV_GROUPS for key in keys]
    assert len(NAV_GROUPS) == 7
    assert len(grouped) == len(set(grouped)) == len(NAV_KEYS)
    assert set(grouped) == {key for key, _tr in NAV_KEYS}


def test_group_headers_collapse_and_expand(qapp) -> None:
    window = MainWindow()
    sb = window.sidebar
    assert len(sb._group_buttons) == 7
    assert set(sb._group_keys["overview"]) == {"dashboard", "health"}

    sb.toggle_group("overview")
    assert sb.collapsed_groups() == ("overview",)
    assert sb._buttons["dashboard"].isHidden() is True
    assert sb._buttons["health"].isHidden() is True
    assert sb._buttons["gpu"].isHidden() is False

    sb.toggle_group("overview")
    assert sb.collapsed_groups() == ()
    assert sb._buttons["dashboard"].isHidden() is False
    window.close()


def test_collapsed_group_expands_on_navigation(qapp) -> None:
    window = MainWindow()
    sb = window.sidebar
    sb.toggle_group("gaming")
    assert sb._buttons["launcher"].isHidden() is True

    window.show_page("launcher")
    assert window.current_key == "launcher"
    assert sb._buttons["launcher"].isHidden() is False
    assert sb.collapsed_groups() == ()
    window.close()


def test_group_state_survives_theme_rebuild(qapp) -> None:
    from app.ui import theme as tract

    orig = tract.CURRENT_THEME
    try:
        window = MainWindow()
        window.sidebar.toggle_group("tools")
        assert window.sidebar.collapsed_groups() == ("tools",)

        window.apply_theme("CYBER")
        assert window.sidebar.collapsed_groups() == ("tools",)
        assert window.sidebar._buttons["export_center"].isHidden() is True
        window.close()
    finally:
        tract.set_theme(orig)


def test_group_headers_follow_compact_and_language(qapp) -> None:
    from app.i18n import I18nService

    window = MainWindow()
    sb = window.sidebar
    header = sb._group_buttons["overview"]
    assert header.text().startswith("▾")

    window.resize(1024, 640)
    window.show()
    qapp.processEvents()
    assert header.text() == "─"
    assert header.toolTip() != ""

    window.resize(1440, 900)
    qapp.processEvents()
    assert len(header.text()) > 2

    I18nService.instance().set_language("EN")
    assert "OVERVIEW" in header.text()
    I18nService.instance().set_language("UA")
    assert "ОГЛЯД" in header.text()
    window.close()


def test_nav_tooltips_describe_destination(qapp) -> None:
    from app.i18n import tr
    from app.ui.sidebar import NAV_KEYS

    window = MainWindow()
    sb = window.sidebar
    for key, _label_key in NAV_KEYS:
        tip = sb._buttons[key].toolTip()
        assert tip == tr(f"tip_nav_{key}"), key
        assert tip

    sb.set_compact(True)
    compact_tip = sb._buttons["monitor"].toolTip()
    assert tr("nav_monitor") in compact_tip
    assert tr("tip_nav_monitor") in compact_tip
    window.close()


def test_group_header_tooltip_includes_count(qapp) -> None:
    from app.i18n import tr

    window = MainWindow()
    header = window.sidebar._group_buttons["overview"]
    summary = tr("nav_group_count", group=tr("nav_group_overview"), count=2)
    assert summary in header.toolTip()
    assert "· 2" in header.text()
    window.close()


def test_topbar_status_tooltip_follows_set_status(qapp) -> None:
    from app.i18n import tr

    window = MainWindow()
    window.topbar.set_status("Busy", "warn")
    assert window.topbar.status.toolTip() == tr("topbar_status_tip", text="Busy")
    window.close()


def test_topbar_pulse_uses_shared_motion_token(qapp) -> None:
    from app.ui import theme as tract

    window = MainWindow()
    assert window.topbar._pulse.duration() == tract.MOTION_PULSE
    window.close()


def test_topbar_title_follows_live_language_switch(qapp) -> None:
    from app.i18n import I18nService, tr

    window = MainWindow()
    window.show_page("settings")
    i18n = I18nService.instance()

    i18n.set_language("EN")
    assert window.topbar.title.text() == tr("nav_settings") == "Settings"
    assert window.topbar.title.text().isascii()

    window.show_page("monitor")
    assert window.topbar.title.text() == tr("nav_monitor")

    i18n.set_language("UA")
    assert window.topbar.title.text() == tr("nav_monitor")
    assert not window.topbar.title.text().isascii()
    window.close()


def test_scaled_layout_tokens_reach_topbar_and_sidebar(qapp) -> None:
    import importlib

    from app.ui import sidebar as sidebar_mod
    from app.ui import theme as tract
    from app.ui import topbar as topbar_mod

    original = tract.UI_SCALE
    try:
        assert tract.set_ui_scale(150) == 150
        importlib.reload(topbar_mod)
        importlib.reload(sidebar_mod)

        bar = topbar_mod.TopBar()
        rail = sidebar_mod.Sidebar()
        assert bar.height() == tract.TOPBAR_HEIGHT
        assert bar.back_button.iconSize().width() == tract.ICON_SIZE
        assert bar.status.height() == tract.STATUS_HEIGHT
        assert rail.width() == tract.SIDEBAR_WIDTH
        assert rail._buttons["dashboard"].iconSize().width() == tract.NAV_ICON_SIZE
        bar.close()
        rail.close()
    finally:
        tract.set_ui_scale(original)
        importlib.reload(topbar_mod)
        importlib.reload(sidebar_mod)


def test_apply_ui_scale_updates_theme_and_rebuilds_pages(qapp, monkeypatch) -> None:
    from app.ui import theme as tract

    original = tract.UI_SCALE
    window = MainWindow()
    applied: list[str] = []
    monkeypatch.setattr(window, "apply_theme", applied.append)
    try:
        window.apply_ui_scale(140)
        assert tract.UI_SCALE == 140
        assert tract.T_BODY == tract.fs(13)
        assert applied == [tract.CURRENT_THEME]
        tract.apply(qapp)
        assert f"font-size: {tract.T_BODY}px" in qapp.styleSheet()
    finally:
        tract.set_ui_scale(original)
        tract.apply(qapp)
        window.close()

