from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.logs import clear_logs, log_file, read_tail, setup_logging
from app.settings import SettingsError, SettingsService

INTERVAL_OPTIONS = (250, 500, 1000, 2000, 5000)
LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


class SettingsPage(QWidget):
    def __init__(
        self,
        service: SettingsService | None = None,
        log_directory: Path | str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or SettingsService()
        self._log_directory = Path(log_directory) if log_directory is not None else None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "Application preferences. Changes are stored in "
            f"{self._service.path} and applied on save."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addWidget(self._build_general_card())
        layout.addWidget(self._build_logging_card())

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.save_button = QPushButton("SAVE CHANGES")
        self.save_button.clicked.connect(self.save)
        actions.addWidget(self.save_button)
        self.reset_button = QPushButton("RESET TO DEFAULTS")
        self.reset_button.setProperty("secondary", True)
        self.reset_button.clicked.connect(self.reset)
        actions.addWidget(self.reset_button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self.load_values()
        self.refresh_preview()

    @property
    def service(self) -> SettingsService:
        return self._service

    # ---------- cards ----------

    def _build_general_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        grid = QGridLayout(card)
        grid.setContentsMargins(18, 16, 18, 16)
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        heading = QLabel("GENERAL")
        heading.setObjectName("cardTitle")
        grid.addWidget(heading, 0, 0, 1, 2)

        grid.addWidget(QLabel("Sample interval"), 1, 0)
        self.interval_combo = QComboBox()
        for value in INTERVAL_OPTIONS:
            self.interval_combo.addItem(f"{value} ms", value)
        grid.addWidget(self.interval_combo, 1, 1)

        self.minimize_check = QCheckBox("Minimize to tray when closing the window")
        grid.addWidget(self.minimize_check, 2, 0, 1, 2)

        self.start_minimized_check = QCheckBox("Start minimized to tray")
        grid.addWidget(self.start_minimized_check, 3, 0, 1, 2)

        self.tray_metrics_check = QCheckBox("Show CPU/RAM in tray tooltip")
        grid.addWidget(self.tray_metrics_check, 4, 0, 1, 2)

        grid.setColumnStretch(1, 1)
        return card

    def _build_logging_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("card")
        outer = QVBoxLayout(card)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(10)

        head = QHBoxLayout()
        heading = QLabel("LOGGING")
        heading.setObjectName("cardTitle")
        head.addWidget(heading)
        head.addStretch(1)

        self.level_combo = QComboBox()
        for level in LOG_LEVELS:
            self.level_combo.addItem(level, level)
        head.addWidget(QLabel("Level"))
        head.addWidget(self.level_combo)

        self.open_logs_button = QPushButton("OPEN LOG FOLDER")
        self.open_logs_button.setProperty("secondary", True)
        self.open_logs_button.clicked.connect(self.open_log_folder)
        head.addWidget(self.open_logs_button)

        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.refresh_preview)
        head.addWidget(self.refresh_button)

        self.clear_button = QPushButton("CLEAR")
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
        self.preview.setMaximumHeight(180)
        self.preview.setPlaceholderText("Log preview appears here…")
        outer.addWidget(self.preview)
        return card

    # ---------- values ----------

    def load_values(self) -> None:
        interval = self._service.get("sample_interval_ms")
        index = self.interval_combo.findData(interval)
        self.interval_combo.setCurrentIndex(max(index, 0))
        self.minimize_check.setChecked(self._service.get("minimize_to_tray"))
        self.start_minimized_check.setChecked(self._service.get("start_minimized"))
        self.tray_metrics_check.setChecked(self._service.get("tray_metrics"))
        level = self._service.get("log_level")
        level_index = self.level_combo.findData(level)
        self.level_combo.setCurrentIndex(level_index if level_index >= 0 else 1)

    def collect_values(self) -> dict[str, object]:
        return {
            "sample_interval_ms": int(self.interval_combo.currentData()),
            "minimize_to_tray": self.minimize_check.isChecked(),
            "start_minimized": self.start_minimized_check.isChecked(),
            "tray_metrics": self.tray_metrics_check.isChecked(),
            "log_level": str(self.level_combo.currentData()),
        }

    def save(self) -> None:
        try:
            for key, value in self.collect_values().items():
                self._service.set(key, value)
            path = self._service.save()
        except SettingsError as exc:
            self.status_label.setText(f"Save failed: {exc}")
            self.status_label.setObjectName("errorLine")
            self.status_label.style().unpolish(self.status_label)
            self.status_label.style().polish(self.status_label)
            return
        setup_logging(self._service.get("log_level"), directory=self._log_directory)
        self.status_label.setObjectName("cardSub")
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
        self.status_label.setText(f"Saved → {path}")
        self.refresh_preview()

    def reset(self) -> None:
        self._service.reset()
        try:
            self._service.save()
        except OSError as exc:
            self.status_label.setText(f"Reset failed: {exc}")
            return
        self.load_values()
        self.status_label.setText("Defaults restored")

    # ---------- log preview ----------

    def refresh_preview(self) -> None:
        lines = read_tail(log_file(self._log_directory), limit=200)
        self.preview.setPlainText("\n".join(lines) if lines else "No log entries yet.")

    def clear_log(self) -> None:
        ok = clear_logs(self._log_directory)
        self.refresh_preview()
        self.status_label.setText("Log cleared" if ok else "Log file missing or locked")

    def open_log_folder(self) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtWidgets import QDesktopServices

        folder = log_file(self._log_directory).parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
