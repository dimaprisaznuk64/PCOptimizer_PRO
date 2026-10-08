from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.cleaner import CleanerService, CleanOutcome, CleanTarget, ScanResult

from .format import size
from .tasks import Task

COLUMNS = ("Target", "Category", "Files", "Size", "Status")


class CleanerPage(QWidget):
    def __init__(self, service: CleanerService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or CleanerService()
        self._scans: dict[str, ScanResult] = {}
        self._outcomes: dict[str, CleanOutcome] = {}
        self._task: Task | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Cleaner")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("Temp files, browser caches, shader caches and recycle bin — sizes are previewed before deleting")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.scan_button = QPushButton("Scan")
        self.scan_button.setProperty("secondary", True)
        self.scan_button.clicked.connect(self.start_scan)
        toolbar.addWidget(self.scan_button)

        self.clean_button = QPushButton("Clean selected")
        self.clean_button.setProperty("danger", True)
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(self.start_clean)
        toolbar.addWidget(self.clean_button)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self.summary = QLabel("Run a scan to preview reclaimable space")
        self.summary.setObjectName("cardRow")
        layout.addWidget(self.summary)

        note = QLabel("Locked / in-use files are skipped automatically. Deletion of temp and cache files is permanent.")
        note.setObjectName("cardSub")
        note.setWordWrap(True)
        layout.addWidget(note)

        self._targets: list[CleanTarget] = self._service.targets
        self._render_table()

    @property
    def service(self) -> CleanerService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._scans and self._task is None:
            self.start_scan()

    def start_scan(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Scanning…")
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)
        self._task = Task(self._service.scan_all, parent=self)
        self._task.done.connect(self._apply_scan)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_scan(self, results: object) -> None:
        self._task = None
        self.scan_button.setEnabled(True)
        if not isinstance(results, list):
            self.status_label.setText(f"Scan failed: {results}")
            return
        by_id = {r.target_id: r for r in results}
        self._scans.update(by_id)
        self._render_table()
        total = sum(r.bytes for r in self._scans.values())
        self.status_label.setText(f"Scan complete · {size(total)} reclaimable")
        self.clean_button.setEnabled(any(r.bytes > 0 for r in self._scans.values()))

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self.scan_button.setEnabled(True)
        self.clean_button.setEnabled(bool(self._scans))
        self.status_label.setText(f"Failed: {message}")

    def start_clean(self) -> None:
        if self._task is not None:
            return
        selected = self._selected_targets()
        if not selected:
            return
        total = sum(self._scans.get(t.id).bytes for t in selected if self._scans.get(t.id))
        if not self._ask_confirm(len(selected), total):
            return
        self.status_label.setText("Cleaning…")
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)

        def run() -> list[CleanOutcome]:
            outcomes = []
            for target in selected:
                scan = self._scans.get(target.id)
                outcomes.append(self._service.clean(target, known_bytes=scan.bytes if scan else 0))
            return outcomes

        self._task = Task(run, parent=self)
        self._task.done.connect(self._apply_clean)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_clean(self, outcomes: object) -> None:
        self._task = None
        self.scan_button.setEnabled(True)
        self.clean_button.setEnabled(True)
        if not isinstance(outcomes, list):
            self.status_label.setText(f"Clean failed: {outcomes}")
            return
        for outcome in outcomes:
            self._outcomes[outcome.target_id] = outcome
        freed = sum(o.freed_bytes for o in outcomes)
        skipped = sum(o.files_skipped for o in outcomes)
        errors = "; ".join(dict.fromkeys(o.error for o in outcomes if o.error))
        self._render_table()
        message = f"Freed {size(freed)}"
        if skipped:
            message += f" · {skipped} files skipped (in use)"
        if errors:
            message += f" · {errors}"
        self.status_label.setText(message)

    def _selected_targets(self) -> list[CleanTarget]:
        selected: list[CleanTarget] = []
        for row, target in enumerate(self._targets):
            item = self.table.item(row, 0)
            if item is not None and item.checkState() == Qt.CheckState.Checked:
                selected.append(target)
        return selected

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() == 0:
            self._update_summary()

    def _update_summary(self) -> None:
        selected = self._selected_targets()
        total = sum(self._scans[t.id].bytes for t in selected if t.id in self._scans)
        self.summary.setText(
            f"Selected {len(selected)} of {len(self._targets)} targets · {size(total)} will be freed"
        )

    def _render_table(self) -> None:
        self._targets = self._service.targets
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._targets))
        for row, target in enumerate(self._targets):
            scan = self._scans.get(target.id)
            outcome = self._outcomes.get(target.id)

            name_item = QTableWidgetItem(target.name)
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            name_item.setCheckState(Qt.CheckState.Checked)
            if scan and scan.error:
                name_item.setToolTip(scan.error)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(target.category))
            self.table.setItem(row, 2, QTableWidgetItem(str(scan.files) if scan else "—"))
            self.table.setItem(row, 3, QTableWidgetItem(size(scan.bytes) if scan else "—"))
            if outcome:
                status = f"freed {size(outcome.freed_bytes)}"
                if outcome.files_skipped:
                    status += f" · {outcome.files_skipped} skipped"
                if outcome.error:
                    status = outcome.error
            elif scan:
                status = "ready"
            else:
                status = "not scanned"
            self.table.setItem(row, 4, QTableWidgetItem(status))
        self.table.blockSignals(False)
        self._update_summary()

    def _ask_confirm(self, targets: int, total_bytes: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Clean selected",
            f"Permanently delete files from {targets} targets ({size(total_bytes)})?\n"
            "In-use files will be skipped.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
