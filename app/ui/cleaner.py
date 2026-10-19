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
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.cleaner import CleanerService, CleanOutcome, CleanTarget, ScanResult
from app.i18n import tr

from .activity import outcome_level
from .activity import record as log_action
from .components import align_numeric_headers
from .format import size
from .tasks import Task

COLUMN_KEYS = ("clean_col_target", "clean_col_category", "clean_col_files", "clean_col_size", "clean_col_status")
COLUMNS = tuple(tr(k) for k in COLUMN_KEYS)


_TARGET_TR = {
    "User temp files": "clean_t_user_temp",
    "Windows temp files": "clean_t_win_temp",
    "Windows Update downloads": "clean_t_wu",
    "Google Chrome cache": "clean_t_chrome",
    "Microsoft Edge cache": "clean_t_edge",
    "Mozilla Firefox cache": "clean_t_firefox",
    "GPU shader caches": "clean_t_gpu",
    "Thumbnail cache": "clean_t_thumb",
    "Recycle Bin": "clean_t_bin",
    "Standby RAM cache": "clean_t_standby",
}
_CATEGORY_TR = {
    "System": "clean_c_system",
    "Browser": "clean_c_browser",
    "GPU": "clean_c_gpu",
    "Memory": "clean_c_memory",
}


def _loc(mapping: dict[str, str], text: str) -> str:
    key = mapping.get(text)
    return tr(key) if key else text


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

        title = QLabel(tr("clean_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("clean_desc"))
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        hero = QFrame()
        hero.setObjectName("hero")
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(22, 18, 22, 18)
        hero_row.setSpacing(12)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        self._hero_caption = QLabel(tr("clean_hero"))
        self._hero_caption.setObjectName("cardTitle")
        hero_text.addWidget(self._hero_caption)
        self.hero_value = QLabel("—")
        self.hero_value.setObjectName("heroValue")
        hero_text.addWidget(self.hero_value)
        self.status_label = QLabel(tr("clean_idle"))
        self.status_label.setObjectName("cardSub")
        hero_text.addWidget(self.status_label)
        hero_row.addLayout(hero_text, 1)

        self.scan_button = QPushButton(tr("clean_scan_btn"))
        self.scan_button.setProperty("primary", True)
        self.scan_button.clicked.connect(self.start_scan)
        hero_row.addWidget(self.scan_button, 0, Qt.AlignmentFlag.AlignVCenter)

        self.clean_button = QPushButton(tr("clean_clean_btn"))
        self.clean_button.setProperty("danger", True)
        self.clean_button.setEnabled(False)
        self.clean_button.clicked.connect(self.start_clean)
        hero_row.addWidget(self.clean_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(hero)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        align_numeric_headers(self.table, (2, 3))
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in range(1, len(COLUMNS)):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.table, 1)

        self.summary = QLabel(tr("clean_summary_init"))
        self.summary.setObjectName("cardRow")
        layout.addWidget(self.summary)

        self.note = QLabel(tr("clean_note"))
        self.note.setObjectName("cardSub")
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

        self._targets: list[CleanTarget] = self._service.targets
        self._render_table()

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("clean_title"))
        self._desc.setText(tr("clean_desc"))
        self._hero_caption.setText(tr("clean_hero"))
        self.scan_button.setText(tr("clean_scan_btn"))
        self.clean_button.setText(tr("clean_clean_btn"))
        self.note.setText(tr("clean_note"))
        self.table.setHorizontalHeaderLabels(tuple(tr(k) for k in COLUMN_KEYS))
        align_numeric_headers(self.table, (2, 3))
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
        self.status_label.setText(tr("clean_scanning"))
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
            self.status_label.setText(tr("clean_scan_failed", msg=results))
            return
        by_id = {r.target_id: r for r in results}
        self._scans.update(by_id)
        self._render_table()
        total = sum(r.bytes for r in self._scans.values())
        self.status_label.setText(tr("clean_scan_complete", size=size(total)))
        self.clean_button.setEnabled(any(r.bytes > 0 for r in self._scans.values()))

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self.scan_button.setEnabled(True)
        self.clean_button.setEnabled(bool(self._scans))
        self.status_label.setText(tr("clean_failed", msg=message))

    def start_clean(self) -> None:
        if self._task is not None:
            return
        selected = self._selected_targets()
        if not selected:
            return
        total = sum(self._scans.get(t.id).bytes for t in selected if self._scans.get(t.id))
        if not self._ask_confirm(len(selected), total):
            return
        self.status_label.setText(tr("clean_cleaning"))
        self.scan_button.setEnabled(False)
        self.clean_button.setEnabled(False)

        def run() -> list[CleanOutcome]:
            outcomes = []
            for target in selected:
                scan = self._scans.get(target.id)
                outcomes.append(self._service.clean(target, known_bytes=scan.bytes if scan else 0, known_files=scan.files if scan else 0))
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
            self.status_label.setText(tr("clean_clean_failed", msg=outcomes))
            return
        for outcome in outcomes:
            self._outcomes[outcome.target_id] = outcome
        freed = sum(o.freed_bytes for o in outcomes)
        skipped = sum(o.files_skipped for o in outcomes)
        errors = "; ".join(dict.fromkeys(o.error for o in outcomes if o.error))
        self._render_table()
        message = tr("clean_freed", size=size(freed))
        if skipped:
            message += " · " + tr("clean_skipped", count=skipped)
        if errors:
            message += f" · {errors}"
        self.status_label.setText(message)
        log_action(tr("act_clean"), size(freed), outcome_level(has_errors=bool(errors), achieved=bool(freed)))

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
            tr(
                "clean_selected",
                sel=len(selected),
                total=len(self._targets),
                size=size(total),
            )
        )

    def _render_table(self) -> None:
        self._targets = self._service.targets
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._targets))
        for row, target in enumerate(self._targets):
            scan = self._scans.get(target.id)
            outcome = self._outcomes.get(target.id)

            name_item = QTableWidgetItem(_loc(_TARGET_TR, target.name))
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            name_item.setCheckState(Qt.CheckState.Checked)
            if scan and scan.error:
                name_item.setToolTip(scan.error)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(_loc(_CATEGORY_TR, target.category)))
            num_item = QTableWidgetItem(str(scan.files) if scan else "—")
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 2, num_item)
            num_item = QTableWidgetItem(size(scan.bytes) if scan else "—")
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, 3, num_item)
            if outcome:
                status = tr("clean_status_freed", size=size(outcome.freed_bytes))
                if outcome.files_skipped:
                    status += " · " + tr("clean_status_skipped", count=outcome.files_skipped)
                if outcome.error:
                    status += " · " + outcome.error
            elif scan:
                status = tr("clean_status_ready")
            else:
                status = tr("clean_status_not_scanned")
            self.table.setItem(row, 4, QTableWidgetItem(status))
        self.table.blockSignals(False)
        self._update_summary()
        self._update_hero()

    def _update_hero(self) -> None:
        if not self._scans:
            self.hero_value.setText("—")
            return
        self.hero_value.setText(size(sum(r.bytes for r in self._scans.values())))

    def _ask_confirm(self, targets: int, total_bytes: int) -> bool:
        answer = QMessageBox.question(
            self,
            tr("clean_confirm_title"),
            tr("clean_confirm_msg", targets=targets, size=size(total_bytes)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes
