from __future__ import annotations

from datetime import datetime
import time

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

from app.processes import ProcessInfo, ProcessService, ProcessServiceError, ProcessNotFound, ProtectedProcessError

from .format import mb, uptime

COLUMNS = ("Name", "PID", "CPU %", "Memory", "User")


class ProcessPage(QWidget):
    def __init__(self, service: ProcessService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or ProcessService()
        self._rows: dict[int, ProcessInfo] = {}
        self._last_refresh_ts = 0.0
        self._auto_refresh_interval = 3.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Processes")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("Running processes — select a row for details, end protected processes is blocked")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter by name, PID or user…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(lambda _t: self.refresh())
        toolbar.addWidget(self.filter, 1)

        self.count_label = QLabel("")
        self.count_label.setObjectName("cardSub")
        toolbar.addWidget(self.count_label)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.refresh)
        toolbar.addWidget(self.refresh_button)

        self.end_button = QPushButton("End process")
        self.end_button.setProperty("danger", True)
        self.end_button.setEnabled(False)
        self.end_button.clicked.connect(self.end_selected)
        toolbar.addWidget(self.end_button)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(2, Qt.SortOrder.DescendingOrder)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        details = QFrame()
        details.setObjectName("card")
        details.setMinimumWidth(320)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(8)

        details_title = QLabel("DETAILS")
        details_title.setObjectName("cardTitle")
        details_layout.addWidget(details_title)

        self.detail_name = QLabel("Select a process")
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

    @property
    def service(self) -> ProcessService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    def apply_snapshot(self, snapshot) -> None:
        if self.isVisible():
            now = time.monotonic()
            if now - self._last_refresh_ts >= self._auto_refresh_interval:
                self.refresh()

    def refresh(self) -> None:
        self._last_refresh_ts = time.monotonic()
        try:
            processes = self._service.list()
        except Exception as e:
            self.status_label.setText(f"Failed to list processes: {e}")
            return

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
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        for row, p in enumerate(filtered):
            name_item = QTableWidgetItem(p.name)
            name_item.setData(Qt.ItemDataRole.UserRole, p.pid)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, self._number_item(p.pid))
            self.table.setItem(row, 2, self._number_item(round(p.cpu_percent, 1)))
            memory = QTableWidgetItem(mb(p.memory_bytes))
            memory.setData(Qt.ItemDataRole.DisplayRole, float(p.memory_bytes))
            self.table.setItem(row, 3, memory)
            self.table.setItem(row, 4, QTableWidgetItem(p.username or "—"))

        self.table.setSortingEnabled(True)
        self.count_label.setText(f"{len(filtered)} processes")

        if selected_pid is not None and selected_pid in self._rows:
            self._select_pid(selected_pid)
        else:
            self.table.clearSelection()
            self._on_selection_changed()

    @staticmethod
    def _number_item(value: int | float) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setData(Qt.ItemDataRole.DisplayRole, value)
        return item

    def _selected_pid(self) -> int | None:
        row = self.table.currentRow()
        if row >= 0:
            item = self.table.item(row, 0)
        else:
            selected = self.table.selectedItems()
            item = selected[0] if selected else None
        if item is None:
            return None
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
        info: ProcessInfo | None = None
        if pid is not None:
            try:
                info = self._service.details(pid)
            except Exception:
                info = self._rows.get(pid)
        if info is None:
            self.detail_name.setText("Select a process")
            for label in self.detail_rows.values():
                label.setText("")
            self.detail_exe.setText("")
            self.detail_cmd.setText("")
            self.protected_badge.setVisible(False)
            self.end_button.setEnabled(False)
            return

        self.detail_name.setText(f"{info.name} (PID {info.pid})")
        started = (
            datetime.fromtimestamp(info.create_time).strftime("%Y-%m-%d %H:%M:%S")
            if info.create_time
            else "—"
        )
        values = {
            "pid": f"PID  {info.pid}",
            "user": f"User  {info.username or '—'}",
            "status": f"Status  {info.status}",
            "cpu": f"CPU  {info.cpu_percent:.1f}%",
            "memory": f"Memory  {mb(info.memory_bytes)} · {info.memory_percent:.1f}%",
            "started": f"Started  {started}",
            "uptime": f"Uptime  {uptime(info.uptime_seconds)}",
            "threads": f"Threads  {info.num_threads if info.num_threads is not None else '—'}",
            "parent": f"Parent  {info.ppid if info.ppid is not None else '—'}",
        }
        for key, text in values.items():
            self.detail_rows[key].setText(text)

        self.detail_exe.setText(f"Path  {info.exe or '—'}")
        self.detail_cmd.setText(f"Cmd  {info.cmdline or '—'}")
        if info.protected_reason:
            self.protected_badge.setText(f"PROTECTED · {info.protected_reason}")
            self.protected_badge.setVisible(True)
        else:
            self.protected_badge.setVisible(False)
        self.end_button.setEnabled(True)

    def _ask_confirm(self, info: ProcessInfo) -> bool:
        answer = QMessageBox.question(
            self,
            "End process",
            f"Terminate {info.name} (PID {info.pid})?",
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
            self._warn("Protected process", str(e))
            return
        except ProcessNotFound:
            self.status_label.setText(f"{info.name} already exited")
            self.refresh()
            return
        except ProcessServiceError as e:
            self._warn("Cannot end process", str(e))
            return
        self.status_label.setText(f"{'Ended' if ended else 'Failed to end'} {info.name} (PID {info.pid})")
        self.refresh()
