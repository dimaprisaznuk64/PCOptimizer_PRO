from __future__ import annotations

import time
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.processes import (
    ProcessInfo,
    ProcessNotFound,
    ProcessService,
    ProcessServiceError,
    ProtectedProcessError,
)

from .components import CardTitleLabel, align_numeric_headers
from .format import mb, uptime
from .tasks import Task
from .theme import CARD_PADDING

COLUMN_KEYS = ("proc_col_name", "proc_col_pid", "proc_col_cpu", "proc_col_mem", "proc_col_user")
COLUMNS = tuple(tr(k) for k in COLUMN_KEYS)

_DETAIL_TR: dict[str, str] = {
    "user": "proc_detail_user",
    "status": "proc_detail_status",
    "cpu": "proc_detail_cpu",
    "memory": "proc_detail_memory",
    "started": "proc_detail_started",
    "uptime": "proc_detail_uptime",
    "threads": "proc_detail_threads",
    "parent": "proc_detail_parent",
}

_REFRESH_INTERVAL_S = 2.0

# Fixed widths for the fixed columns (0 = name stretches). Tuned to fit PID /
# CPU / memory / user without running the expensive ResizeToContents pass.
_COL_WIDTHS = {1: 70, 2: 66, 3: 92, 4: 150}


class _NumItem(QTableWidgetItem):
    """Right-aligned number shown with a fixed format ('.' decimal) but sorted by its real value."""

    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self._value = float(value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other) -> bool:
        if isinstance(other, _NumItem):
            return self._value < other._value
        return super().__lt__(other)


class _SizeItem(QTableWidgetItem):
    """Shows formatted text but sorts by the raw byte count."""

    def __init__(self, text: str, value: float) -> None:
        super().__init__(text)
        self._value = float(value)
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other) -> bool:
        if isinstance(other, _SizeItem):
            return self._value < other._value
        return super().__lt__(other)


