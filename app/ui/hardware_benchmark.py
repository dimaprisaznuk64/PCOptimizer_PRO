from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.benchmarks.hardware import HardwareBenchmarkReport, HardwareBenchmarkService
from app.i18n import tr
from app.reports import ReportError, format_for_path, timestamp_name, write_report

from .components import CardTitleLabel, ValueListCard, attach_empty_hint
from .tasks import Task
from .theme import CARD_PADDING, DANGER, OK, PAGE_MARGINS

COLUMN_KEYS = (
    "hwb_col_metric",
    "hwb_col_value",
    "hwb_col_unit",
    "hwb_col_ms",
    "hwb_col_runs",
    "hwb_col_detail",
)
BASELINE_COLUMN_KEYS = (
    "hwb_col_metric",
    "hwb_col_value",
    "hwb_col_unit",
    "hwb_col_previous",
    "hwb_col_delta",
)
_MISSING = "—"


def _metric_text(metric: str) -> str:
    key = f"bench_metric_{metric}"
    text = tr(key)
    return metric if text == key else text


def _delta_text(delta: float | None) -> str:
    return _MISSING if delta is None else f"{delta:+.1f}%"


def _delta_color(delta: float | None) -> str | None:
    if delta is None or abs(delta) < 2.0:
        return None
    return OK if delta > 0 else DANGER


