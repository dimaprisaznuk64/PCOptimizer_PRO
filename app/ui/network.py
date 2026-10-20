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

from app.i18n import tr
from app.network import DEFAULT_PING_HOST, CheckResult, NetworkService, PingResult

from .activity import record as log_action
from .components import attach_empty_hint
from .tasks import Task
from .theme import CARD_PADDING

PING_COLUMN_KEYS = ("net_col_time", "net_col_host", "net_col_avg", "net_col_loss", "net_col_result")
DIAG_COLUMN_KEYS = ("net_col_check", "net_col_status", "net_col_detail")


_CHECK_NAMES = {"Proxy": "net_chk_proxy", "Internet": "net_chk_internet", "Gateway": "net_chk_gateway",
                "DNS": "net_chk_dns", "Adapters": "net_chk_adapters"}
_CHECK_DETAIL_RULES = (
    (r"no system proxy", "net_cd_noproxy"),
    (r"(?P<host>\S+) avg (?P<n>\d+(?:\.\d+)?)ms", "net_cd_internet"),
    (r"(?P<host>\S+) resolved in (?P<n>\d+(?:\.\d+)?)ms", "net_cd_dns"),
    (r"(?P<n>\d+) up: (?P<names>.+)", "net_cd_adapters"),
    (r"no active adapters", "net_cd_noadapters"),
    (r"no default gateway found", "net_cd_nogateway"),
)


def _check_name(name: str) -> str:
    key = _CHECK_NAMES.get(name)
    return tr(key) if key else name