class ProcessPage(QWidget):
    def __init__(self, service: ProcessService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or ProcessService()
        self._rows: dict[int, ProcessInfo] = {}
        self._task: Task | None = None
        self._details_task: Task | None = None
        self._details_pid: int | None = None
        self._last_refresh = 0.0
        self._signature: list[tuple] | None = None
        self._all: list[ProcessInfo] | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("proc_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("proc_desc"))
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText(tr("proc_filter_placeholder"))
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _t: self._refilter())
        toolbar.addWidget(self.filter, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("cardSub")
        toolbar.addWidget(self.count_label)

        self.refresh_button = QPushButton(tr("proc_refresh"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(lambda: self.start_refresh(force=True))
        toolbar.addWidget(self.refresh_button)

        self.end_button = QPushButton(tr("proc_end"))
        self.end_button.setProperty("danger", True)
        self.end_button.setEnabled(False)
        self.end_button.clicked.connect(self.end_selected)
        toolbar.addWidget(self.end_button)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        align_numeric_headers(self.table, (1, 2, 3))
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(COLUMNS)):
            # ``ResizeToContents`` re-measures every cell on each refresh, which
            # is O(rows) layout work and makes the page stutter with hundreds of
            # processes — fixed widths are stable and cheap.
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
            self.table.setColumnWidth(col, _COL_WIDTHS[col])
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        details = QFrame()
        details.setObjectName("card")
        details.setMinimumWidth(320)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        details_layout.setSpacing(8)

        details_title = CardTitleLabel(tr("proc_details"))
        details_layout.addWidget(details_title)

        self._details_title = details_title

        self.detail_name = QLabel(tr("proc_select_hint"))
        self.detail_name.setObjectName("gpuName")
        self.detail_name.setWordWrap(True)
        details_layout.addWidget(self.detail_name)

        self.protected_badge = QLabel("")
        self.protected_badge.setObjectName("pageBadge")
        self.protected_badge.setVisible(False)
        details_layout.addWidget(self.protected_badge, 0, Qt.AlignmentFlag.AlignLeft)

        self.detail_rows: dict[str, QLabel] = {}
        for key in ("pid", "user", "status", "cpu", "memory", "started", "uptime", "threads", "parent"):
            label = QLabel("")
            label.setObjectName("cardRow")
            label.setWordWrap(True)
            self.detail_rows[key] = label
            details_layout.addWidget(label)

        exe_label = QLabel("")
        exe_label.setObjectName("cardSub")
        exe_label.setWordWrap(True)
        self.detail_exe = exe_label
        details_layout.addWidget(exe_label)

        cmd_label = QLabel("")
        cmd_label.setObjectName("cardSub")
        cmd_label.setWordWrap(True)
        self.detail_cmd = cmd_label
        details_layout.addWidget(cmd_label)

        details_layout.addStretch(1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("")
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self._detail_info: ProcessInfo | None = None

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("proc_title"))
        self._desc.setText(tr("proc_desc"))
        self.filter.setPlaceholderText(tr("proc_filter_placeholder"))
        self.refresh_button.setText(tr("proc_refresh"))
        self.end_button.setText(tr("proc_end"))
        self._details_title.setText(tr("proc_details"))
        self.table.setHorizontalHeaderLabels(tuple(tr(k) for k in COLUMN_KEYS))
        align_numeric_headers(self.table, (1, 2, 3))
        if self._detail_info is None:
            self.detail_name.setText(tr("proc_select_hint"))
        else:
            self.detail_name.setText(f"{self._detail_info.name} (PID {self._detail_info.pid})")
            self._on_selection_changed()
        if self._rows:
            self.count_label.setText(tr("proc_count", count=len(self._rows)))

    @property
    def service(self) -> ProcessService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.start_refresh()

    def apply_snapshot(self, snapshot) -> None:
        if self.isVisible():
            self.start_refresh()

    def start_refresh(self, force: bool = False) -> None:
        if self._task is not None:
            return
        now = time.monotonic()
        if not force and now - self._last_refresh < _REFRESH_INTERVAL_S:
            return
        self._last_refresh = now
        self._task = Task(self._service.list, parent=self)
        self._task.done.connect(self._apply_result)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_result(self, result: object) -> None:
        self._task = None
        if not isinstance(result, list):
            self.status_label.setText(tr("proc_failed_list", msg=result))
            return
        self._all = result
        self._render(result)

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self.status_label.setText(tr("proc_failed_list", msg=message))

    def refresh(self) -> None:
        try:
            processes = self._service.list()
        except Exception as e:
            self.status_label.setText(tr("proc_failed_list", msg=e))
            return
        self._all = processes
        self._render(processes)

    def _refilter(self) -> None:
        """Re-filter the cached process list without a new psutil scan."""
        if self._all is not None:
            self._render(self._all)

    def _render(self, processes: list[ProcessInfo]) -> None:
        needle = self.filter.text().strip().lower()
        selected_pid = self._selected_pid()

        filtered = [
            p
            for p in processes
            if not needle
            or needle in p.name.lower()
            or needle == str(p.pid)
            or needle in (p.username or "").lower()
        ]

        self._rows = {p.pid: p for p in filtered}
        self.count_label.setText(tr("proc_count", count=len(filtered)))

        # Skip the expensive full rebuild when nothing that we display changed;
        # the sampler tick fires far more often than the data actually moves.
        signature = [
            (p.pid, round(p.cpu_percent, 1), p.memory_bytes, p.username or "")
            for p in filtered
        ]
        if signature == self._signature:
            return
        self._signature = signature

        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        try:
            self.table.setSortingEnabled(False)
            self.table.setRowCount(len(filtered))
            for row, p in enumerate(filtered):
                name_item = QTableWidgetItem(p.name)
                name_item.setData(Qt.ItemDataRole.UserRole, p.pid)
                self.table.setItem(row, 0, name_item)
                self.table.setItem(row, 1, self._number_item(p.pid))
                self.table.setItem(row, 2, _NumItem(f"{p.cpu_percent:.1f}", p.cpu_percent))
                memory = _SizeItem(mb(p.memory_bytes), p.memory_bytes)
                self.table.setItem(row, 3, memory)
                self.table.setItem(row, 4, QTableWidgetItem(p.username or "—"))
            self.table.setSortingEnabled(True)
            if selected_pid is not None and selected_pid in self._rows:
                self._select_pid(selected_pid)
            else:
                self.table.clearSelection()
        finally:
            self.table.blockSignals(False)
            self.table.setUpdatesEnabled(True)

        if selected_pid is None or selected_pid not in self._rows:
            self._on_selection_changed()

    @staticmethod
    def _number_item(value: float) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return item

    def _selected_pid(self) -> int | None:
        row = self.table.currentRow()
        if row < 0:
            item = self.table.item(row, 0) if self.table.selectedItems() else None
        else:
            item = self.table.item(row, 0)
        if item is None:
            selected = self.table.selectedItems()
            if not selected:
                return None
            item = selected[0]
        pid = item.data(Qt.ItemDataRole.UserRole)
        return int(pid) if pid is not None else None

    def _select_pid(self, pid: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == pid:
                self.table.selectRow(row)
                return

    def _on_selection_changed(self) -> None:
        pid = self._selected_pid()
        if pid is None:
            self._show_details(None)
            return
        # Show what we already have immediately, then fill in the heavy fields
        # (status / threads / cmdline) off the GUI thread — ``details()`` does a
        # second psutil round-trip that would otherwise freeze the window.
        self._show_details(self._rows.get(pid), pending=True)
        if self._details_task is not None:
            return
        self._details_pid = pid
        self._details_task = Task(lambda: self._service.details(pid), parent=self)
        self._details_task.done.connect(self._apply_details)
        self._details_task.failed.connect(self._on_details_failed)
        self._details_task.start()

    def _apply_details(self, result: object) -> None:
        self._details_task = None
        if isinstance(result, ProcessInfo):
            self._show_details(result)

    def _on_details_failed(self, _message: str) -> None:
        self._details_task = None

    def _show_details(self, info: ProcessInfo | None, pending: bool = False) -> None:
        self._detail_info = info
        if info is None:
            self.detail_name.setText(tr("proc_select_hint"))
            for label in self.detail_rows.values():
                label.setText("")
            self.detail_exe.setText("")
            self.detail_cmd.setText("")
            self.protected_badge.setVisible(False)
            self.end_button.setEnabled(False)
            return

        self.detail_name.setText(f"{info.name} (PID {info.pid})")
        self.detail_rows["pid"].setText(f"PID  {info.pid}")
        self.detail_rows["user"].setText(tr("proc_detail_user", value=info.username or "—"))
        self.detail_rows["status"].setText(tr("proc_detail_status", value=info.status or "…"))
        self.detail_rows["cpu"].setText(tr("proc_detail_cpu", value=f"{info.cpu_percent:.1f}%"))
        self.detail_rows["memory"].setText(
            tr("proc_detail_memory", value=mb(info.memory_bytes), pct=f"{info.memory_percent:.1f}%")
        )
        started = (
            datetime.fromtimestamp(info.create_time).strftime("%Y-%m-%d %H:%M:%S")
            if info.create_time
            else "—"
        )
        self.detail_rows["started"].setText(tr("proc_detail_started", value=started))
        self.detail_rows["uptime"].setText(tr("proc_detail_uptime", value=uptime(info.uptime_seconds)))
        self.detail_rows["threads"].setText(
            tr("proc_detail_threads", value=info.num_threads if info.num_threads is not None else "—")
        )
        self.detail_rows["parent"].setText(
            tr("proc_detail_parent", value=info.ppid if info.ppid is not None else "—")
        )

        self.detail_exe.setText(tr("proc_detail_path", value=info.exe or "—"))
        self.detail_cmd.setText(tr("proc_detail_cmd", value=info.cmdline or "—"))
        if info.protected_reason:
            self.protected_badge.setText(tr("proc_protected", reason=info.protected_reason))
            self.protected_badge.setVisible(True)
        else:
            self.protected_badge.setVisible(False)
        self.end_button.setEnabled(True)

    def _ask_confirm(self, info: ProcessInfo) -> bool:
        answer = QMessageBox.question(
            self,
            tr("proc_confirm_title"),
            tr("proc_confirm_msg", name=info.name, pid=info.pid),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _warn(self, title: str, message: str) -> None:
        QMessageBox.warning(self, title, message)

    def end_selected(self) -> None:
        pid = self._selected_pid()
        info = self._rows.get(pid) if pid is not None else None
        if info is None:
            return
        if not self._ask_confirm(info):
            return
        try:
            ended = self._service.terminate(info.pid)
        except ProtectedProcessError as e:
            self._warn(tr("proc_protected_title"), str(e))
            return
        except ProcessNotFound:
            self.status_label.setText(tr("proc_already_exited", name=info.name))
            self.start_refresh(force=True)
            return
        except ProcessServiceError as e:
            self._warn(tr("proc_cannot_end"), str(e))
            return
        key = "proc_ended" if ended else "proc_end_failed"
        self.status_label.setText(tr(key, name=info.name, pid=info.pid))
        self.start_refresh(force=True)
