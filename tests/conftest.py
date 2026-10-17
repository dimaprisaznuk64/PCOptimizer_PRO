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