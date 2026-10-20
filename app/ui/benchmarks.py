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
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.benchmarks import BenchmarkHistory, BenchmarkService, BenchmarkType
from app.i18n import tr
from app.reports import ReportError, export_history, timestamp_name
from app.settings import data_root

from .components import CardTitleLabel, attach_empty_hint
from .tasks import Task
from .theme import CARD_PADDING, DANGER, OK

_COLUMNS = (
    "bench_col_metric",
    "bench_col_value",
    "bench_col_unit",
    "bench_col_ms",
    "bench_col_runs",
    "bench_col_detail",
)
_HISTORY_COLUMNS = (
    "bench_hist_col_time",
    "bench_hist_col_metric",
    "bench_hist_col_value",
    "bench_hist_col_unit",
    "bench_hist_col_delta",
)
_MISSING = "—"
_BASELINE_MARK = "★"


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


class BenchmarksPage(QWidget):
    def __init__(
        self,
        service: BenchmarkService | None = None,
        history: BenchmarkHistory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or BenchmarkService()
        self._history = history or BenchmarkHistory()
        self._task: Task | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("bench_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("bench_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.cpu_btn = QPushButton(tr("bench_cpu"))
        self.cpu_btn.setProperty("secondary", True)
        self.cpu_btn.clicked.connect(lambda: self.start_run(BenchmarkType.CPU))
        toolbar.addWidget(self.cpu_btn)
        self.ram_btn = QPushButton(tr("bench_ram"))
        self.ram_btn.setProperty("secondary", True)
        self.ram_btn.clicked.connect(lambda: self.start_run(BenchmarkType.RAM))
        toolbar.addWidget(self.ram_btn)
        self.disk_btn = QPushButton(tr("bench_disk"))
        self.disk_btn.setProperty("secondary", True)
        self.disk_btn.clicked.connect(lambda: self.start_run(BenchmarkType.DISK))
        toolbar.addWidget(self.disk_btn)
        self.all_btn = QPushButton(tr("bench_all"))
        self.all_btn.setProperty("secondary", True)
        self.all_btn.clicked.connect(lambda: self.start_run(BenchmarkType.ALL))
        toolbar.addWidget(self.all_btn)
        self._buttons = {
            BenchmarkType.CPU: self.cpu_btn,
            BenchmarkType.RAM: self.ram_btn,
            BenchmarkType.DISK: self.disk_btn,
            BenchmarkType.ALL: self.all_btn,
        }
        self._active_btn: QPushButton | None = None
        self.status_label = QLabel(tr("bench_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        results_card, self.results_title, self.table = self._make_card(
            "bench_results_title", _COLUMNS, "bench_empty"
        )
        splitter.addWidget(results_card)

        history_card = QFrame()
        history_card.setObjectName("card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        history_layout.setSpacing(8)

        history_head = QHBoxLayout()
        history_head.setSpacing(8)
        self.history_title = CardTitleLabel(tr("bench_history_title"))
        history_head.addWidget(self.history_title)
        history_head.addStretch(1)
        self.baseline_button = QPushButton(tr("bench_set_baseline"))
        self.baseline_button.setProperty("secondary", True)
        self.baseline_button.clicked.connect(self.set_baseline)
        history_head.addWidget(self.baseline_button)
        self.clear_button = QPushButton(tr("bench_clear_history"))
        self.clear_button.setProperty("secondary", True)
        self.clear_button.clicked.connect(self.clear_history)
        history_head.addWidget(self.clear_button)
        self.export_button = QPushButton(tr("bench_export_btn"))
        self.export_button.setProperty("secondary", True)
        self.export_button.clicked.connect(self.export_history)
        history_head.addWidget(self.export_button)
        history_layout.addLayout(history_head)

        self.history_table = self._build_table(_HISTORY_COLUMNS, "bench_history_empty")
        history_layout.addWidget(self.history_table, 1)
        splitter.addWidget(history_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self._refresh_history()

    @property
    def service(self) -> BenchmarkService:
        return self._service

    @property
    def history(self) -> BenchmarkHistory:
        return self._history

    # ---------- layout helpers ----------

    def _build_table(self, column_keys: tuple[str, ...], hint: str) -> QTableWidget:
        table = QTableWidget(0, len(column_keys))
        attach_empty_hint(table, hint)
        table.setHorizontalHeaderLabels([tr(key) for key in column_keys])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = table.horizontalHeader()
        for i in range(len(column_keys) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(column_keys) - 1, QHeaderView.ResizeMode.Stretch)
        return table

    def _make_card(self, title_key: str, column_keys: tuple[str, ...], hint: str):
        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        body.setSpacing(8)
        title = CardTitleLabel(tr(title_key))
        body.addWidget(title)
        table = self._build_table(column_keys, hint)
        body.addWidget(table, 1)
        return card, title, table

    # ---------- runs ----------

    def start_run(self, btype: BenchmarkType) -> None:
        if self._task is not None:
            return
        self._set_busy(True)
        self._set_active(self._buttons.get(btype))
        self.status_label.setText(tr("bench_running"))
        target = data_root() if btype in (BenchmarkType.DISK, BenchmarkType.ALL) else None
        self._task = Task(lambda d=target: self._service.run(btype, disk_dir=d), parent=self)
        self._task.done.connect(self._on_done)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _on_done(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        results = result if isinstance(result, list) else []
        self._render_results(results)
        self._history.record(results)
        self._refresh_history()
        self.status_label.setText(tr("bench_done", count=len(results)))

    def _on_failed(self, msg: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("bench_failed", msg=msg))
        self._render_results([])

    def _render_results(self, results) -> None:
        self.table.setRowCount(len(results))
        for row, result in enumerate(results):
            decimals = 2 if result.unit == "GB/s" else 1
            cells = (
                _metric_text(result.metric),
                f"{result.value:.{decimals}f}",
                result.unit,
                str(result.duration_ms),
                str(result.runs),
                result.detail,
            )
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(text))

    # ---------- history ----------

    def set_baseline(self) -> None:
        marked = self._history.set_baseline()
        self._refresh_history()
        self.status_label.setText(tr("bench_baseline_set", count=marked))

    def clear_history(self) -> None:
        if not self._ask_confirm():
            return
        self._history.clear()
        self._refresh_history()
        self.status_label.setText(tr("bench_history_cleared"))

    def export_history(self) -> None:
        entries = self._history.entries(limit=0)
        if not entries:
            self.status_label.setText(tr("exp_nothing"))
            return
        path = self._ask_save_path(timestamp_name("benchmark_history", "csv"))
        if not path:
            return

        def _delta_of(e):
            if e.baseline:
                return None
            return self._history.delta_pct(e.metric, e.value)

        try:
            target = export_history(
                entries,
                path,
                localize=_metric_text,
                delta_of=_delta_of,
                header=(
                    tr("exp_hist_time"), tr("exp_hist_metric"), tr("exp_hist_value"),
                    tr("exp_hist_unit"), tr("exp_hist_detail"), tr("exp_hist_baseline"),
                    tr("exp_hist_delta"),
                ),
            )
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
            fmt = "json" if "json" in (selected or "").lower() else "csv"
            path = f"{path}.{fmt}"
        return path

    def _refresh_history(self) -> None:
        entries = self._history.entries(limit=100)
        self.history_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            delta = None if entry.baseline else self._history.delta_pct(entry.metric, entry.value)
            metric = _metric_text(entry.metric)
            if entry.baseline:
                metric = f"{metric} {_BASELINE_MARK}"
            cells = (
                QTableWidgetItem(entry.when.replace("T", " ")),
                QTableWidgetItem(metric),
                QTableWidgetItem(_format_value(entry.value, entry.unit)),
                QTableWidgetItem(entry.unit),
                QTableWidgetItem(_delta_text(delta) if not entry.baseline else _MISSING),
            )
            color = _delta_color(delta)
            if color is not None:
                cells[4].setForeground(QColor(color))
            for col, item in enumerate(cells):
                self.history_table.setItem(row, col, item)

    def _ask_confirm(self) -> bool:
        answer = QMessageBox.question(
            self,
            tr("bench_clear_history"),
            tr("bench_confirm_clear"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ---------- state ----------

    def _set_busy(self, busy: bool) -> None:
        for btn in (self.cpu_btn, self.ram_btn, self.disk_btn, self.all_btn):
            btn.setEnabled(not busy)
        self.export_button.setEnabled(not busy)

    def _set_active(self, button: QPushButton | None) -> None:
        """Highlight only the button for the currently running benchmark."""
        self._active_btn = button
        for btn in self._buttons.values():
            active = btn is button
            btn.setProperty("primary", active)
            btn.setProperty("secondary", not active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ---------- i18n ----------

    def retranslate(self) -> None:
        self._title.setText(tr("bench_title"))
        self._desc.setText(tr("bench_desc"))
        self.cpu_btn.setText(tr("bench_cpu"))
        self.ram_btn.setText(tr("bench_ram"))
        self.disk_btn.setText(tr("bench_disk"))
        self.all_btn.setText(tr("bench_all"))
        self.results_title.setText(tr("bench_results_title").upper())
        self.history_title.setText(tr("bench_history_title").upper())
        self.baseline_button.setText(tr("bench_set_baseline"))
        self.clear_button.setText(tr("bench_clear_history"))
        self.export_button.setText(tr("bench_export_btn"))
        if self._task is None:
            self.status_label.setText(tr("bench_idle"))
        self.table.setHorizontalHeaderLabels([tr(key) for key in _COLUMNS])
        self.history_table.setHorizontalHeaderLabels([tr(key) for key in _HISTORY_COLUMNS])
        self._refresh_history()


def _format_value(value: float, unit: str) -> str:
    decimals = 2 if unit == "GB/s" else 1
    return f"{value:.{decimals}f}"
