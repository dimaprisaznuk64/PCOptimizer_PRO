from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.network import DEFAULT_PING_HOST, CheckResult, NetworkService, PingResult

from .tasks import Task

PING_COLUMNS = ("Time", "Host", "Avg", "Loss", "Result")
DIAG_COLUMNS = ("Check", "Status", "Detail")


class NetworkPage(QWidget):
    def __init__(self, service: NetworkService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or NetworkService()
        self._task: Task | None = None
        self._results: list[PingResult] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Network")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "Ping monitor and safe connectivity diagnostics. "
            "Checks are read-only; the only action is flushing the DNS cache."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        ping_card = QFrame()
        ping_card.setObjectName("card")
        ping_layout = QVBoxLayout(ping_card)
        ping_layout.setContentsMargins(18, 16, 18, 16)
        ping_layout.setSpacing(8)

        ping_title = QLabel("PING MONITOR")
        ping_title.setObjectName("cardTitle")
        ping_layout.addWidget(ping_title)

        controls = QHBoxLayout()
        self.host_input = QLineEdit(DEFAULT_PING_HOST)
        self.host_input.setPlaceholderText("host or IP")
        controls.addWidget(self.host_input, 1)
        self.ping_button = QPushButton("Ping ×4")
        self.ping_button.clicked.connect(self.start_ping)
        controls.addWidget(self.ping_button)
        ping_layout.addLayout(controls)

        summary = QHBoxLayout()
        self.avg_label = QLabel("avg —")
        self.avg_label.setObjectName("cardValue")
        self.loss_label = QLabel("loss —")
        self.loss_label.setObjectName("cardValue")
        summary.addWidget(self.avg_label)
        summary.addWidget(self.loss_label)
        summary.addStretch(1)
        ping_layout.addLayout(summary)

        self.ping_table = QTableWidget(0, len(PING_COLUMNS))
        self.ping_table.setHorizontalHeaderLabels(PING_COLUMNS)
        self.ping_table.verticalHeader().setVisible(False)
        self.ping_table.setShowGrid(False)
        self.ping_table.setAlternatingRowColors(True)
        self.ping_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ping_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self.ping_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        ping_layout.addWidget(self.ping_table, 1)
        splitter.addWidget(ping_card)

        diag_card = QFrame()
        diag_card.setObjectName("card")
        diag_layout = QVBoxLayout(diag_card)
        diag_layout.setContentsMargins(18, 16, 18, 16)
        diag_layout.setSpacing(8)

        diag_head = QHBoxLayout()
        diag_title = QLabel("DIAGNOSTICS")
        diag_title.setObjectName("cardTitle")
        diag_head.addWidget(diag_title)
        diag_head.addStretch(1)
        self.diag_button = QPushButton("Run checks")
        self.diag_button.clicked.connect(self.start_diagnostics)
        diag_head.addWidget(self.diag_button)
        self.flush_button = QPushButton("Flush DNS")
        self.flush_button.setProperty("secondary", True)
        self.flush_button.clicked.connect(self.start_flush)
        diag_head.addWidget(self.flush_button)
        diag_layout.addLayout(diag_head)

        self.diag_table = QTableWidget(0, len(DIAG_COLUMNS))
        self.diag_table.setHorizontalHeaderLabels(DIAG_COLUMNS)
        self.diag_table.verticalHeader().setVisible(False)
        self.diag_table.setShowGrid(False)
        self.diag_table.setAlternatingRowColors(True)
        self.diag_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.diag_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        diag_header = self.diag_table.horizontalHeader()
        diag_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        diag_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        diag_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        diag_layout.addWidget(self.diag_table, 1)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        diag_layout.addWidget(self.status_label)
        splitter.addWidget(diag_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> NetworkService:
        return self._service

    # ---------- ping ----------

    def start_ping(self) -> None:
        if self._task is not None:
            return
        host = self.host_input.text().strip() or DEFAULT_PING_HOST
        self.status_label.setText(f"Pinging {host}…")
        self._set_busy(True)
        self._task = Task(lambda: self._service.ping(host, 4), parent=self)
        self._task.done.connect(self._after_ping)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_ping(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, PingResult):
            self.status_label.setText(f"Ping failed: {result}")
            return
        self._results.append(result)
        self._render_ping(result)
        self._update_ping_summary(result)
        if result.error:
            self.status_label.setText(f"{result.host}: {result.error}")
        else:
            self.status_label.setText(
                f"{result.host}: {result.received}/{result.sent} · avg {result.avg_ms}ms"
            )

    def _render_ping(self, result: PingResult) -> None:
        self.ping_table.setSortingEnabled(False)
        row = self.ping_table.rowCount()
        self.ping_table.insertRow(row)
        self.ping_table.setItem(row, 0, QTableWidgetItem(time.strftime("%H:%M:%S")))
        self.ping_table.setItem(row, 1, QTableWidgetItem(result.host))
        avg = f"{result.avg_ms}ms" if result.avg_ms is not None else "—"
        self.ping_table.setItem(row, 2, QTableWidgetItem(avg))
        self.ping_table.setItem(row, 3, QTableWidgetItem(f"{result.loss_percent:g}%"))
        status = result.error or "ok"
        self.ping_table.setItem(row, 4, QTableWidgetItem(status))
        self.ping_table.setSortingEnabled(True)

    def _update_ping_summary(self, result: PingResult) -> None:
        if result.avg_ms is not None:
            self.avg_label.setText(f"avg {result.avg_ms}ms")
        else:
            self.avg_label.setText("avg —")
        self.loss_label.setText(f"loss {result.loss_percent:g}%")

    # ---------- diagnostics ----------

    def start_diagnostics(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Running checks…")
        self._set_busy(True)
        self._task = Task(self._service.diagnostics, parent=self)
        self._task.done.connect(self._after_diagnostics)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_diagnostics(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(f"Diagnostics failed: {result}")
            return
        checks = [r for r in result if isinstance(r, CheckResult)]
        self.diag_table.setSortingEnabled(False)
        self.diag_table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            name_item = QTableWidgetItem(check.name)
            status_item = QTableWidgetItem("OK" if check.ok else "FAIL")
            detail_item = QTableWidgetItem(check.detail)
            detail_item.setToolTip(check.detail)
            self.diag_table.setItem(row, 0, name_item)
            self.diag_table.setItem(row, 1, status_item)
            self.diag_table.setItem(row, 2, detail_item)
        self.diag_table.setSortingEnabled(True)
        failed = sum(1 for c in checks if not c.ok)
        self.status_label.setText(
            f"{len(checks) - failed}/{len(checks)} checks passed"
            if failed
            else f"all {len(checks)} checks passed"
        )

    def start_flush(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Flushing DNS cache…")
        self._set_busy(True)
        self._task = Task(self._service.flush_dns, parent=self)
        self._task.done.connect(self._after_flush)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_flush(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(str(result))

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.ping_button.setEnabled(not busy)
        self.diag_button.setEnabled(not busy)
        self.flush_button.setEnabled(not busy)
        self.host_input.setEnabled(not busy)
