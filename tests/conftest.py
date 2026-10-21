from __future__ import annotations

import os

import pytest

from app.i18n.service import I18nService


@pytest.fixture(scope="session")
def qapp():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    try:
        from PySide6.QtWidgets import QApplication
    except Exception as e:  # pragma: no cover
        pytest.skip(f"PySide6 not available: {e}")
    app = QApplication.instance() or QApplication([])
    yield app
    for widget in list(app.topLevelWidgets()):
        widget.close()
        widget.deleteLater()
    app.processEvents()


@pytest.fixture(autouse=True)
def i18n_english():
    """Pin interface language to EN so page tests assert stable English strings."""
    I18nService.instance().set_language("EN", emit=False)
    yield
    I18nService.instance().set_language("EN", emit=False)


@pytest.fixture(autouse=True)
def isolated_data_root(tmp_path, monkeypatch):
    """Keep runtime data (health result etc.) out of the project tree and reset the log singleton."""
    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path / "data"))
    from app.ui.activity import ActivityLog

    ActivityLog._instance = None
    yield
    ActivityLog._instance = None


@pytest.fixture(autouse=True)
def reset_theme():
    """Restore the shipped palette after each test.

    Pages read theme tokens from module globals, so any test that builds a
    MainWindow (which loads the developer's saved theme) or applies another
    theme would otherwise leak that palette's colours into later tests.
    """
    from app.ui import theme

    if theme.CURRENT_THEME != theme.DEFAULT_THEME:
        theme.set_theme(theme.DEFAULT_THEME)
    yield
    if theme.CURRENT_THEME != theme.DEFAULT_THEME:
        theme.set_theme(theme.DEFAULT_THEME)