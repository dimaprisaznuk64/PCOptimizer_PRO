from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.reports.system import SystemReportConfig, build_system_report

from .tasks import Task
from .theme import CARD_PADDING, PAGE_MARGINS

SECTION_KEYS = (
    "system",
    "hardware",
    "health",
    "optimizer",
    "restore",
    "benchmarks",
    "history",
    "diagnostics",
)

Provider = object


def _default_providers() -> dict[str, Provider]:
    from app import __version__
    from app.settings import data_root

    def system() -> dict[str, object]:
        return {
            "application": "PCOptimizer PRO",
            "version": __version__,
            "platform": "Windows",
            "data_root": str(data_root()),
        }

    def hardware() -> object:
        from app.hardware import HardwareService

        return HardwareService().report()

    def health() -> object:
        from app.health import HealthService

        return HealthService().scan()

    def optimizer() -> object:
        from app.optimizer import OptimizerService

        return OptimizerService().state()

    def restore() -> object:
        from app.restore import RestorePointService

        return RestorePointService().list_points()

    def benchmarks() -> object:
        from app.benchmarks import BenchmarkHistory

        return BenchmarkHistory().entries(limit=50)

    def history() -> object:
        from app.history import PerformanceHistory

        return PerformanceHistory().query(60 * 24 * 7)

    def diagnostics() -> object:
        from app.diagnostics import DiagnosticsService

        return DiagnosticsService().report()

    return {
        "system": system,
        "hardware": hardware,
        "health": health,
        "optimizer": optimizer,
        "restore": restore,
        "benchmarks": benchmarks,
        "history": history,
        "diagnostics": diagnostics,
    }


class SystemReportPage(QWidget):
    def __init__(
        self,
        providers: Mapping[str, Provider] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._providers: Mapping[str, Provider] = providers if providers is not None else _default_providers()
        self._task: Task | None = None
        self._text = ""
        self._format = "html"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(10)

        title = QLabel(tr("sys_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("sys_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.ids_check = QCheckBox(tr("sys_include_ids"))
        toolbar.addWidget(self.ids_check)
        toolbar.addWidget(QLabel(tr("sys_format")))
        self.format_combo = QComboBox()
        self.format_combo.addItem(tr("sys_format_html"), "html")
        self.format_combo.addItem(tr("sys_format_text"), "text")
        self.format_combo.currentIndexChanged.connect(self._on_format_changed)
        toolbar.addWidget(self.format_combo)
        self.generate_button = QPushButton(tr("sys_generate"))
        self.generate_button.setProperty("primary", True)
        self.generate_button.clicked.connect(self.start_generate)
        toolbar.addWidget(self.generate_button)
        self.save_button = QPushButton(tr("sys_save"))
        self.save_button.clicked.connect(self.save_report)
        toolbar.addWidget(self.save_button)
        self.status_label = QLabel(tr("sys_empty"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        body.setSpacing(8)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(tr("sys_empty"))
        body.addWidget(self.preview, 1)
        layout.addWidget(card, 1)

    def _on_format_changed(self) -> None:
        self._format = str(self.format_combo.currentData() or "html")
        if self._text:
            self._show_report(self._text)

    def _config(self) -> SystemReportConfig:
        return SystemReportConfig(
            include_identifiers=self.ids_check.isChecked(),
            output=self._format,
        )

    def start_generate(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("sys_generating"))
        self.generate_button.setEnabled(False)
        self.save_button.setEnabled(False)
        self._task = Task(self._build, parent=self)
        self._task.done.connect(self._apply_report)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _build(self) -> str:
        return build_system_report(
            **self._providers,
            config=self._config(),
            generated=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _apply_report(self, text: object) -> None:
        self._task = None
        self.generate_button.setEnabled(True)
        if not isinstance(text, str):
            self.status_label.setText(tr("sys_failed", msg=text))
            return
        self._text = text
        self._show_report(text)
        self.status_label.setText(tr("sys_ready"))
        self.save_button.setEnabled(True)

    def _on_failed(self, message: str) -> None:
        self._task = None
        self.generate_button.setEnabled(True)
        self.status_label.setText(tr("sys_failed", msg=message))

    def _show_report(self, text: str) -> None:
        if self._format == "html":
            self.preview.setHtml(text)
        else:
            self.preview.setPlainText(text)

    def save_report(self) -> None:
        if not self._text:
            self.status_label.setText(tr("sys_status"))
            return
        suffix = ".txt" if self._format == "text" else ".html"
        path, _ = QFileDialog.getSaveFileName(
            self,
            tr("sys_save_title"),
            f"pcoptimizer_report{suffix}",
            "HTML (*.html);;Text (*.txt)" if suffix == ".html" else "Text (*.txt);;HTML (*.html)",
        )
        if not path:
            return
        target = Path(path)
        if not target.suffix:
            target = target.with_suffix(suffix)
        try:
            target.write_text(self._text, encoding="utf-8")
        except OSError as e:
            self.status_label.setText(tr("sys_failed", msg=e))
            return
        self.status_label.setText(tr("sys_saved", path=str(target)))

    def retranslate(self) -> None:
        self._title.setText(tr("sys_title"))
        self._desc.setText(tr("sys_desc"))
        self.ids_check.setText(tr("sys_include_ids"))
        self.format_combo.setItemText(0, tr("sys_format_html"))
        self.format_combo.setItemText(1, tr("sys_format_text"))
        self.generate_button.setText(tr("sys_generate"))
        self.save_button.setText(tr("sys_save"))
        if not self._text:
            self.preview.setPlainText(tr("sys_empty"))
            self.status_label.setText(tr("sys_empty"))
