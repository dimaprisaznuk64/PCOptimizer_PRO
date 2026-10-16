from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.benchmarks import BenchmarkService, BenchmarkType
from app.i18n import tr
from app.settings import data_root

from .components import attach_empty_hint
from .tasks import Task

_COLUMNS = (
    "bench_col_metric",
    "bench_col_value",
    "bench_col_unit",
    "bench_col_ms",
    "bench_col_runs",
    "bench_col_detail",
)


class BenchmarksPage(QWidget):
    def __init__(self, service: BenchmarkService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or BenchmarkService()
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

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(key) for key in _COLUMNS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        for i in range(len(_COLUMNS)):
            if i in (1, 2, 3, 4):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
        attach_empty_hint(self.table, "bench_empty")
        layout.addWidget(self.table, 1)

    @property
    def service(self) -> BenchmarkService:
        return self._service

    def retranslate(self) -> None:
        self._title.setText(tr("bench_title"))
        self._desc.setText(tr("bench_desc"))
        self.cpu_btn.setText(tr("bench_cpu"))
        self.ram_btn.setText(tr("bench_ram"))
        self.disk_btn.setText(tr("bench_disk"))
        self.all_btn.setText(tr("bench_all"))
        if self._task is None:
            self.status_label.setText(tr("bench_idle"))
        self.table.setHorizontalHeaderLabels([tr(key) for key in _COLUMNS])

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
        self.status_label.setText(tr("bench_done", count=len(results)))
        self._render_results(results)

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
                tr(f"bench_metric_{result.metric}"),
                f"{result.value:.{decimals}f}",
                result.unit,
                str(result.duration_ms),
                str(result.runs),
                result.detail,
            )
            for col, text in enumerate(cells):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def _set_busy(self, busy: bool) -> None:
        for btn in (self.cpu_btn, self.ram_btn, self.disk_btn, self.all_btn):
            btn.setEnabled(not busy)

    def _set_active(self, button: QPushButton | None) -> None:
        """Highlight only the button for the currently running benchmark."""
        self._active_btn = button
        for btn in self._buttons.values():
            active = btn is button
            btn.setProperty("primary", active)
            btn.setProperty("secondary", not active)
            btn.style().unpolish(btn)
            btn.style().polish(btn)
