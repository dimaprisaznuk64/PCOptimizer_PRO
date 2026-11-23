from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.i18n import I18nService, tr
from app.logs import clear_logs, log_file, read_tail, setup_logging
from app.monitor.profiles import DEFAULT_PROFILE, PROFILE_KEYS, profile_for
from app.settings import SettingsError, SettingsService, data_root
from app.update import RELEASES_PAGE, UpdateService, download_installer

from .combos import COMBO_HEIGHT, COMBO_WIDTH_WIDE, CompactCombo, tune_combo
from .components import CardTitleLabel
from .dashboard_custom import (
    DashboardCustomizerDialog,
    serialize_dashboard_hidden,
)
from .tasks import Task
from .theme import (
    CARD_PADDING,
    CURRENT_THEME,
    PAGE_MARGINS,
    PAGE_SPACING,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XL,
    T_SMALL,
    THEME_LABELS,
)
from .theme_picker import ThemeSwatchDelegate

INTERVAL_OPTIONS = (250, 500, 1000, 2000, 5000)
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
LANGUAGE_OPTIONS = ("UA", "EN")


class SettingsPage(QWidget):
    wizard_requested = Signal()

    def __init__(
        self,
        service: SettingsService | None = None,
        log_directory: Path | str | None = None,
        parent: QWidget | None = None,
        on_theme_applied=None,
        on_scale_applied=None,
        update_service: UpdateService | None = None,
        on_wizard_requested=None,
        on_dashboard_hidden_applied=None,
        on_monitor_profile_applied=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or SettingsService()
        self._log_directory = Path(log_directory) if log_directory is not None else None
        self._on_theme_applied = on_theme_applied
        self._on_scale_applied = on_scale_applied
        self._update_service = update_service
        self._on_wizard_requested = on_wizard_requested
        self._on_dashboard_hidden_applied = on_dashboard_hidden_applied
        self._on_monitor_profile_applied = on_monitor_profile_applied
        self._check_task: Task | None = None
        self._download_task: Task | None = None
        self._dynamic_visibility: dict[int, bool] = {}
        self._release_url = RELEASES_PAGE
        self.last_update = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        # The page scrolls: on short windows the form must not be squeezed
        # (labels clipped, combos collapsed into thin lines).
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        content = QWidget()
        content.setObjectName("page")
        outer.addWidget(scroll)
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)

        title = QLabel(tr("set_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            tr("set_desc") + "\n" + str(self._service.path)
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("settingsSearch")
        self.search_edit.setPlaceholderText(tr("set_search_placeholder"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._apply_search)
        layout.addWidget(self.search_edit)

        self.general_card = self._build_general_card()
        self.logging_card = self._build_logging_card()
        layout.addWidget(self.general_card)
        layout.addWidget(self.logging_card, 1)

        self.no_match_label = QLabel(tr("set_search_no_match"))
        self.no_match_label.setObjectName("cardSub")
        self.no_match_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.no_match_label.setWordWrap(True)
        self.no_match_label.setVisible(False)
        layout.addWidget(self.no_match_label)

        actions_bar = QFrame()
        actions_bar.setObjectName("card")
        actions_outer = QHBoxLayout(actions_bar)
        actions_outer.setContentsMargins(CARD_PADDING, PAGE_SPACING, CARD_PADDING, PAGE_SPACING)
        actions_outer.setSpacing(SPACING_SM)
        self.save_button = QPushButton(tr("set_save_btn"))
        self.save_button.setProperty("primary", True)
        self.save_button.clicked.connect(self.save)
        actions_outer.addWidget(self.save_button)
        self.reset_button = QPushButton(tr("set_reset_btn"))
        self.reset_button.setProperty("secondary", True)
        self.reset_button.clicked.connect(self.reset)
        actions_outer.addWidget(self.reset_button)
        self.admin_button = QPushButton(tr("set_restart_admin"))
        self.admin_button.setProperty("secondary", True)
        self.admin_button.setToolTip(tr("set_restart_admin_tip"))
        self.admin_button.clicked.connect(self.restart_as_admin)
        actions_outer.addWidget(self.admin_button)
        self.wizard_button = QPushButton(tr("set_run_wizard"))
        self.wizard_button.setProperty("secondary", True)
        self.wizard_button.setToolTip(tr("set_run_wizard_tip"))
        self.wizard_button.clicked.connect(self.request_wizard)
        actions_outer.addWidget(self.wizard_button)
        self.dashboard_button = QPushButton(tr("dash_custom_btn"))
        self.dashboard_button.setProperty("secondary", True)
        self.dashboard_button.setToolTip(tr("dash_custom_desc"))
        self.dashboard_button.clicked.connect(self.customize_dashboard)
        actions_outer.addWidget(self.dashboard_button)
        if on_wizard_requested is not None:
            self.wizard_requested.connect(on_wizard_requested)
        actions_outer.addStretch(1)
        self.actions_bar = actions_bar
        layout.addWidget(actions_bar)

        self.status_label = QLabel(tr("set_idle"))
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self.load_values()
        self.refresh_preview()
        self._rebuild_search_index()
        self._apply_search(self.search_edit.text())

    @property
    def service(self) -> SettingsService:
        return self._service

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("set_title"))
        self._desc.setText(tr("set_desc") + "\n" + str(self._service.path))
        self._general_heading.setText(tr("set_general"))
        self._interval_label.setText(tr("set_sample_interval"))
        self._profile_label.setText(tr("set_monitor_profile"))
        self._profile_label.setToolTip(tr("set_monitor_profile_tip"))
        self.profile_combo.setToolTip(tr("set_monitor_profile_tip"))
        for i in range(self.profile_combo.count()):
            self.profile_combo.setItemText(i, tr(f"monitor_profile_{self.profile_combo.itemData(i).lower()}"))
        self._theme_label.setText(tr("set_theme"))
        for i in range(self.theme_combo.count()):
            self.theme_combo.setItemText(i, tr(f"theme_{self.theme_combo.itemData(i)}"))
        self._language_label.setText(tr("set_language"))
        self._scale_label.setText(tr("set_ui_scale"))
        self._scale_label.setToolTip(tr("set_ui_scale_tip"))
        self._data_label.setText(tr("set_data_dir"))
        self._data_label.setToolTip(tr("set_data_dir_tip"))
        self._level_label.setText(tr("set_log_level"))
        self._logging_heading.setText(tr("set_logging"))
        self.minimize_check.setText(tr("set_minimize_tray"))
        self.start_minimized_check.setText(tr("set_start_minimized"))
        self.tray_metrics_check.setText(tr("set_tray_metrics"))
        self.temp_alerts_check.setText(tr("set_temp_alerts"))
        self.quiet_games_check.setText(tr("set_quiet_games"))
        self.usage_alerts_check.setText(tr("set_usage_alerts"))
        self.save_button.setText(tr("set_save_btn"))
        self.reset_button.setText(tr("set_reset_btn"))
        self.admin_button.setText(tr("set_restart_admin"))
        self.admin_button.setToolTip(tr("set_restart_admin_tip"))
        self.wizard_button.setText(tr("set_run_wizard"))
        self.wizard_button.setToolTip(tr("set_run_wizard_tip"))
        self.dashboard_button.setText(tr("dash_custom_btn"))
        self.dashboard_button.setToolTip(tr("dash_custom_desc"))
        self._version_label.setText(tr("set_version"))
        self.update_check.setText(tr("set_update_check"))
        self.check_updates_button.setText(tr("set_check_updates"))
        self.release_button.setText(tr("set_open_release"))
        self.download_button.setText(tr("set_download_update"))
        self.open_logs_button.setText(tr("set_open_folder"))
        self.refresh_button.setText(tr("set_refresh_log"))
        self.clear_button.setText(tr("set_clear_log"))
        self.preview.setPlaceholderText(tr("set_log_empty"))
        self.search_edit.setPlaceholderText(tr("set_search_placeholder"))
        self.no_match_label.setText(tr("set_search_no_match"))
        self._rebuild_search_index()
        self._apply_search(self.search_edit.text())

    # ---------- search ----------

    _SEARCH_ALIASES = {
        1: "sample interval polling ms інтервал опитування частота",
        2: "theme palette оформлення тема палітра",
        3: "language locale україн english ua en мова",
        4: "ui scale zoom dpi масштаб інтерфейсу",
        5: "data folder path папка даних шлях",
        6: "minimize tray згортати трей",
        7: "start minimized запуск згорнутий",
        8: "tray metrics cpu ram підказка трей",
        9: "temperature alerts перегрів температура сповіщення",
        10: "quiet games alerts тиша ігри сповіщення",
        11: "usage alerts cpu ram disk навантаження сповіщення",
        12: "version update release версія оновлення",
        13: "update check auto автоматична перевірка оновлень",
        14: "update status статус оновлення",
        15: "monitor profile eco balanced performance профіль моніторингу продуктивність економія",
    }
    _SEARCH_LOGGING = "logging logs level folder clear refresh журнал події рівень папка очистити оновити"
    _SEARCH_ACTIONS = (
        "save reset administrator wizard dashboard зберегти скинути адміністратор майстер панель"
    )

    @staticmethod
    def _collect_item_text(item, tokens: list[str]) -> None:
        widget = item.widget()
        if widget is not None:
            for method in ("text", "toolTip", "placeholderText"):
                getter = getattr(widget, method, None)
                if callable(getter):
                    value = getter()
                    if value:
                        tokens.append(str(value))
            return
        child_layout = item.layout()
        if child_layout is not None:
            for index in range(child_layout.count()):
                SettingsPage._collect_item_text(child_layout.itemAt(index), tokens)

    def _rebuild_search_index(self) -> None:
        grid = getattr(self, "_general_grid", None)
        if grid is None:
            return
        index: dict[int, str] = {}
        for row, aliases in self._SEARCH_ALIASES.items():
            tokens = [aliases]
            for column in range(grid.columnCount()):
                item = grid.itemAtPosition(row, column)
                if item is not None:
                    self._collect_item_text(item, tokens)
            index[row] = " ".join(tokens).casefold()
        self._search_index = index
        self._search_logging_text = " ".join(
            (self._SEARCH_LOGGING, self.logging_card.windowTitle(), self._logging_heading.text())
        ).casefold()

    def _set_item_visible(self, item, visible: bool) -> None:
        widget = item.widget()
        if widget is not None:
            if widget.property("searchKeepVisibility"):
                key = id(widget)
                if visible:
                    was_hidden = self._dynamic_visibility.pop(key, None)
                    if was_hidden is not None:
                        widget.setVisible(not was_hidden)
                else:
                    self._dynamic_visibility[key] = widget.isHidden()
                    widget.setVisible(False)
                return
            widget.setVisible(visible)
            return
        child_layout = item.layout()
        if child_layout is not None:
            for index in range(child_layout.count()):
                self._set_item_visible(child_layout.itemAt(index), visible)

    def _set_grid_row_visible(self, row: int, visible: bool) -> None:
        grid = self._general_grid
        for column in range(grid.columnCount()):
            item = grid.itemAtPosition(row, column)
            if item is not None:
                self._set_item_visible(item, visible)

    def _apply_search(self, query: str) -> None:
        if not hasattr(self, "_search_index"):
            return
        query = query.strip().casefold()
        if not query:
            for row in self._search_index:
                self._set_grid_row_visible(row, True)
            self.general_card.setVisible(True)
            self.logging_card.setVisible(True)
            self.actions_bar.setVisible(True)
            self.no_match_label.setVisible(False)
            return

        any_match = False
        general_match = False
        for row, haystack in self._search_index.items():
            match = query in haystack
            self._set_grid_row_visible(row, match)
            any_match |= match
            general_match |= match
        self.general_card.setVisible(general_match)

        logging_match = query in self._search_logging_text
        self.logging_card.setVisible(logging_match)
        any_match |= logging_match

        actions_match = query in self._SEARCH_ACTIONS.casefold()
        self.actions_bar.setVisible(actions_match)
        any_match |= actions_match

        self.no_match_label.setVisible(not any_match)

    # ---------- cards ----------

    def _build_general_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        self._general_grid = grid
        grid.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        grid.setHorizontalSpacing(SPACING_XL)
        grid.setVerticalSpacing(SPACING_MD)

        heading = CardTitleLabel(tr("set_general"))
        grid.addWidget(heading, 0, 0, 1, 2)
        self._general_heading = heading

        self._interval_label = QLabel(tr("set_sample_interval"))
        grid.addWidget(self._interval_label, 1, 0)
        self.interval_combo = CompactCombo()
        for value in INTERVAL_OPTIONS:
            self.interval_combo.addItem(f"{value} ms", value)
        tune_combo(self.interval_combo)
        grid.addWidget(self.interval_combo, 1, 1)

        self._theme_label = QLabel(tr("set_theme"))
        grid.addWidget(self._theme_label, 2, 0)
        self.theme_combo = CompactCombo()
        for key in THEME_LABELS:
            self.theme_combo.addItem(tr(f"theme_{key}"), key)
        tune_combo(self.theme_combo, COMBO_WIDTH_WIDE, expand=True)
        self._theme_delegate = ThemeSwatchDelegate(self.theme_combo)
        self.theme_combo.setItemDelegate(self._theme_delegate)
        self.theme_combo.currentIndexChanged.connect(self._sync_theme_check)
        self._theme_delegate.set_current(str(self.theme_combo.currentData()))
        grid.addWidget(self.theme_combo, 2, 1)

        self._language_label = QLabel(tr("set_language"))
        grid.addWidget(self._language_label, 3, 0)
        self.language_combo = CompactCombo()
        for code in LANGUAGE_OPTIONS:
            self.language_combo.addItem({"UA": "Українська", "EN": "English"}.get(code, code), code)
        tune_combo(self.language_combo)
        grid.addWidget(self.language_combo, 3, 1)

        self._scale_label = QLabel(tr("set_ui_scale"))
        self._scale_label.setToolTip(tr("set_ui_scale_tip"))
        grid.addWidget(self._scale_label, 4, 0)
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(100, 150)
        self.scale_spin.setSingleStep(5)
        self.scale_spin.setSuffix("%")
        self.scale_spin.setFixedHeight(COMBO_HEIGHT)
        self.scale_spin.setFixedWidth(120)
        grid.addWidget(self.scale_spin, 4, 1)

        self._data_label = QLabel(tr("set_data_dir"))
        self._data_label.setToolTip(tr("set_data_dir_tip"))
        grid.addWidget(self._data_label, 5, 0)
        self.data_dir_edit = QLineEdit(str(data_root()))
        self.data_dir_edit.setReadOnly(True)
        self.data_dir_edit.setFixedHeight(COMBO_HEIGHT)
        self.data_dir_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        grid.addWidget(self.data_dir_edit, 5, 1)

        self.minimize_check = QCheckBox(tr("set_minimize_tray"))
        grid.addWidget(self.minimize_check, 6, 0, 1, 2)

        self.start_minimized_check = QCheckBox(tr("set_start_minimized"))
        grid.addWidget(self.start_minimized_check, 7, 0, 1, 2)

        self.tray_metrics_check = QCheckBox(tr("set_tray_metrics"))
        grid.addWidget(self.tray_metrics_check, 8, 0, 1, 2)

        self.temp_alerts_check = QCheckBox(tr("set_temp_alerts"))
        grid.addWidget(self.temp_alerts_check, 9, 0, 1, 2)

        self.quiet_games_check = QCheckBox(tr("set_quiet_games"))
        grid.addWidget(self.quiet_games_check, 10, 0, 1, 2)

        self.usage_alerts_check = QCheckBox(tr("set_usage_alerts"))
        grid.addWidget(self.usage_alerts_check, 11, 0, 1, 2)

        self._version_label = QLabel(tr("set_version"))
        grid.addWidget(self._version_label, 12, 0)
        version_row = QHBoxLayout()
        version_row.setSpacing(SPACING_SM)
        self.version_value = QLabel(f"v{__version__}")
        self.version_value.setObjectName("cardSub")
        version_row.addWidget(self.version_value)
        self.release_button = QPushButton(tr("set_open_release"))
        self.release_button.setProperty("secondary", True)
        self.release_button.setProperty("searchKeepVisibility", True)
        self.release_button.clicked.connect(self._open_release_page)
        self.release_button.setVisible(False)
        version_row.addWidget(self.release_button)
        self.download_button = QPushButton(tr("set_download_update"))
        self.download_button.setProperty("secondary", True)
        self.download_button.setProperty("searchKeepVisibility", True)
        self.download_button.clicked.connect(self.download_update)
        self.download_button.setVisible(False)
        version_row.addWidget(self.download_button)
        version_row.addStretch(1)
        self.check_updates_button = QPushButton(tr("set_check_updates"))
        self.check_updates_button.setProperty("secondary", True)
        self.check_updates_button.clicked.connect(self.check_for_updates)
        version_row.addWidget(self.check_updates_button)
        grid.addLayout(version_row, 12, 1)

        self.update_check = QCheckBox(tr("set_update_check"))
        grid.addWidget(self.update_check, 13, 0, 1, 2)

        self.update_status = QLabel("")
        self.update_status.setObjectName("cardSub")
        self.update_status.setProperty("searchKeepVisibility", True)
        self.update_status.setWordWrap(True)
        self.update_status.setVisible(False)
        grid.addWidget(self.update_status, 14, 0, 1, 2)

        self._profile_label = QLabel(tr("set_monitor_profile"))
        self._profile_label.setToolTip(tr("set_monitor_profile_tip"))
        grid.addWidget(self._profile_label, 15, 0)
        self.profile_combo = CompactCombo()
        for key in PROFILE_KEYS:
            self.profile_combo.addItem(tr(f"monitor_profile_{key.lower()}"), key)
        tune_combo(self.profile_combo)
        self.profile_combo.setToolTip(tr("set_monitor_profile_tip"))
        self.profile_combo.currentIndexChanged.connect(self._sync_interval_to_profile)
        grid.addWidget(self.profile_combo, 15, 1)

        for check in (
            self.minimize_check,
            self.start_minimized_check,
            self.tray_metrics_check,
            self.temp_alerts_check,
            self.quiet_games_check,
            self.usage_alerts_check,
            self.update_check,
        ):
            check.setMinimumHeight(26)

        # Column 1 takes the available width, column 2 is kept empty for spacing.
        grid.setColumnStretch(0, 0)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 0)
        return card

    def _build_logging_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        outer.setSpacing(SPACING_MD)

        head = QHBoxLayout()
        heading = CardTitleLabel(tr("set_logging"))
        head.addWidget(heading)
        head.addStretch(1)
        self._logging_heading = heading

        self.level_combo = CompactCombo()
        for level in LOG_LEVELS:
            self.level_combo.addItem(level, level)
        tune_combo(self.level_combo, 150)
        self._level_label = QLabel(tr("set_log_level"))
        head.addWidget(self._level_label)
        head.addWidget(self.level_combo)

        self.open_logs_button = QPushButton(tr("set_open_folder"))
        self.open_logs_button.setProperty("secondary", True)
        self.open_logs_button.clicked.connect(self.open_log_folder)
        head.addWidget(self.open_logs_button)

        self.refresh_button = QPushButton(tr("set_refresh_log"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.refresh_preview)
        head.addWidget(self.refresh_button)

        self.clear_button = QPushButton(tr("set_clear_log"))
        self.clear_button.setProperty("danger", True)
        self.clear_button.clicked.connect(self.clear_log)
        head.addWidget(self.clear_button)
        outer.addLayout(head)

        path_row = QHBoxLayout()
        self.log_path_edit = QLineEdit(str(log_file(self._log_directory)))
        self.log_path_edit.setReadOnly(True)
        path_row.addWidget(self.log_path_edit)
        outer.addLayout(path_row)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setMinimumHeight(160)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFont()
        mono.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
        mono.setPixelSize(T_SMALL)
        self.preview.setFont(mono)
        self.preview.setPlaceholderText(tr("set_log_empty"))
        outer.addWidget(self.preview, 1)
        return card

    # ---------- values ----------

    def _sync_theme_check(self) -> None:
        self._theme_delegate.set_current(str(self.theme_combo.currentData()))

    def _sync_interval_to_profile(self) -> None:
        profile = profile_for(self.profile_combo.currentData())
        index = self.interval_combo.findData(profile.sample_interval_ms)
        if index >= 0:
            self.interval_combo.setCurrentIndex(index)

    def load_values(self) -> None:
        profile_index = self.profile_combo.findData(self._service.get("monitor_profile"))
        with QSignalBlocker(self.profile_combo):
            self.profile_combo.setCurrentIndex(max(profile_index, 0))
        self._loaded_profile = str(self.profile_combo.currentData())
        interval = self._service.get("sample_interval_ms")
        index = self.interval_combo.findData(interval)
        self.interval_combo.setCurrentIndex(max(index, 0))
        self._loaded_interval = int(self.interval_combo.currentData())
        theme_index = self.theme_combo.findData(self._service.get("theme"))
        self.theme_combo.setCurrentIndex(max(theme_index, 0))
        self._loaded_theme = str(self._service.get("theme"))
        self._sync_theme_check()
        self.scale_spin.setValue(int(self._service.get("ui_scale")))
        self._loaded_scale = self.scale_spin.value()
        language_index = self.language_combo.findData(self._service.get("language"))
        self.language_combo.setCurrentIndex(max(language_index, 0))
        self.minimize_check.setChecked(self._service.get("minimize_to_tray"))
        self.start_minimized_check.setChecked(self._service.get("start_minimized"))
        self.tray_metrics_check.setChecked(self._service.get("tray_metrics"))
        self.update_check.setChecked(bool(self._service.get("update_check_enabled")))
        self.temp_alerts_check.setChecked(self._service.get("temp_alerts_enabled"))
        self.quiet_games_check.setChecked(bool(self._service.get("alerts_quiet_during_games")))
        self.usage_alerts_check.setChecked(bool(self._service.get("usage_alerts_enabled")))
        self._dashboard_hidden = str(self._service.get("dashboard_hidden"))
        self._loaded_dashboard = self._dashboard_hidden
        level = self._service.get("log_level")
        level_index = self.level_combo.findData(level)
        self.level_combo.setCurrentIndex(level_index if level_index >= 0 else 1)

    def collect_values(self) -> dict[str, object]:
        return {
            "monitor_profile": str(self.profile_combo.currentData()),
            "sample_interval_ms": int(self.interval_combo.currentData()),
            "language": str(self.language_combo.currentData()),
            "ui_scale": self.scale_spin.value(),
            "minimize_to_tray": self.minimize_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "tray_metrics": self.tray_metrics_check.isChecked(),
            "update_check_enabled": self.update_check.isChecked(),
            "temp_alerts_enabled": self.temp_alerts_check.isChecked(),
            "alerts_quiet_during_games": self.quiet_games_check.isChecked(),
            "usage_alerts_enabled": self.usage_alerts_check.isChecked(),
            "dashboard_hidden": serialize_dashboard_hidden(self._dashboard_hidden),
            "log_level": str(self.level_combo.currentData()),
            "theme": str(self.theme_combo.currentData()),
        }

    def save(self) -> None:
        try:
            for key, value in self.collect_values().items():
                self._service.set(key, value)
            path = self._service.save()
        except SettingsError as exc:
            self.status_label.setText(tr("set_save_failed", msg=exc))
            self.status_label.setObjectName("errorLine")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
            return
        setup_logging(self._service.get("log_level"), directory=self._log_directory)
        previous_language = I18nService.instance().current_language
        previous_theme = getattr(self, "_loaded_theme", CURRENT_THEME)
        previous_scale = getattr(self, "_loaded_scale", 100)
        previous_dashboard = getattr(self, "_loaded_dashboard", "")
        previous_profile = getattr(self, "_loaded_profile", DEFAULT_PROFILE)
        previous_interval = getattr(self, "_loaded_interval", 1000)
        self.status_label.setObjectName("cardSub")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setText(tr("set_saved", path=path))
        self.refresh_preview()
        self._apply_live_changes(
            previous_language,
            previous_theme,
            previous_scale,
            previous_dashboard,
            previous_profile,
            previous_interval,
        )

    def _apply_live_changes(
        self,
        previous_language: str,
        previous_theme: str,
        previous_scale: int,
        previous_dashboard: str = "",
        previous_profile: str = DEFAULT_PROFILE,
        previous_interval: int = 1000,
    ) -> None:
        language = str(self._service.get("language"))
        theme = str(self._service.get("theme"))
        scale = int(self._service.get("ui_scale"))
        dashboard = serialize_dashboard_hidden(self._dashboard_hidden)
        profile = str(self._service.get("monitor_profile"))
        interval = int(self._service.get("sample_interval_ms"))
        self._loaded_theme = theme
        self._loaded_scale = scale
        self._loaded_dashboard = dashboard
        self._loaded_profile = profile
        self._loaded_interval = interval
        if language != previous_language:
            I18nService.instance().set_language(language)
        if scale != previous_scale and self._on_scale_applied is not None:
            self._on_scale_applied(scale)
        if theme != previous_theme and self._on_theme_applied is not None:
            self._on_theme_applied(theme)
        if dashboard != previous_dashboard and self._on_dashboard_hidden_applied is not None:
            self._on_dashboard_hidden_applied(dashboard)
        if (
            profile != previous_profile or interval != previous_interval
        ) and self._on_monitor_profile_applied is not None:
            self._on_monitor_profile_applied(profile, interval)

    def reset(self) -> None:
        previous_language = I18nService.instance().current_language
        previous_theme = getattr(self, "_loaded_theme", CURRENT_THEME)
        previous_scale = getattr(self, "_loaded_scale", 100)
        previous_dashboard = getattr(self, "_loaded_dashboard", "")
        previous_profile = getattr(self, "_loaded_profile", DEFAULT_PROFILE)
        previous_interval = getattr(self, "_loaded_interval", 1000)
        self._service.reset()
        try:
            self._service.save()
        except OSError as exc:
            self.status_label.setText(tr("set_reset_failed", msg=exc))
            return
        self.load_values()
        self.status_label.setText(tr("set_reset_done"))
        self._apply_live_changes(
            previous_language,
            previous_theme,
            previous_scale,
            previous_dashboard,
            previous_profile,
            previous_interval,
        )

    def customize_dashboard(self) -> None:
        dialog = DashboardCustomizerDialog(self._dashboard_hidden, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._dashboard_hidden = serialize_dashboard_hidden(dialog.values())

    def request_wizard(self) -> None:
        self._service.set("first_run_completed", False)
        try:
            self._service.save()
        except OSError as exc:
            self.status_label.setText(tr("set_save_failed", msg=exc))
            return
        self.wizard_requested.emit()

    # ---------- updates ----------

    def check_for_updates(self) -> None:
        """Ask GitHub for the newest release in a background thread."""
        if self._check_task is not None:
            return
        from .tasks import Task

        self.last_update = None
        self.release_button.setVisible(False)
        self.download_button.setVisible(False)
        self.update_status.setVisible(True)
        self.update_status.setText(tr("set_upd_checking"))
        self.check_updates_button.setEnabled(False)
        service = self._update_service or UpdateService()
        task = Task(service.check, parent=self)
        task.done.connect(self._on_update_checked)
        task.failed.connect(self._on_update_failed)
        self._check_task = task
        task.start()

    def _finish_update_check(self) -> None:
        self._check_task = None
        self.check_updates_button.setEnabled(True)

    def _on_update_checked(self, info) -> None:
        self._finish_update_check()
        self.last_update = info
        if getattr(info, "error", None):
            self.update_status.setText(tr("set_upd_failed", msg=info.error))
            self.download_button.setVisible(False)
            return
        if getattr(info, "available", False):
            self.update_status.setText(tr("set_upd_available", version=info.latest))
            self._release_url = str(info.url)
            self.release_button.setVisible(True)
            self.download_button.setVisible(bool(getattr(info, "download_url", "")))
            return
        self.download_button.setVisible(False)
        self.update_status.setText(tr("set_upd_current", version=info.latest or info.current))

    def _on_update_failed(self, message: str) -> None:
        self._finish_update_check()
        self.update_status.setText(tr("set_upd_failed", msg=message))

    def _open_release_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self._release_url))

    def download_update(self) -> None:
        """Download the published installer in the background (never runs it)."""
        info = getattr(self, "last_update", None)
        if info is None or not getattr(info, "available", False):
            self.update_status.setText(tr("set_upd_no_asset"))
            return
        if not getattr(info, "download_url", ""):
            self.update_status.setText(tr("set_upd_no_asset"))
            return
        if self._download_task is not None:
            return
        from .tasks import Task

        self.update_status.setVisible(True)
        self.update_status.setText(tr("set_upd_downloading"))
        self.download_button.setEnabled(False)
        task = Task(lambda: download_installer(info), parent=self)
        task.done.connect(self._on_download_done)
        task.failed.connect(self._on_download_failed)
        self._download_task = task
        task.start()

    def _finish_download(self) -> None:
        self._download_task = None
        self.download_button.setEnabled(True)

    def _on_download_done(self, path) -> None:
        self._finish_download()
        self.update_status.setText(tr("set_upd_downloaded", path=str(path)))

    def _on_download_failed(self, message: str) -> None:
        self._finish_download()
        self.update_status.setText(tr("set_upd_download_failed", msg=message))

    # ---------- log preview ----------

    def refresh_preview(self) -> None:
        lines = read_tail(log_file(self._log_directory), limit=200)
        self.preview.setPlainText("\n".join(lines) if lines else tr("set_log_empty"))

    def clear_log(self) -> None:
        ok = clear_logs(self._log_directory)
        self.refresh_preview()
        self.status_label.setText(tr("set_log_cleared") if ok else tr("set_log_locked"))

    def open_log_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        folder = log_file(self._log_directory).parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _shell_execute_admin(self, exe: str, args: str) -> int:
        import ctypes

        return int(ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1))

    def restart_as_admin(self) -> None:
        """Restart the app elevated (UAC prompt), so some operations need no extra prompts."""
        import sys

        exe = sys.executable
        args = "" if getattr(sys, "frozen", False) else " ".join(f'"{a}"' for a in sys.argv)
        try:
            result = self._shell_execute_admin(exe, args)
        except OSError as exc:
            self.status_label.setText(tr("set_admin_failed", code=exc))
            return
        if result == 1223:
            self.status_label.setText(tr("set_admin_cancelled"))
            return
        if result <= 32:
            self.status_label.setText(tr("set_admin_failed", code=result))
            return
        QApplication.quit()
