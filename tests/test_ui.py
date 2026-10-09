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


def test_sidebar_highlight_follows_programmatic_navigation(qapp) -> None:
    window = MainWindow()
    window.show_page("gpu")
    assert window.sidebar._buttons["gpu"].isChecked()
    assert not window.sidebar._buttons["dashboard"].isChecked()
    window.show_page("settings")
    assert window.sidebar._buttons["settings"].isChecked()
    assert not window.sidebar._buttons["gpu"].isChecked()
    window.close()


def test_sidebar_buttons_are_exclusive_on_click(qapp) -> None:
    window = MainWindow()
    window.sidebar._buttons["cleaner"].click()
    assert window.sidebar._buttons["cleaner"].isChecked()
    assert not window.sidebar._buttons["dashboard"].isChecked()
    window.sidebar._buttons["optimizer"].click()
    assert window.sidebar._buttons["optimizer"].isChecked()
    assert not window.sidebar._buttons["cleaner"].isChecked()
    window.close()
