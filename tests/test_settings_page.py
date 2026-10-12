from __future__ import annotations

from app.logs import setup_logging
from app.settings import DEFAULTS, SettingsService
from app.ui.settings import SettingsPage


def _page(qapp, tmp_path, **kwargs) -> SettingsPage:
    service = SettingsService(tmp_path / "settings.json")
    return SettingsPage(service, log_directory=tmp_path / "logs", **kwargs)


def test_page_renders(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    assert page.interval_combo.count() == 5
    assert page.level_combo.count() == 4
    assert page.save_button.isEnabled()
    assert page.status_label.text() == "Idle"


def test_widgets_show_saved_values(qapp, tmp_path) -> None:
    service = SettingsService(tmp_path / "settings.json")
    service.set("sample_interval_ms", 5000)
    service.set("minimize_to_tray", False)
    service.set("log_level", "DEBUG")
    service.save()

    page = SettingsPage(service, log_directory=tmp_path / "logs")
    assert page.interval_combo.currentData() == 5000
    assert page.minimize_check.isChecked() is False
    assert page.level_combo.currentData() == "DEBUG"


def test_save_persists_values(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    page.interval_combo.setCurrentIndex(page.interval_combo.findData(2000))
    page.minimize_check.setChecked(False)
    page.start_minimized_check.setChecked(True)
    page.tray_metrics_check.setChecked(False)
    page.level_combo.setCurrentIndex(page.level_combo.findData("ERROR"))
    page.save()

    assert "Saved" in page.status_label.text()
    reloaded = SettingsService(tmp_path / "settings.json")
    assert reloaded.get("sample_interval_ms") == 2000
    assert reloaded.get("minimize_to_tray") is False
    assert reloaded.get("start_minimized") is True
    assert reloaded.get("tray_metrics") is False
    assert reloaded.get("log_level") == "ERROR"


def test_save_sets_up_logging(qapp, tmp_path) -> None:
    import logging as _logging

    from app.logs import log_file

    page = _page(qapp, tmp_path)
    page.level_combo.setCurrentIndex(page.level_combo.findData("ERROR"))
    page.save()
    assert _logging.getLogger("pcoptimizer").level == _logging.ERROR
    assert log_file(tmp_path / "logs").exists()


def test_reset_restores_defaults(qapp, tmp_path) -> None:
    from app.i18n import I18nService, tr

    page = _page(qapp, tmp_path)
    page.interval_combo.setCurrentIndex(page.interval_combo.findData(5000))
    page.minimize_check.setChecked(False)
    page.save()
    assert SettingsService(tmp_path / "settings.json").get("sample_interval_ms") == 5000

    I18nService.instance().set_language("EN", emit=False)
    page.reset()
    assert page.interval_combo.currentData() == DEFAULTS["sample_interval_ms"]
    assert page.minimize_check.isChecked() is True
    assert page.status_label.text() == tr("set_reset_done") == "Defaults restored"
    assert SettingsService(tmp_path / "settings.json").get("sample_interval_ms") == DEFAULTS[
        "sample_interval_ms"
    ]


def test_preview_shows_log_lines(qapp, tmp_path) -> None:
    setup_logging("INFO", directory=tmp_path / "logs", console=False)
    from app.logs import get_logger

    get_logger("page").info("preview marker")
    page = _page(qapp, tmp_path)
    assert "preview marker" in page.preview.toPlainText()


def test_clear_log(qapp, tmp_path) -> None:
    setup_logging("INFO", directory=tmp_path / "logs", console=False)
    from app.logs import get_logger

    get_logger("page").info("to be cleared")
    page = _page(qapp, tmp_path)
    page.clear_log()
    assert page.preview.toPlainText() == "No log entries yet."
    assert page.status_label.text() == "Log cleared"


def test_collect_values_shape(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    values = page.collect_values()
    assert set(values) == {
        "sample_interval_ms",
        "minimize_to_tray",
        "start_minimized",
        "tray_metrics",
        "log_level",
        "theme",
        "language",
    }
    assert isinstance(values["sample_interval_ms"], int)
    assert isinstance(values["minimize_to_tray"], bool)
