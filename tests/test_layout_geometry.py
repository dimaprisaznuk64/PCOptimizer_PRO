from __future__ import annotations

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication

from app.settings import SettingsService
from app.ui import pages
from app.ui.main_window import MainWindow


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_dashboard_fits_at_1024(qapp) -> None:
    mw = MainWindow(SettingsService())
    mw.resize(1024, 640)
    mw.show()
    mw.show_page("dashboard")
    qapp.processEvents()
    # page should not have horizontal scroll visible
    from PySide6.QtWidgets import QScrollArea

    for sa in mw.findChildren(QScrollArea):
        if sa.objectName() == "navScroll":
            continue
        if sa.horizontalScrollBar().isVisible():
            raise AssertionError("horizontal scroll visible")


def test_settings_fits_at_1024(qapp) -> None:
    mw = MainWindow(SettingsService())
    mw.resize(1024, 640)
    mw.show()
    mw.show_page("settings")
    qapp.processEvents()
    from PySide6.QtWidgets import QScrollArea

    for sa in mw.findChildren(QScrollArea):
        if sa.objectName() == "navScroll":
            continue
        if sa.horizontalScrollBar().isVisible():
            raise AssertionError("horizontal scroll visible")


def test_all_pages_build_and_switch(qapp) -> None:
    mw = MainWindow(SettingsService())
    mw.resize(1024, 640)
    mw.show()
    for key, _ in pages.build_pages(SettingsService()):
        mw.show_page(key)
        qapp.processEvents()
