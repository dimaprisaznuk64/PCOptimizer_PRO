from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from app.startup import StartupItem, StartupService

from .format import mb
from .tasks import Task

COLUMNS = ("Name", "Source", "Command", "Impact", "State")


class StartupPage(QWidget):
    def __init__(self, service: StartupService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or StartupService()
        self._items: list[StartupItem] = []
        self._errors: list[str] = []
        self._task: Task | None = None
        self.detail_rows: dict[str, QLabel] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Startup")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("Programs that launch at logon — registry Run keys, Startup folder and Task Scheduler")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)

        self.toggle_button = QPushButton("Enable / Disable")
        self.toggle_button.setProperty("secondary", True)
        self.toggle_button.setEnabled(False)
        self.toggle_button.clicked.connect(self.start_toggle)
        toolbar.addWidget(self.toggle_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setProperty("danger", True)
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.start_remove)
        toolbar.addWidget(self.remove_button)

        self.undo_button = QPushButton("Undo last")
        self.undo_button.setProperty("secondary", True)
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.start_undo)
        toolbar.addWidget(self.undo_button)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
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
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSortingEnabled(True)
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

        self.detail_name = QLabel("Select an entry")
        self.detail_name.setObjectName("gpuName")
        self.detail_name.setWordWrap(True)
        details_layout.addWidget(self.detail_name)

        self.detail_badge = QLabel("")
        self.detail_badge.setObjectName("pageBadge")
        self.detail_badge.setVisible(False)
        details_layout.addWidget(self.detail_badge, 0, Qt.AlignmentFlag.AlignLeft)

        for key in ("source", "state", "impact", "target", "location"):
            label = QLabel("")
            label.setObjectName("cardRow")
            label.setWordWrap(True)
            self.detail_rows[key] = label
            details_layout.addWidget(label)

        command_label = QLabel("")
        command_label.setObjectName("cardSub")
        command_label.setWordWrap(True)
        self.detail_command = command_label
        details_layout.addWidget(command_label)

        note = QLabel("Disabling is reversible. Removed entries are backed up and can be restored with Undo.")
        note.setObjectName("cardSub")
        note.setWordWrap(True)
        details_layout.addWidget(note)
        details_layout.addStretch(1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> StartupService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._items and self._task is None:
            self.start_refresh()

    def start_refresh(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Loading startup entries…")
        self._set_busy(True)
        self._task = Task(self._service.list_items, parent=self)
        self._task.done.connect(self._apply_list)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_list(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, tuple) or len(result) != 2:
            self.status_label.setText(f"Load failed: {result}")
            return
        items, errors = result
        self._items = list(items)
        self._errors = list(errors)
        self.undo_button.setEnabled(self._history_exists())
        self._render_table()
        message = f"{len(self._items)} startup entries"
        if errors:
            message += f" · issues: {'; '.join(errors[:2])}"
        self.status_label.setText(message)
        self._on_selection_changed()

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.toggle_button.setEnabled(False)
            self.remove_button.setEnabled(False)

    def start_toggle(self) -> None:
        item = self._selected_item()
        if item is None or self._task is not None:
            return
        target_state = not item.enabled
        verb = "Enable" if target_state else "Disable"
        if not self._ask_confirm(f"{verb} {item.name}?", item):
            return
        self.status_label.setText(f"{verb} {item.name}…")
        self._set_busy(True)
        self._task = Task(lambda: self._service.set_enabled(item, target_state), parent=self)
        self._task.done.connect(lambda _r, name=item.name, verb=verb: self._after_change(f"{verb}d {name}"))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def start_remove(self) -> None:
        item = self._selected_item()
        if item is None or self._task is not None:
            return
        if not self._ask_confirm(f"Remove {item.name} from startup?", item):
            return
        self.status_label.setText(f"Removing {item.name}…")
        self._set_busy(True)
        self._task = Task(lambda: self._service.remove(item), parent=self)
        self._task.done.connect(lambda result, name=item.name: self._after_change(str(result) or f"Removed {name}"))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def start_undo(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Restoring last removal…")
        self._set_busy(True)
        self._task = Task(self._service.undo_last, parent=self)
        self._task.done.connect(lambda result: self._after_change(str(result)))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_change(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(message)
        self.start_refresh()

    def _history_exists(self) -> bool:
        try:
            history = self._service._history_path()
            return history.exists() and bool(history.read_text(encoding="utf-8").strip())
        except OSError:
            return False

    def _render_table(self) -> None:
        selected_id = self._selected_item().id if self._selected_item() else None
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._items))
        for row, item in enumerate(self._items):
            name_item = QTableWidgetItem(item.name)
            name_item.setData(Qt.ItemDataRole.UserRole, item.id)
            name_item.setToolTip(item.impact_reason)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(item.source))
            command_item = QTableWidgetItem(item.command)
            command_item.setToolTip(item.command)
            self.table.setItem(row, 2, command_item)
            impact_item = QTableWidgetItem(item.impact)
            impact_item.setData(Qt.ItemDataRole.UserRole, item.id)
            self.table.setItem(row, 3, impact_item)
            state_item = QTableWidgetItem("Enabled" if item.enabled else "Disabled")
            self.table.setItem(row, 4, state_item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        if selected_id:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item is not None and item.data(Qt.ItemDataRole.UserRole) == selected_id:
                    self.table.selectRow(row)
                    return

    def _selected_item(self) -> StartupItem | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return None
        item_id = item.data(Qt.ItemDataRole.UserRole)
        for candidate in self._items:
            if candidate.id == item_id:
                return candidate
        return None

    def _on_selection_changed(self) -> None:
        item = self._selected_item()
        if item is None:
            self.detail_name.setText("Select an entry")
            self.detail_badge.setVisible(False)
            for label in self.detail_rows.values():
                label.setText("")
            self.detail_command.setText("")
            self.toggle_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return

        self.detail_name.setText(item.name)
        self.detail_badge.setText("DISABLED" if not item.enabled else item.impact.upper())
        self.detail_badge.setVisible(True)
        self.detail_rows["source"].setText(f"Source  {item.source}")
        self.detail_rows["state"].setText(f"State  {'Enabled' if item.enabled else 'Disabled'}")
        self.detail_rows["impact"].setText(f"Impact  {item.impact} — {item.impact_reason}")
        self.detail_rows["target"].setText(f"Target size  {mb(item.target_size)}")
        self.detail_rows["location"].setText(f"Location  {item.location}")
        self.detail_command.setText(f"Command  {item.command}")

        can_modify = item.kind in ("registry", "folder", "task")
        self.toggle_button.setEnabled(can_modify and self._task is None)
        self.remove_button.setEnabled(item.kind in ("registry", "folder") and self._task is None)
        if item.kind == "registry" and item.hive == "HKLM":
            self.remove_button.setToolTip("Changing HKLM entries requires running as administrator")
        else:
            self.remove_button.setToolTip("")

    def _ask_confirm(self, question: str, item: StartupItem) -> bool:
        answer = QMessageBox.question(
            self,
            "Startup change",
            f"{question}\n\nYou can undo this from the toolbar.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
