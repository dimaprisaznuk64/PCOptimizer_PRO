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


def test_save_applies_quiet_games_toggle_live(qapp, tmp_path) -> None:
    applied: list[bool] = []
    page = _page(qapp, tmp_path, on_quiet_games_applied=applied.append)
    assert page.quiet_games_check.isChecked() is True
    page.quiet_games_check.setChecked(False)
    page.save()
    page.quiet_games_check.setChecked(True)
    page.save()
    page.save()  # unchanged value must not re-apply
    assert applied == [False, True]


def test_reset_applies_quiet_games_toggle_live(qapp, tmp_path) -> None:
    applied: list[bool] = []
    page = _page(qapp, tmp_path, on_quiet_games_applied=applied.append)
    page.quiet_games_check.setChecked(False)
    page.save()
    page.reset()
    assert applied == [False, True]


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
    expected_status = tr("set_reset_done")
    page.reset()
    assert page.interval_combo.currentData() == DEFAULTS["sample_interval_ms"]
    assert page.minimize_check.isChecked() is True
    assert I18nService.instance().current_language == DEFAULTS["language"]
    assert page.status_label.text() == expected_status == "Defaults restored"
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
        "monitor_profile",
        "sample_interval_ms",
        "minimize_to_tray",
        "start_minimized",
        "tray_metrics",
        "update_check_enabled",
        "temp_alerts_enabled",
        "alerts_quiet_during_games",
        "usage_alerts_enabled",
        "log_level",
        "theme",
        "language",
        "ui_scale",
        "dashboard_hidden",
    }
    assert isinstance(values["sample_interval_ms"], int)
    assert isinstance(values["minimize_to_tray"], bool)
    assert isinstance(values["temp_alerts_enabled"], bool)
    assert isinstance(values["alerts_quiet_during_games"], bool)
    assert isinstance(values["usage_alerts_enabled"], bool)


def test_dashboard_hidden_is_persisted_and_applied_live(qapp, tmp_path) -> None:
    applied: list[str] = []
    page = _page(qapp, tmp_path, on_dashboard_hidden_applied=applied.append)
    page._dashboard_hidden = "chart,cpu"
    page.save()
    assert applied == ["cpu,chart"]
    assert SettingsService(tmp_path / "settings.json").get("dashboard_hidden") == "cpu,chart"

    applied.clear()
    page.reset()
    assert applied == [""]
    assert page._dashboard_hidden == ""


