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
        self.cpu_btn.setProperty("primary", True)
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
        self.status_label = QLabel(tr("bench_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, 5)
        headers = (tr("bench_col_type"), tr("bench_col_score"), tr("bench_col_units"),
                   tr("bench_col_ms"), tr("bench_col_info"))
        self.table.setHorizontalHeaderLabels(list(headers))
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        for i in range(5):
            if i in (1, 2, 3):
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
        if "Running" not in self.status_label.text() and "…" not in self.status_label.text():
            self.status_label.setText(tr("bench_idle"))
        headers = (tr("bench_col_type"), tr("bench_col_score"), tr("bench_col_units"),
                   tr("bench_col_ms"), tr("bench_col_info"))
        self.table.setHorizontalHeaderLabels(list(headers))

    def start_run(self, btype: BenchmarkType) -> None:
        if self._task is not None:
            return
        self._set_busy(True)
        self.status_label.setText(tr("bench_running"))
        path = data_root() / "bench_temp.bin" if btype in (BenchmarkType.DISK, BenchmarkType.ALL) else None
        self._task = Task(lambda p=path: self._service.run(btype, disk_path=p), parent=self)
        self._task.done.connect(self._on_done)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _on_done(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if isinstance(result, list):
            self.status_label.setText(tr("bench_done", count=len(result)))
            self._render_results(result)
        else:
            self.status_label.setText(tr("bench_failed", msg=str(result)))
            self._render_results([])

    def _on_failed(self, msg: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("bench_failed", msg=msg))
        self._render_results([])

    def _render_results(self, results) -> None:
        self.table.setRowCount(len(results))
        for i, r in enumerate(results):
            self.table.setItem(i, 0, QTableWidgetItem(r.type.name))
            self.table.setItem(i, 1, QTableWidgetItem(f"{r.score:.1f}"))
            self.table.setItem(i, 2, QTableWidgetItem(r.units))
            self.table.setItem(i, 3, QTableWidgetItem(str(r.duration_ms)))
            self.table.setItem(i, 4, QTableWidgetItem(r.info))

    def _set_busy(self, busy: bool) -> None:
        for btn in (self.cpu_btn, self.ram_btn, self.disk_btn, self.all_btn):
            btn.setEnabled(not busy)
