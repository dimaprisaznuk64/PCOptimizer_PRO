from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.cleaner import (
    CleanerSchedule,
    CleanerScheduler,
    CleanerService,
    CleanerWhitelist,
    CleanOutcome,
    CleanTarget,
    ScanResult,
    list_leftover_candidates,
    scan_large_files,
)
from app.i18n import tr

from .activity import outcome_level
from .activity import record as log_action
from .components import CardTitleLabel, align_numeric_headers
from .format import size
from .tasks import Task
from .theme import CARD_PADDING

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
    "Windows Error Reporting cache": "clean_t_wer",
    "Crash dumps": "clean_t_crash",
    "pip cache": "clean_t_pip",
    "npm cache": "clean_t_npm",
    "Recycle Bin": "clean_t_bin",
    "Standby RAM cache": "clean_t_standby",
}
_CATEGORY_TR = {
    "System": "clean_c_system",
    "Browser": "clean_c_browser",
    "GPU": "clean_c_gpu",
    "Memory": "clean_c_memory",
    "Development": "clean_c_dev",
    "Leftovers": "clean_c_leftovers",
    "Large files": "clean_c_large",
}
_CADENCE_TR = {
    "daily": "clean_schedule_daily",
    "weekly": "clean_schedule_weekly",
    "monthly": "clean_schedule_monthly",
}


def _loc(mapping: dict[str, str], text: str) -> str:
    key = mapping.get(text)
    return tr(key) if key else text