def test_customize_dashboard_stages_choice(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QDialog

    from app.ui import settings as settings_module

    class _Dialog:
        def __init__(self, hidden, parent=None) -> None:
            self.hidden = hidden

        def exec(self):
            return QDialog.DialogCode.Accepted

        def values(self):
            return {"cpu"}

    monkeypatch.setattr(settings_module, "DashboardCustomizerDialog", _Dialog)
    page = _page(qapp, tmp_path)
    page.customize_dashboard()
    page.save()
    assert SettingsService(tmp_path / "settings.json").get("dashboard_hidden") == "cpu"


def test_alert_threshold_controls_are_removed(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    for name in (
        "temp_cpu_spin",
        "temp_gpu_spin",
        "cpu_alert_spin",
        "ram_alert_spin",
        "disk_alert_spin",
        "cooldown_spin",
    ):
        assert not hasattr(page, name)


def test_reset_applies_default_theme(qapp, tmp_path) -> None:
    applied: list[str] = []
    page = _page(qapp, tmp_path, on_theme_applied=applied.append)
    theme_keys = [page.theme_combo.itemData(i) for i in range(page.theme_combo.count())]
    other_theme = next(key for key in theme_keys if key and key != DEFAULTS["theme"])
    page.theme_combo.setCurrentIndex(page.theme_combo.findData(other_theme))
    page.save()
    assert applied == [other_theme]

    applied.clear()
    page.reset()
    assert applied == [DEFAULTS["theme"]]
    assert page.theme_combo.currentData() == DEFAULTS["theme"]


def test_ui_scale_is_persisted_and_applied_live(qapp, tmp_path) -> None:
    applied: list[int] = []
    page = _page(qapp, tmp_path, on_scale_applied=applied.append)
    assert page.scale_spin.minimum() == 100
    assert page.scale_spin.maximum() == 150
    page.scale_spin.setValue(125)
    page.save()
    assert applied == [125]
    assert SettingsService(tmp_path / "settings.json").get("ui_scale") == 125


def test_reset_restores_default_ui_scale(qapp, tmp_path) -> None:
    applied: list[int] = []
    page = _page(qapp, tmp_path, on_scale_applied=applied.append)
    page.scale_spin.setValue(140)
    page.save()
    assert applied == [140]
    applied.clear()
    page.reset()
    assert applied == [DEFAULTS["ui_scale"]]
    assert page.scale_spin.value() == DEFAULTS["ui_scale"]


def test_restart_admin_cancel_keeps_app_running(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    from app.i18n import tr

    page = _page(qapp, tmp_path)
    quits: list[bool] = []
    monkeypatch.setattr(page, "_shell_execute_admin", lambda exe, args: 1223)
    monkeypatch.setattr(QApplication, "quit", lambda: quits.append(True))
    page.restart_as_admin()
    assert page.status_label.text() == tr("set_admin_cancelled")
    assert quits == []


def test_restart_admin_failure_keeps_app_running(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    from app.i18n import tr

    page = _page(qapp, tmp_path)
    quits: list[bool] = []
    monkeypatch.setattr(page, "_shell_execute_admin", lambda exe, args: 5)
    monkeypatch.setattr(QApplication, "quit", lambda: quits.append(True))
    page.restart_as_admin()
    assert page.status_label.text() == tr("set_admin_failed", code=5)
    assert quits == []


def test_restart_admin_success_quits(qapp, tmp_path, monkeypatch) -> None:
    from PySide6.QtWidgets import QApplication

    page = _page(qapp, tmp_path)
    quits: list[bool] = []
    monkeypatch.setattr(page, "_shell_execute_admin", lambda exe, args: 42)
    monkeypatch.setattr(QApplication, "quit", lambda: quits.append(True))
    page.restart_as_admin()
    assert quits == [True]


def test_update_widgets_follow_settings(qapp, tmp_path) -> None:
    from app import __version__

    service = SettingsService(tmp_path / "settings.json")
    service.set("update_check_enabled", False)
    page = SettingsPage(service, log_directory=tmp_path / "logs")
    assert page.update_check.isChecked() is False
    assert page.version_value.text() == f"v{__version__}"
    assert page.release_button.isHidden()


def test_check_reports_available_update(qapp, tmp_path) -> None:
    from app.update import UpdateInfo

    page = _page(qapp, tmp_path)
    page._on_update_checked(
        UpdateInfo(
            current="1.6.5",
            latest="1.7.0",
            available=True,
            url="https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v1.7.0",
        )
    )
    assert page.update_status.text() == "Update available: v1.7.0"
    assert page.release_button.isHidden() is False


def test_unverified_installer_disables_download(qapp, tmp_path) -> None:
    from app.update import UpdateInfo

    page = _page(qapp, tmp_path)
    page._on_update_checked(
        UpdateInfo(
            current="1.6.5",
            latest="1.7.0",
            available=True,
            url="https://github.com/dimaprisaznuk64/PCOptimizer_PRO/releases/tag/v1.7.0",
            asset_name="PCOptimizer_PRO_Setup_1.7.0.exe",
            download_unavailable="no_checksum",
        )
    )
    assert "no SHA-256" in page.update_status.text()
    assert page.release_button.isHidden() is False
    assert page.download_button.isHidden() is True


def test_update_status_follows_live_language_switch(qapp, tmp_path) -> None:
    from app.i18n import I18nService
    from app.update import UpdateInfo

    page = _page(qapp, tmp_path)
    page._on_update_checked(UpdateInfo(current="1.6.5", latest="1.6.5"))
    assert page.update_status.text() == "You have the latest version (v1.6.5)"
    I18nService.instance().set_language("UA", emit=False)
    page.retranslate()
    assert page.update_status.text() == "У вас остання версія (v1.6.5)"


def test_check_reports_latest_version(qapp, tmp_path) -> None:
    from app.update import UpdateInfo

    page = _page(qapp, tmp_path)
    page._on_update_checked(UpdateInfo(current="1.6.5", latest="1.6.5"))
    assert page.update_status.text() == "You have the latest version (v1.6.5)"
    assert page.release_button.isHidden()


def test_download_button_saves_installer_in_background(qapp, tmp_path, monkeypatch) -> None:
    import time

    from app.update import UpdateInfo

    page = _page(qapp, tmp_path)
    target = tmp_path / "updates" / "setup.exe"
    monkeypatch.setattr("app.ui.settings.download_installer", lambda info: str(target))
    page._on_update_checked(
        UpdateInfo(
            current="1.6.5",
            latest="1.7.0",
            available=True,
            download_url="https://github.com/release/setup.exe",
        )
    )
    assert page.download_button.isHidden() is False
    page.download_update()
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline and str(target) not in page.update_status.text():
        qapp.processEvents()
        time.sleep(0.01)
    assert str(target) in page.update_status.text()
    assert page.download_button.isEnabled() is True


def test_check_failure_is_shown(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    page._on_update_failed("no internet")
    assert page.update_status.text() == "Update check failed: no internet"
    assert page.check_updates_button.isEnabled()


def test_search_filters_general_rows_and_clears(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    assert page.interval_combo.isHidden() is False

    page.search_edit.setText("theme")
    assert page.theme_combo.isHidden() is False
    assert page.interval_combo.isHidden() is True
    assert page.logging_card.isHidden() is True
    assert page.general_card.isHidden() is False

    page.search_edit.clear()
    assert page.interval_combo.isHidden() is False
    assert page.logging_card.isHidden() is False
    assert page.actions_bar.isHidden() is False
    assert page.no_match_label.isHidden() is True


def test_search_matches_logging_and_reports_no_match(qapp, tmp_path) -> None:
    page = _page(qapp, tmp_path)
    page.search_edit.setText("журнал")
    assert page.logging_card.isHidden() is False
    assert page.general_card.isHidden() is True

    page.search_edit.setText("zzzz-no-such-setting")
    assert page.logging_card.isHidden() is True
    assert page.general_card.isHidden() is True
    assert page.no_match_label.isHidden() is False


def test_search_follows_live_language_switch(qapp, tmp_path) -> None:
    from app.i18n import I18nService

    page = _page(qapp, tmp_path)
    I18nService.instance().set_language("UA", emit=False)
    page.retranslate()
    page.search_edit.setText("тема")
    assert page.theme_combo.isHidden() is False
    assert page.interval_combo.isHidden() is True