def _check_detail(detail: str) -> str:
    import re

    for pattern, key in _CHECK_DETAIL_RULES:
        m = re.fullmatch(pattern, detail)
        if m:
            return tr(key, **m.groupdict())
    return detail


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

        title = QLabel(tr("net_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("net_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        splitter = QSplitter(Qt.Orientation.Horizontal)

        ping_card = QFrame()
        ping_card.setObjectName("card")
        ping_layout = QVBoxLayout(ping_card)
        ping_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        ping_layout.setSpacing(8)

        ping_title = QLabel(tr("net_ping_title"))
        ping_title.setObjectName("cardTitle")
        ping_layout.addWidget(ping_title)
        self._ping_title = ping_title

        controls = QHBoxLayout()
        self.host_input = QLineEdit(DEFAULT_PING_HOST)
        self.host_input.setPlaceholderText(tr("net_host_placeholder"))
        controls.addWidget(self.host_input, 1)
        self.ping_button = QPushButton(tr("net_ping_btn"))
        self.ping_button.setProperty("primary", True)
        self.ping_button.clicked.connect(self.start_ping)
        controls.addWidget(self.ping_button)
        ping_layout.addLayout(controls)

        summary = QHBoxLayout()
        self.avg_label = QLabel(tr("net_avg_none"))
        self.avg_label.setObjectName("statValue")
        self.loss_label = QLabel(tr("net_loss_n", pct=0))
        self.loss_label.setObjectName("statValue")
        summary.addWidget(self.avg_label)
        summary.addWidget(self.loss_label)
        summary.addStretch(1)
        ping_layout.addLayout(summary)

        self.ping_table = QTableWidget(0, len(PING_COLUMN_KEYS))
        attach_empty_hint(self.ping_table, "empty_ping")
        self.ping_table.setHorizontalHeaderLabels([tr(k) for k in PING_COLUMN_KEYS])
        self.ping_table.verticalHeader().setVisible(False)
        self.ping_table.setShowGrid(False)
        self.ping_table.setAlternatingRowColors(True)
        self.ping_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.ping_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        header = self.ping_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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
        diag_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        diag_layout.setSpacing(8)

        diag_head = QHBoxLayout()
        diag_title = QLabel(tr("net_diag_title"))
        diag_title.setObjectName("cardTitle")
        diag_head.addWidget(diag_title)
        self._diag_title = diag_title
        diag_head.addStretch(1)
        self.diag_button = QPushButton(tr("net_diag_btn"))
        self.diag_button.setProperty("primary", True)
        self.diag_button.clicked.connect(self.start_diagnostics)
        diag_head.addWidget(self.diag_button)
        self.flush_button = QPushButton(tr("net_flush_btn"))
        self.flush_button.setProperty("secondary", True)
        self.flush_button.clicked.connect(self.start_flush)
        diag_head.addWidget(self.flush_button)
        diag_layout.addLayout(diag_head)

        self.diag_table = QTableWidget(0, len(DIAG_COLUMN_KEYS))
        attach_empty_hint(self.diag_table, "empty_diag")
        self.diag_table.setHorizontalHeaderLabels([tr(k) for k in DIAG_COLUMN_KEYS])
        self.diag_table.verticalHeader().setVisible(False)
        self.diag_table.setShowGrid(False)
        self.diag_table.setAlternatingRowColors(True)
        self.diag_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.diag_table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        diag_header = self.diag_table.horizontalHeader()
        diag_header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        diag_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        diag_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        diag_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        diag_layout.addWidget(self.diag_table, 1)

        self.status_label = QLabel(tr("net_idle"))
        self.status_label.setObjectName("cardSub")
        diag_layout.addWidget(self.status_label)
        splitter.addWidget(diag_card)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> NetworkService:
        return self._service

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("net_title"))
        self._desc.setText(tr("net_desc"))
        self._ping_title.setText(tr("net_ping_title"))
        self._diag_title.setText(tr("net_diag_title"))
        self.host_input.setPlaceholderText(tr("net_host_placeholder"))
        self.ping_button.setText(tr("net_ping_btn"))
        self.diag_button.setText(tr("net_diag_btn"))
        self.flush_button.setText(tr("net_flush_btn"))
        self.avg_label.setText(tr("net_avg_none") if not self._results else self.avg_label.text())
        self.ping_table.setHorizontalHeaderLabels([tr(k) for k in PING_COLUMN_KEYS])
        self.diag_table.setHorizontalHeaderLabels([tr(k) for k in DIAG_COLUMN_KEYS])

    # ---------- ping ----------

    def start_ping(self) -> None:
        if self._task is not None:
            return
        host = self.host_input.text().strip() or DEFAULT_PING_HOST
        self.status_label.setText(tr("net_pinging", host=host))
        self._set_busy(True)
        self._task = Task(lambda: self._service.ping(host, 4), parent=self)
        self._task.done.connect(self._after_ping)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_ping(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, PingResult):
            self.status_label.setText(tr("net_ping_failed", msg=result))
            return
        self._results.append(result)
        self._render_ping(result)
        self._update_ping_summary(result)
        if result.error:
            self.status_label.setText(f"{result.host}: {result.error}")
        else:
            self.status_label.setText(
                tr("net_ping_result", host=result.host, received=result.received, sent=result.sent, avg=result.avg_ms, avg_unit="ms")
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
        status = result.error or tr("net_overall_ok")
        self.ping_table.setItem(row, 4, QTableWidgetItem(status))
        self.ping_table.setSortingEnabled(True)

    def _update_ping_summary(self, result: PingResult) -> None:
        if result.avg_ms is not None:
            self.avg_label.setText(f"{tr('net_avg')} {result.avg_ms}ms")
        else:
            self.avg_label.setText(tr("net_avg_none"))
        self.loss_label.setText(tr("net_loss_n", pct=result.loss_percent))

    # ---------- diagnostics ----------

    def start_diagnostics(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("net_running"))
        self._set_busy(True)
        self._task = Task(self._service.diagnostics, parent=self)
        self._task.done.connect(self._after_diagnostics)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_diagnostics(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(tr("net_diag_failed", msg=result))
            return
        checks = [r for r in result if isinstance(r, CheckResult)]
        self.diag_table.setSortingEnabled(False)
        self.diag_table.setRowCount(len(checks))
        for row, check in enumerate(checks):
            name_item = QTableWidgetItem(_check_name(check.name))
            status_item = QTableWidgetItem(tr("net_ok_short") if check.ok else tr("net_fail_short"))
            detail_item = QTableWidgetItem(_check_detail(check.detail))
            detail_item.setToolTip(check.detail)
            self.diag_table.setItem(row, 0, name_item)
            self.diag_table.setItem(row, 1, status_item)
            self.diag_table.setItem(row, 2, detail_item)
        self.diag_table.setSortingEnabled(True)
        failed = sum(1 for c in checks if not c.ok)
        self.status_label.setText(
            tr("net_checks_partial", ok=len(checks) - failed, total=len(checks))
            if failed
            else tr("net_checks_all", total=len(checks))
        )

    def start_flush(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("net_flushing"))
        self._set_busy(True)
        self._task = Task(self._service.flush_dns, parent=self)
        self._task.done.connect(self._after_flush)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_flush(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(str(result))
        log_action(tr("act_dns"), tr("act_done"))

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("net_failed", msg=message))

    def _set_busy(self, busy: bool) -> None:
        self.ping_button.setEnabled(not busy)
        self.diag_button.setEnabled(not busy)
        self.flush_button.setEnabled(not busy)
        self.host_input.setEnabled(not busy)
