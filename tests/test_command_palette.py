from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtTest import QTest

from app.i18n import I18nService, tr
from app.ui.command_palette import build_entries, search_entries
from app.ui.main_window import MainWindow


def test_search_entries_matches_label_description_and_group() -> None:
    entries = build_entries()
    assert [entry.key for entry in search_entries(entries, "gpu")][:1] == ["gpu"]
    assert "cleaner" in [entry.key for entry in search_entries(entries, "temporary files")]
    assert "history" in [entry.key for entry in search_entries(entries, "monitoring")]


def test_search_entries_ranks_label_matches_first() -> None:
    from app.i18n import tr

    entries = build_entries()
    results = search_entries(entries, "disk")
    label = tr("nav_disk").casefold()
    assert results[0].key == "disk"
    assert label in results[0].label.casefold()
    assert len(results) > 1


def test_search_entries_empty_query_keeps_order() -> None:
    entries = build_entries()
    assert search_entries(entries, "   ") == entries
    assert search_entries(entries, "nothing matches this") == []


def test_build_entries_pins_recent_first() -> None:
    entries = build_entries(["gpu", "cleaner"])
    assert [entry.key for entry in entries[:2]] == ["gpu", "cleaner"]
    assert entries[0].group == "Recent"
    assert len({entry.key for entry in entries}) == len(entries)


def test_palette_shows_results_and_placeholder(qapp) -> None:
    window = MainWindow()
    window.open_search()
    palette = window._palette
    assert palette.isVisible()
    assert palette.result_list.count() == len(build_entries())
    assert palette.search.placeholderText() == tr("palette_placeholder")
    assert palette.result_list.currentItem().data(Qt.ItemDataRole.UserRole) == "dashboard"
    window.close()


def test_palette_filters_and_enter_selects_page(qapp) -> None:
    window = MainWindow()
    window.open_search()
    palette = window._palette
    palette.search.setText("gpu")
    assert palette.result_list.item(0).data(Qt.ItemDataRole.UserRole) == "gpu"
    QTest.keyClick(palette.search, Qt.Key.Key_Return)
    assert window.current_key == "gpu"
    assert not palette.isVisible()
    window.close()


def test_palette_escape_hides(qapp) -> None:
    window = MainWindow()
    window.open_search()
    QTest.keyClick(window._palette.search, Qt.Key.Key_Escape)
    assert not window._palette.isVisible()
    window.close()


def test_palette_arrow_keys_move_selection(qapp) -> None:
    window = MainWindow()
    window.open_search()
    palette = window._palette
    first = palette.result_list.item(0).data(Qt.ItemDataRole.UserRole)
    QTest.keyClick(palette.search, Qt.Key.Key_Down)
    second = palette.result_list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert second != first
    QTest.keyClick(palette.search, Qt.Key.Key_Up)
    assert palette.result_list.currentItem().data(Qt.ItemDataRole.UserRole) == first
    window.close()


def test_topbar_button_and_shortcut_open_palette(qapp) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()
    QTest.mouseClick(window.topbar.search_button, Qt.MouseButton.LeftButton)
    assert window._palette.isVisible()
    window._palette.hide()
    QTest.keySequence(window, QKeySequence("Ctrl+K"))
    assert window._palette.isVisible()
    window.close()


def test_palette_follows_live_language_switch(qapp) -> None:
    window = MainWindow()
    window.open_search()
    I18nService.instance().set_language("UA")
    assert "Пошук" in window._palette.search.placeholderText()
    assert window._palette.result_list.item(0).text().endswith("Огляд")
    window.close()


def test_palette_survives_theme_rebuild(qapp, monkeypatch) -> None:
    from app.ui import theme

    original = theme.CURRENT_THEME
    try:
        window = MainWindow()
        monkeypatch.setattr(window, "_reload_ui_modules", lambda: None)
        monkeypatch.setattr(theme, "apply", lambda app: None)
        window.apply_theme("CYBER")
        assert not window.topbar.search_button.isHidden()
        window.open_search()
        assert window._palette.isVisible()
        window.close()
    finally:
        theme.set_theme(original)