class CleanerPage(QWidget):
    def __init__(
        self,
        service: CleanerService | None = None,
        parent: QWidget | None = None,
        *,
        whitelist: CleanerWhitelist | None = None,
        scheduler: CleanerScheduler | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or CleanerService()
        if whitelist is not None:
            self._service.whitelist = whitelist
        self._whitelist = self._service.whitelist
        self._scheduler = scheduler or CleanerScheduler()
        self._extra_targets: dict[str, CleanTarget] = {}
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

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.whitelist_button = QPushButton(tr("clean_whitelist_btn"))
        self.whitelist_button.setProperty("secondary", True)
        self.whitelist_button.clicked.connect(self.open_whitelist)
        tools.addWidget(self.whitelist_button)

        self.schedule_button = QPushButton(tr("clean_schedule_btn"))
        self.schedule_button.setProperty("secondary", True)
        self.schedule_button.clicked.connect(self.open_schedule)
        tools.addWidget(self.schedule_button)

        self.leftovers_button = QPushButton(tr("clean_leftovers_btn"))
        self.leftovers_button.setProperty("secondary", True)
        self.leftovers_button.clicked.connect(self.start_leftovers)
        tools.addWidget(self.leftovers_button)

        self.large_files_button = QPushButton(tr("clean_large_btn"))
        self.large_files_button.setProperty("secondary", True)
        self.large_files_button.clicked.connect(self.start_large_files)
        tools.addWidget(self.large_files_button)
        tools.addStretch(1)
        layout.addLayout(tools)

        hero = QFrame()
        hero.setObjectName("hero")
        hero_row = QHBoxLayout(hero)
        hero_row.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        hero_row.setSpacing(12)
        hero_text = QVBoxLayout()
        hero_text.setSpacing(2)
        self._hero_caption = CardTitleLabel(tr("clean_hero"))
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

        self._targets = self._all_targets()
        self._render_table()

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("clean_title"))
        self._desc.setText(tr("clean_desc"))
        self._hero_caption.setText(tr("clean_hero"))
        self.scan_button.setText(tr("clean_scan_btn"))
        self.clean_button.setText(tr("clean_clean_btn"))
        self.whitelist_button.setText(tr("clean_whitelist_btn"))
        self.schedule_button.setText(tr("clean_schedule_btn"))
        self.leftovers_button.setText(tr("clean_leftovers_btn"))
        self.large_files_button.setText(tr("clean_large_btn"))
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
        self._set_tools_enabled(True)
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

    def _all_targets(self) -> list[CleanTarget]:
        targets = list(self._service.targets)
        known = {target.id for target in targets}
        for target in self._extra_targets.values():
            if target.id not in known:
                targets.append(target)
                known.add(target.id)
        return targets

    def _render_table(self) -> None:
        self._targets = self._all_targets()
        self.table.blockSignals(True)
        self.table.setRowCount(len(self._targets))
        for row, target in enumerate(self._targets):
            scan = self._scans.get(target.id)
            outcome = self._outcomes.get(target.id)

            name_item = QTableWidgetItem(_loc(_TARGET_TR, target.name))
            name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = Qt.CheckState.Checked if target.selected_by_default else Qt.CheckState.Unchecked
            name_item.setCheckState(checked)
            tips: list[str] = []
            if target.min_age_days:
                tips.append(tr("clean_age", days=target.min_age_days))
            if target.note:
                tips.append(target.note)
            if scan and scan.error:
                tips.append(scan.error)
            if tips:
                name_item.setToolTip("\n".join(tips))
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(_loc(_CATEGORY_TR, target.category)))
            num_item = QTableWidgetItem(str(scan.files) if scan else "—")
            num_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if scan and scan.details:
                lines = [f"{size(detail.size)} · {detail.path}" for detail in scan.details]
                if scan.details_truncated:
                    lines.append(tr("clean_details_more", count=scan.files - len(scan.details)))
                num_item.setToolTip("\n".join(lines))
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

    def open_whitelist(self) -> None:
        dialog = _WhitelistDialog(self._whitelist, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        wanted = set(dialog.patterns)
        for pattern in tuple(self._whitelist.patterns):
            if pattern not in wanted:
                self._whitelist.remove(pattern)
        for pattern in dialog.patterns:
            self._whitelist.add(pattern)
        self.status_label.setText(tr("clean_whitelist_saved", count=len(dialog.patterns)))

    def open_schedule(self) -> None:
        dialog = _ScheduleDialog(self._scheduler.schedule, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        enabled, cadence = dialog.values()
        selected = self._selected_targets()
        target_ids = tuple(target.id for target in selected) or tuple(
            target.id for target in self._targets if target.selected_by_default
        )
        schedule = CleanerSchedule(
            enabled=enabled,
            cadence=cadence,
            target_ids=target_ids,
            last_run=self._scheduler.last_run,
        )
        self._scheduler.save(schedule)
        self.status_label.setText(
            tr(
                "clean_schedule_saved",
                cadence=tr(_CADENCE_TR.get(cadence, "clean_schedule_weekly")),
                count=len(target_ids),
            )
        )

    def start_leftovers(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("clean_leftovers_scanning"))
        self._set_tools_enabled(False)
        self._task = Task(self._load_leftovers, parent=self)
        self._task.done.connect(self._apply_leftovers)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _load_leftovers(self) -> list[CleanTarget]:
        return list(list_leftover_candidates())

    def _apply_leftovers(self, found: object) -> None:
        self._task = None
        self._set_tools_enabled(True)
        if not isinstance(found, list):
            self.status_label.setText(tr("clean_failed", msg=found))
            return
        added = 0
        for target in found:
            if not isinstance(target, CleanTarget) or target.id in {t.id for t in self._all_targets()}:
                continue
            self._extra_targets[target.id] = target
            added += 1
        if added:
            self._render_table()
        self.status_label.setText(tr("clean_leftovers_status", count=added))

    def start_large_files(self) -> None:
        if self._task is not None:
            return
        folder = QFileDialog.getExistingDirectory(self, tr("clean_large_dir_title"))
        if not folder:
            return
        self.status_label.setText(tr("clean_large_scanning"))
        self._set_tools_enabled(False)

        def run() -> tuple[int, int, str]:
            errors: list[str] = []
            files = scan_large_files(folder, 100 * 1024 * 1024, 200, errors=errors)
            total = sum(file.size for file in files)
            return len(files), total, "; ".join(errors)

        self._task = Task(run, parent=self)
        self._task.done.connect(self._apply_large_files)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_large_files(self, result: object) -> None:
        self._task = None
        self._set_tools_enabled(True)
        if not isinstance(result, tuple) or len(result) != 3:
            self.status_label.setText(tr("clean_failed", msg=result))
            return
        count, total, errors = result
        message = tr("clean_large_status", count=count, size=size(int(total)))
        if errors:
            message += f" · {errors}"
        self.status_label.setText(message)

    def _set_tools_enabled(self, enabled: bool) -> None:
        self.scan_button.setEnabled(enabled)
        self.whitelist_button.setEnabled(enabled)
        self.schedule_button.setEnabled(enabled)
        self.leftovers_button.setEnabled(enabled)
        self.large_files_button.setEnabled(enabled)


class _WhitelistDialog(QDialog):
    def __init__(self, whitelist: CleanerWhitelist, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("clean_whitelist_title"))
        self.patterns = list(whitelist.patterns)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        hint = QLabel(tr("clean_whitelist_hint"))
        hint.setWordWrap(True)
        hint.setObjectName("cardSub")
        layout.addWidget(hint)
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(tr("clean_whitelist_placeholder"))
        row.addWidget(self.input, 1)
        add = QPushButton(tr("clean_whitelist_add"))
        add.setProperty("secondary", True)
        add.clicked.connect(self._add)
        row.addWidget(add)
        remove = QPushButton(tr("clean_whitelist_remove"))
        remove.setProperty("secondary", True)
        remove.clicked.connect(self._remove)
        row.addWidget(remove)
        layout.addLayout(row)
        buttons = QHBoxLayout()
        save = QPushButton(tr("clean_whitelist_save"))
        save.setProperty("primary", True)
        save.clicked.connect(self.accept)
        cancel = QPushButton(tr("clean_cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        self._render()

    def _render(self) -> None:
        self.list.clear()
        if not self.patterns:
            self.list.addItem(tr("clean_whitelist_empty"))
        else:
            self.list.addItems(self.patterns)

    def _add(self) -> None:
        value = self.input.text().strip()
        if value and value not in self.patterns:
            self.patterns.append(value)
            self.input.clear()
            self._render()

    def _remove(self) -> None:
        current = self.list.currentItem()
        if current is None:
            return
        value = current.text()
        if value in self.patterns:
            self.patterns.remove(value)
        self._render()


class _ScheduleDialog(QDialog):
    def __init__(self, schedule: CleanerSchedule, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("clean_schedule_title"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(8)
        self.enabled = QCheckBox(tr("clean_schedule_enabled"))
        self.enabled.setChecked(schedule.enabled)
        layout.addWidget(self.enabled)
        self.combo = QComboBox()
        for key, label in _CADENCE_TR.items():
            self.combo.addItem(tr(label), key)
        index = self.combo.findData(schedule.cadence)
        self.combo.setCurrentIndex(max(0, index))
        layout.addWidget(self.combo)
        last = (
            tr("clean_schedule_never")
            if not schedule.last_run
            else time.strftime("%Y-%m-%d %H:%M", time.localtime(schedule.last_run))
        )
        layout.addWidget(QLabel(tr("clean_schedule_last", last=last)))
        buttons = QHBoxLayout()
        save = QPushButton(tr("clean_whitelist_save"))
        save.setProperty("primary", True)
        save.clicked.connect(self.accept)
        cancel = QPushButton(tr("clean_cancel"))
        cancel.clicked.connect(self.reject)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

    def values(self) -> tuple[bool, str]:
        return self.enabled.isChecked(), str(self.combo.currentData() or "weekly")