class HardwareBenchmarkPage(QWidget):
    def __init__(
        self,
        service: HardwareBenchmarkService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or HardwareBenchmarkService()
        self._task: Task | None = None
        self._report: HardwareBenchmarkReport | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(10)

        title = QLabel(tr("hwb_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("hwb_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.run_button = QPushButton(tr("hwb_run"))
        self.run_button.setProperty("primary", True)
        self.run_button.clicked.connect(self.start_run)
        toolbar.addWidget(self.run_button)
        self.baseline_button = QPushButton(tr("hwb_set_baseline"))
        self.baseline_button.setProperty("secondary", True)
        self.baseline_button.clicked.connect(self.set_baseline)
        toolbar.addWidget(self.baseline_button)
        self.export_button = QPushButton(tr("hwb_export"))
        self.export_button.setProperty("secondary", True)
        self.export_button.clicked.connect(self.export_report)
        toolbar.addWidget(self.export_button)
        self.status_label = QLabel(tr("hwb_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)
        self.summary_card = ValueListCard(tr("hwb_summary"))
        splitter.addWidget(self.summary_card)

        results_card, self.results_title, self.results_table = self._make_table(
            "hwb_results", COLUMN_KEYS, "hwb_empty"
        )
        baseline_card, self.baseline_title, self.baseline_table = self._make_table(
            "hwb_baseline", BASELINE_COLUMN_KEYS, "hwb_baseline_empty"
        )
        splitter.addWidget(results_card)
        splitter.addWidget(baseline_card)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 2)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> HardwareBenchmarkService:
        return self._service

    @property
    def report(self) -> HardwareBenchmarkReport | None:
        return self._report

    def _make_table(self, title_key: str, column_keys: tuple[str, ...], hint: str):
        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        body.setSpacing(8)
        title = CardTitleLabel(tr(title_key))
        body.addWidget(title)
        table = QTableWidget(0, len(column_keys))
        attach_empty_hint(table, hint)
        table.setHorizontalHeaderLabels([tr(key) for key in column_keys])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        for col in range(len(column_keys) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(column_keys) - 1, QHeaderView.ResizeMode.Stretch)
        body.addWidget(table, 1)
        return card, title, table

    def start_run(self) -> None:
        if self._task is not None:
            return
        self._set_busy(True)
        self.status_label.setText(tr("hwb_running"))
        self._task = Task(self._service.run, parent=self, com=True)
        self._task.done.connect(self._on_done)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _release_task(self) -> None:
        task = self._task
        self._task = None
        if task is not None:
            task.deleteLater()

    def _on_done(self, result: object) -> None:
        self._release_task()
        self._set_busy(False)
        if not isinstance(result, HardwareBenchmarkReport):
            self.status_label.setText(tr("hwb_failed", msg=result))
            return
        self._report = result
        self._render()
        if result.errors:
            self.status_label.setText(tr("hwb_partial", count=len(result.errors)))
        else:
            self.status_label.setText(tr("hwb_done", count=len(result.results)))

    def _on_failed(self, message: str) -> None:
        self._release_task()
        self._set_busy(False)
        self._report = None
        self._clear()
        self.status_label.setText(tr("hwb_failed", msg=message))

    def _render(self) -> None:
        report = self._report
        if report is None:
            return
        self.summary_card.set_values([(tr(key), value) for key, value in self._service.summary_rows(report)])
        self.results_table.setRowCount(len(report.results))
        for row, result in enumerate(report.results):
            cells = (
                _metric_text(result.metric),
                f"{result.value:.2f}" if result.unit == "GB/s" else f"{result.value:.1f}",
                result.unit,
                str(result.duration_ms),
                str(result.runs),
                result.detail,
            )
            for col, text in enumerate(cells):
                self.results_table.setItem(row, col, QTableWidgetItem(text))
        self._render_baseline(report)

    def _render_baseline(self, report: HardwareBenchmarkReport) -> None:
        rows = self._service.baseline_rows(report)
        self.baseline_table.setRowCount(len(rows))
        for row, item in enumerate(rows):
            text = f"{item.value:.2f}" if item.unit == "GB/s" else f"{item.value:.1f}"
            previous = _MISSING if item.previous is None else (
                f"{item.previous:.2f}" if item.unit == "GB/s" else f"{item.previous:.1f}"
            )
            cells = (
                QTableWidgetItem(_metric_text(item.metric)),
                QTableWidgetItem(text),
                QTableWidgetItem(item.unit),
                QTableWidgetItem(previous),
                QTableWidgetItem(_delta_text(item.delta_pct)),
            )
            color = _delta_color(item.delta_pct)
            if color is not None:
                cells[4].setForeground(QColor(color))
            for col, cell in enumerate(cells):
                self.baseline_table.setItem(row, col, cell)

    def _clear(self) -> None:
        self.summary_card.set_values([])
        self.results_table.setRowCount(0)
        self.baseline_table.setRowCount(0)

    def set_baseline(self) -> None:
        if self._task is not None:
            return
        marked = self._service.history.set_baseline()
        if self._report is not None:
            self._render_baseline(self._report)
        self.status_label.setText(tr("hwb_baseline_set", count=marked))

    def export_report(self) -> None:
        if self._task is not None:
            return
        report = self._report
        if report is None:
            self.status_label.setText(tr("exp_nothing"))
            return
        path = self._ask_save_path(timestamp_name("hardware_benchmark", "csv"))
        if not path:
            return
        fmt = format_for_path(path)
        try:
            text = self._service.export_text(report, fmt)
            target = write_report(path, text, fmt)
        except ReportError as e:
            self.status_label.setText(tr("exp_failed", msg=str(e)))
            return
        self.status_label.setText(tr("exp_done", path=str(target)))

    def _ask_save_path(self, default_name: str) -> str:
        path, selected = QFileDialog.getSaveFileName(
            self, tr("exp_dialog_title"), default_name, tr("exp_filter")
        )
        if not path:
            return ""
        if not Path(path).suffix:
            choice = (selected or "").lower()
            fmt = "json" if "json" in choice else "csv"
            path = f"{path}.{fmt}"
        return path

    def _set_busy(self, busy: bool) -> None:
        for button in (self.run_button, self.baseline_button, self.export_button):
            button.setEnabled(not busy)

    def retranslate(self) -> None:
        self._title.setText(tr("hwb_title"))
        self._desc.setText(tr("hwb_desc"))
        self.run_button.setText(tr("hwb_run"))
        self.baseline_button.setText(tr("hwb_set_baseline"))
        self.export_button.setText(tr("hwb_export"))
        self.summary_card.set_title(tr("hwb_summary"))
        self.results_title.setText(tr("hwb_results").upper())
        self.baseline_title.setText(tr("hwb_baseline").upper())
        self.results_table.setHorizontalHeaderLabels([tr(key) for key in COLUMN_KEYS])
        self.baseline_table.setHorizontalHeaderLabels([tr(key) for key in BASELINE_COLUMN_KEYS])
        if self._task is None and self._report is None:
            self.status_label.setText(tr("hwb_idle"))
        if self._report is not None:
            self._render()
