from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from app.i18n.service import I18nService


@pytest.fixture(scope="session")
def qapp():
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