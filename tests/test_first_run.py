from __future__ import annotations

import json

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog

from app.i18n import I18nService, tr
from app.settings import DEFAULTS, SettingsService
from app.ui.first_run import FirstRunWizard
from app.ui.main_window import MainWindow
from app.ui.settings import SettingsPage


@pytest.fixture
def wizard_service(tmp_path):
    return SettingsService(
        tmp_path / "settings.json",
        data={"language": "EN", "theme": "TITANIUM", "ui_scale": 100},
    )


def test_default_marks_existing_installs_complete() -> None:
    assert DEFAULTS["first_run_completed"] is True


def test_legacy_settings_without_key_are_not_prompted(tmp_path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"language": "EN", "theme": "GRAPHITE"}), encoding="utf-8")
    service = SettingsService(path)
    assert service.get("first_run_completed") is True


def test_wizard_applies_selected_values(qapp, wizard_service) -> None:
    wizard = FirstRunWizard(wizard_service)
    applied: list[dict] = []
    wizard.settings_applied.connect(applied.append)

    wizard.language_combo.setCurrentIndex(wizard.language_combo.findData("EN"))
    wizard.theme_combo.setCurrentIndex(wizard.theme_combo.findData("ARCTIC"))
    wizard.scale_combo.setCurrentIndex(wizard.scale_combo.findData(125))
    wizard.update_check.setChecked(False)
    wizard.tray_check.setChecked(False)
    wizard.next()
    wizard.next()
    wizard.finish()

    assert wizard.result() == QDialog.DialogCode.Accepted
    assert wizard.changes["language"] == "EN"
    assert wizard_service.get("language") == "EN"
    assert wizard_service.get("theme") == "ARCTIC"
    assert wizard_service.get("ui_scale") == 125
    assert wizard_service.get("update_check_enabled") is False
    assert wizard_service.get("minimize_to_tray") is False
    assert wizard_service.get("first_run_completed") is True
    applied_again = SettingsService(wizard_service.path)
    assert applied_again.get("first_run_completed") is True
    assert applied and applied[0]["ui_scale"] == 125


def test_wizard_skip_only_marks_complete(qapp, wizard_service) -> None:
    wizard = FirstRunWizard(wizard_service)
    wizard.language_combo.setCurrentIndex(wizard.language_combo.findData("EN"))
    wizard.next()
    wizard.skip()

    assert wizard.result() == QDialog.DialogCode.Rejected
    assert wizard_service.get("language") == "EN"
    assert wizard_service.get("first_run_completed") is True


def test_wizard_rejects_missing_choice(qapp, wizard_service, monkeypatch) -> None:
    wizard = FirstRunWizard(wizard_service)
    warnings: list[str] = []
    monkeypatch.setattr(wizard, "_warn", warnings.append)
    wizard.language_combo.setCurrentIndex(-1)
    wizard.next()
    wizard.finish()

    assert warnings == [tr("wiz_invalid_choice")]
    assert not wizard.changes
    assert not wizard_service.path.exists()


def test_wizard_navigation_and_retranslate(qapp, wizard_service) -> None:
    wizard = FirstRunWizard(wizard_service)
    assert wizard._step == 0
    assert not wizard.back_button.isVisibleTo(wizard)
    assert wizard.next_button.isVisibleTo(wizard)
    wizard.next()
    assert wizard.back_button.isVisibleTo(wizard)
    wizard.next()
    assert wizard.finish_button.isVisibleTo(wizard)
    wizard.back()
    assert wizard._step == 1

    I18nService.instance().set_language("UA", emit=False)
    try:
        wizard.retranslate()
        assert wizard.title_label.text() == tr("wiz_title")
        assert "Українська" in [wizard.language_combo.itemText(i) for i in range(2)]
    finally:
        I18nService.instance().set_language("EN", emit=False)
    wizard.close()


def test_settings_page_reopens_wizard(qapp, wizard_service) -> None:
    requested: list[str] = []
    page = SettingsPage(wizard_service, on_wizard_requested=lambda: requested.append("yes"))
    assert page.wizard_button.text() == tr("set_run_wizard")
    page.wizard_button.click()

    assert requested == ["yes"]
    assert wizard_service.get("first_run_completed") is False
    assert SettingsService(wizard_service.path).get("first_run_completed") is False


def test_main_window_applies_wizard_preferences(
    qapp, wizard_service, monkeypatch
) -> None:
    class FakeWizard(QObject):
        open_settings_requested = Signal()

        def __init__(self, service, parent=None) -> None:
            super().__init__(parent)
            self.changes = {
                "language": "UA",
                "theme": "GRAPHITE",
                "ui_scale": 125,
                "first_run_completed": True,
            }

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("app.ui.first_run.FirstRunWizard", FakeWizard)
    applied: list[tuple[str, object]] = []
    monkeypatch.setattr(
        "app.ui.theme.set_ui_scale", lambda value: applied.append(("scale", value))
    )
    window = MainWindow(settings=wizard_service)
    monkeypatch.setattr(window, "apply_theme", lambda name: applied.append(("theme", name)))

    window.open_first_run()

    assert ("scale", 125) in applied
    assert ("theme", "GRAPHITE") in applied
    assert I18nService.instance().current_language == "UA"
    window.close()
