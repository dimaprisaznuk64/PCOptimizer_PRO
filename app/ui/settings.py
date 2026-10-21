from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
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

from app.i18n import I18nService, tr
from app.logs import clear_logs, log_file, read_tail, setup_logging
from app.settings import SettingsError, SettingsService, data_root

from .combos import COMBO_HEIGHT, COMBO_WIDTH_WIDE, CompactCombo, tune_combo
from .components import CardTitleLabel
from .theme import CURRENT_THEME, T_SMALL, THEME_LABELS
from .theme_picker import ThemeSwatchDelegate

INTERVAL_OPTIONS = (250, 500, 1000, 2000, 5000)
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
LANGUAGE_OPTIONS = ("UA", "EN")
TEMP_MIN, TEMP_MAX = 50, 110

class SettingsPage(QWidget):
    def __init__(
        self,
        service: SettingsService | None = None,
        log_directory: Path | str | None = None,
        parent: QWidget | None = None,
        on_theme_applied=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or SettingsService()
        self._log_directory = Path(log_directory) if log_directory is not None else None
        self._on_theme_applied = on_theme_applied

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
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(14)

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

        layout.addWidget(self._build_general_card())
        layout.addWidget(self._build_logging_card(), 1)

        actions_bar = QFrame()
        actions_bar.setObjectName("card")
        actions_outer = QHBoxLayout(actions_bar)
        actions_outer.setContentsMargins(16, 12, 16, 12)
        actions_outer.setSpacing(8)
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
        actions_outer.addStretch(1)
        layout.addWidget(actions_bar)

        self.status_label = QLabel(tr("set_idle"))
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self.load_values()
        self.refresh_preview()

    @property
    def service(self) -> SettingsService:
        return self._service

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("set_title"))
        self._desc.setText(tr("set_desc") + "\n" + str(self._service.path))
        self._general_heading.setText(tr("set_general"))
        self._interval_label.setText(tr("set_sample_interval"))
        self._theme_label.setText(tr("set_theme"))
        for i in range(self.theme_combo.count()):
            self.theme_combo.setItemText(i, tr(f"theme_{self.theme_combo.itemData(i)}"))
        self._language_label.setText(tr("set_language"))
        self._data_label.setText(tr("set_data_dir"))
        self._data_label.setToolTip(tr("set_data_dir_tip"))
        self._level_label.setText(tr("set_log_level"))
        self._logging_heading.setText(tr("set_logging"))
        self.minimize_check.setText(tr("set_minimize_tray"))
        self.start_minimized_check.setText(tr("set_start_minimized"))
        self.tray_metrics_check.setText(tr("set_tray_metrics"))
        self.temp_alerts_check.setText(tr("set_temp_alerts"))
        self._temp_cpu_label.setText(tr("set_temp_cpu"))
        self._temp_gpu_label.setText(tr("set_temp_gpu"))
        self.save_button.setText(tr("set_save_btn"))
        self.reset_button.setText(tr("set_reset_btn"))
        self.admin_button.setText(tr("set_restart_admin"))
        self.admin_button.setToolTip(tr("set_restart_admin_tip"))
        self.open_logs_button.setText(tr("set_open_folder"))
        self.refresh_button.setText(tr("set_refresh_log"))
        self.clear_button.setText(tr("set_clear_log"))
        self.preview.setPlaceholderText(tr("set_log_empty"))

    # ---------- cards ----------

    def _build_general_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(20, 18, 20, 18)
        grid.setHorizontalSpacing(20)
        grid.setVerticalSpacing(12)

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
        self.theme_combo.setItemDelegate(ThemeSwatchDelegate(self.theme_combo))
        grid.addWidget(self.theme_combo, 2, 1)

        self._language_label = QLabel(tr("set_language"))
        grid.addWidget(self._language_label, 3, 0)
        self.language_combo = CompactCombo()
        for code in LANGUAGE_OPTIONS:
            self.language_combo.addItem({"UA": "Українська", "EN": "English"}.get(code, code), code)
        tune_combo(self.language_combo)
        grid.addWidget(self.language_combo, 3, 1)

        self._data_label = QLabel(tr("set_data_dir"))
        self._data_label.setToolTip(tr("set_data_dir_tip"))
        grid.addWidget(self._data_label, 4, 0)
        self.data_dir_edit = QLineEdit(str(data_root()))
        self.data_dir_edit.setReadOnly(True)
        self.data_dir_edit.setFixedHeight(COMBO_HEIGHT)
        self.data_dir_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.data_dir_edit, 4, 1)

        self.minimize_check = QCheckBox(tr("set_minimize_tray"))
        grid.addWidget(self.minimize_check, 5, 0, 1, 2)

        self.start_minimized_check = QCheckBox(tr("set_start_minimized"))
        grid.addWidget(self.start_minimized_check, 6, 0, 1, 2)

        self.tray_metrics_check = QCheckBox(tr("set_tray_metrics"))
        grid.addWidget(self.tray_metrics_check, 7, 0, 1, 2)

        self.temp_alerts_check = QCheckBox(tr("set_temp_alerts"))
        grid.addWidget(self.temp_alerts_check, 8, 0, 1, 2)

        self._temp_cpu_label = QLabel(tr("set_temp_cpu"))
        grid.addWidget(self._temp_cpu_label, 9, 0)
        self.temp_cpu_spin = QSpinBox()
        self.temp_cpu_spin.setRange(TEMP_MIN, TEMP_MAX)
        self.temp_cpu_spin.setSuffix(" °C")
        self.temp_cpu_spin.setFixedHeight(COMBO_HEIGHT)
        self.temp_cpu_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.temp_cpu_spin, 9, 1)

        self._temp_gpu_label = QLabel(tr("set_temp_gpu"))
        grid.addWidget(self._temp_gpu_label, 10, 0)
        self.temp_gpu_spin = QSpinBox()
        self.temp_gpu_spin.setRange(TEMP_MIN, TEMP_MAX)
        self.temp_gpu_spin.setSuffix(" °C")
        self.temp_gpu_spin.setFixedHeight(COMBO_HEIGHT)
        self.temp_gpu_spin.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid.addWidget(self.temp_gpu_spin, 10, 1)

        for check in (
            self.minimize_check,
            self.start_minimized_check,
            self.tray_metrics_check,
            self.temp_alerts_check,
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
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

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
        self.preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        mono = QFont()
        mono.setFamilies(["Cascadia Mono", "Consolas", "Courier New"])
        mono.setPixelSize(T_SMALL)
        self.preview.setFont(mono)
        self.preview.setPlaceholderText(tr("set_log_empty"))
        outer.addWidget(self.preview, 1)
        return card

    # ---------- values ----------

    def load_values(self) -> None:
        interval = self._service.get("sample_interval_ms")
        index = self.interval_combo.findData(interval)
        self.interval_combo.setCurrentIndex(max(index, 0))
        theme_index = self.theme_combo.findData(self._service.get("theme"))
        self.theme_combo.setCurrentIndex(max(theme_index, 0))
        self._loaded_theme = str(self._service.get("theme"))
        language_index = self.language_combo.findData(self._service.get("language"))
        self.language_combo.setCurrentIndex(max(language_index, 0))
        self.minimize_check.setChecked(self._service.get("minimize_to_tray"))
        self.start_minimized_check.setChecked(self._service.get("start_minimized"))
        self.tray_metrics_check.setChecked(self._service.get("tray_metrics"))
        self.temp_alerts_check.setChecked(self._service.get("temp_alerts_enabled"))
        self.temp_cpu_spin.setValue(int(self._service.get("temp_alert_cpu")))
        self.temp_gpu_spin.setValue(int(self._service.get("temp_alert_gpu")))
        level = self._service.get("log_level")
        level_index = self.level_combo.findData(level)
        self.level_combo.setCurrentIndex(level_index if level_index >= 0 else 1)

    def collect_values(self) -> dict[str, object]:
        return {
            "sample_interval_ms": int(self.interval_combo.currentData()),
            "language": str(self.language_combo.currentData()),
            "minimize_to_tray": self.minimize_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "tray_metrics": self.tray_metrics_check.isChecked(),
            "temp_alerts_enabled": self.temp_alerts_check.isChecked(),
            "temp_alert_cpu": int(self.temp_cpu_spin.value()),
            "temp_alert_gpu": int(self.temp_gpu_spin.value()),
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
        theme_changed = self._service.get("theme") != getattr(self, "_loaded_theme", CURRENT_THEME)
        language = str(self._service.get("language"))
        language_changed = language != I18nService.instance().current_language
        self.status_label.setObjectName("cardSub")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setText(tr("set_saved", path=path))
        self.refresh_preview()
        if language_changed:
            I18nService.instance().set_language(language)
        if theme_changed and self._on_theme_applied is not None:
            self._on_theme_applied(str(self.theme_combo.currentData()))

    def reset(self) -> None:
        self._service.reset()
        try:
            self._service.save()
        except OSError as exc:
            self.status_label.setText(tr("set_reset_failed", msg=exc))
            return
        self.load_values()
        self.status_label.setText(tr("set_reset_done"))

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

    def restart_as_admin(self) -> None:
        """Restart the app elevated (UAC prompt), so some operations need no extra prompts."""
        import ctypes
        import sys


        if getattr(sys, "frozen", False):
            exe = sys.executable
            args = ""
        else:
            exe = sys.executable
            args = " ".join(f'"{a}"' for a in sys.argv)
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", exe, args, None, 1)
        except OSError:
            self.status_label.setText(tr("set_save_failed", msg="ShellExecuteW failed"))
            return
        QApplication.quit()
