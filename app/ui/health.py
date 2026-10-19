from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
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

from app.health import Finding, FixReport, HealthReport, HealthService
from app.i18n import tr
from app.reports import ReportError, export_health, timestamp_name

from .activity import ActivityLog
from .activity import record as log_action
from .components import ScoreRing, attach_empty_hint
from .tasks import Task
from .theme import ACCENT, DANGER, OK, TEXT_DIM, WARN

HEALTH_COLUMN_KEYS = (
    "health_col_category", "health_col_severity", "health_col_issue",
    "health_col_details", "health_col_action",
)

SEVERITY_COLOR = {
    "critical": DANGER,
    "warning": WARN,
    "info": ACCENT,
    "ok": OK,
}

SEVERITY_TR = {
    "critical": "health_sev_critical",
    "warning": "health_sev_warning",
    "info": "health_sev_info",
    "ok": "health_sev_ok",
}

# Findings that only make sense as a jump to the page that handles them.
_GO_PAGES = {
    "disk": "cleaner",
    "memory": "monitor", "memory_missing": "monitor",
    "cpu_load": "monitor", "thermal": "monitor",
    "thermal_missing": "monitor", "thermal_gpu": "monitor", "gpu_load": "monitor",
}


def action_for(finding) -> tuple[str, str]:
    """('fix', '') when HealthService.fix_finding can apply it, ('go', page) for navigation."""
    if finding.severity == "ok":
        return ("", "")
    if finding.fixable or finding.id in ("power", "startup"):
        return ("fix", "")
    page = _GO_PAGES.get(finding.id.split(":", 1)[0] if finding.id.startswith("disk:") else finding.id)
    if page:
        return ("go", page)
    return ("", "")


def grade_text(grade: str) -> str:
    key = f"grade_{grade.lower()}"
    text = tr(key)
    return grade if text == key else text


_CATEGORY_KEYS = {
    "Memory": "fc_memory", "Thermal": "fc_thermal", "CPU": "fc_cpu", "Storage": "fc_storage",
    "Startup": "fc_startup", "Power": "fc_power", "Cleanup": "fc_cleanup", "GPU": "fc_gpu",
}
_TITLE_RULES = (
    (r"RAM almost full", "ft_ram_full"), (r"High RAM usage", "ft_ram_high"), (r"RAM usage healthy", "ft_ram_ok"),
    (r"Very high CPU temperature", "ft_temp_crit"), (r"High CPU temperature", "ft_temp_high"),
    (r"Very high GPU temperature", "ft_gpu_temp_crit"), (r"High GPU temperature", "ft_gpu_temp_high"),
    (r"Temperatures normal", "ft_temp_ok"), (r"CPU load is high right now", "ft_cpu_high"),
    (r"GPU load is high right now", "ft_gpu_high"),
    (r"(?P<mount>.+) nearly full", "ft_disk_full"), (r"(?P<mount>.+) running low", "ft_disk_low"),
    (r"(?P<n>\d+) heavy startup apps", "ft_startup_heavy"), (r"Power saver plan is active", "ft_power_saver"),
    (r"Lots of temporary files", "ft_junk_crit"), (r"Temporary files found", "ft_junk_warn"),
    (r"Little temporary clutter", "ft_junk_ok"),
)
_DETAIL_RULES = (
    (r"(?P<n>\d+)% of RAM in use — close heavy apps", "fd_ram_full"), (r"(?P<n>\d+)% of RAM in use", "fd_ram_high"),
    (r"(?P<n>\d+)% used — free space now", "fd_disk_full"), (r"(?P<n>\d+)% used", "fd_used"),
    (r"(?P<n>\d+)C — check cooling / dust", "fd_temp_crit"), (r"(?P<n>\d+)C", "fd_temp"),
    (r"(?P<n>\d+)C — GPU is close to throttling", "fd_gpu_temp_crit"),
    (r"(?P<n>\d+)C — normal while gaming, not at idle", "fd_gpu_temp"),
    (r"(?P<n>\d+)% — may be a background task", "fd_cpu_high"),
    (r"(?P<n>\d+)% — normal in games, check temperatures if constant", "fd_gpu_high"),
    (r"They slow down logon and consume RAM", "fd_startup_warn"),
    (r"Consider disabling the ones you do not need", "fd_startup_info"),
    (r"Switch to Balanced or the Gaming profile for more performance", "fd_power_saver"),
    (r"(?P<gb>[\d.]+) GB across (?P<n>\d+) locations", "fd_junk"), (r"(?P<n>\d+) MB found", "fd_junk_ok"),
)


def _localize(rules, text: str) -> str:
    import re

    for pattern, key in rules:
        m = re.fullmatch(pattern, text)
        if m:
            return tr(key, **m.groupdict())
    return text


def localize_finding(finding) -> tuple[str, str, str]:
    """The health service produces English text; translate known findings, keep unknown ones as is."""
    key = _CATEGORY_KEYS.get(finding.category)
    return (
        tr(key) if key else finding.category,
        _localize(_TITLE_RULES, finding.title),
        _localize(_DETAIL_RULES, finding.detail),
    )


class HealthPage(QWidget):
    navigate = Signal(str)

    def __init__(self, service: HealthService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or HealthService()
        self._task: Task | None = None
        self._report: HealthReport | None = None
        self._action_buttons: list[QPushButton] = []
        self._action_cells: list[QWidget] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("health_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("health_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        score_card = QFrame()
        score_card.setObjectName("hero")
        score_layout = QHBoxLayout(score_card)
        score_layout.setContentsMargins(18, 16, 18, 16)
        score_layout.setSpacing(20)

        self.score_label = QLabel("—")
        self.score_label.setObjectName("scoreValue")
        self.ring = ScoreRing(self.score_label)
        score_layout.addWidget(self.ring)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.grade_label = QLabel(tr("health_not_scanned"))
        self.grade_label.setObjectName("cardValue")
        text_box.addWidget(self.grade_label)
        self.detail_label = QLabel(tr("health_grade_hint"))
        self.detail_label.setObjectName("cardSub")
        self.detail_label.setWordWrap(True)
        text_box.addWidget(self.detail_label)
        score_layout.addLayout(text_box, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        self.scan_button = QPushButton(tr("health_scan_btn"))
        self.scan_button.setProperty("primary", True)
        self.scan_button.clicked.connect(self.start_scan)
        buttons.addWidget(self.scan_button)
        self.fix_button = QPushButton(tr("health_fix_btn"))
        self.fix_button.setProperty("secondary", True)
        self.fix_button.setEnabled(False)
        self.fix_button.clicked.connect(self.start_fix)
        buttons.addWidget(self.fix_button)
        self.export_button = QPushButton(tr("health_export_btn"))
        self.export_button.setProperty("secondary", True)
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_report)
        buttons.addWidget(self.export_button)
        score_layout.addLayout(buttons)
        layout.addWidget(score_card)

        self.findings_table = QTableWidget(0, len(HEALTH_COLUMN_KEYS))
        attach_empty_hint(self.findings_table, "empty_health")
        self.findings_table.setHorizontalHeaderLabels([tr(k) for k in HEALTH_COLUMN_KEYS])
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.setShowGrid(False)
        self.findings_table.setAlternatingRowColors(True)
        self.findings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.findings_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.findings_table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.findings_table, 1)

        self.status_label = QLabel(tr("health_idle"))
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

    @property
    def service(self) -> HealthService:
        return self._service

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("health_title"))
        self._desc.setText(tr("health_desc"))
        self.scan_button.setText(tr("health_scan_btn"))
        self.fix_button.setText(tr("health_fix_btn"))
        self.export_button.setText(tr("health_export_btn"))
        self.findings_table.setHorizontalHeaderLabels([tr(k) for k in HEALTH_COLUMN_KEYS])
        for row in range(self.findings_table.rowCount()):
            self._retranslate_finding_row(row)
        if getattr(self, "_report", None) is not None:
            self._render_report(self._report)

    def _retranslate_finding_row(self, row: int) -> None:
        item = self.findings_table.item(row, 1)
        if item is None:
            return
        severity = item.data(Qt.ItemDataRole.UserRole)
        key = SEVERITY_TR.get(severity)
        if key:
            item.setText(tr(key))

    # ---------- scan ----------

    def start_scan(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("health_scanning"))
        self._set_busy(True)
        self._task = Task(self._service.scan, parent=self)
        self._task.done.connect(self._after_scan)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_scan(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, HealthReport):
            self.status_label.setText(tr("health_scan_failed", msg=result))
            return
        self._report = result
        self._render_report(result)
        ActivityLog.instance().health = (result.score, str(result.grade))
        log_action(tr("act_health"), f"{result.score}/100")

    def _render_report(self, report: HealthReport) -> None:
        self.score_label.setText(str(report.score))
        self.ring.set_value(report.score)
        self.grade_label.setText(grade_text(report.grade))
        issues = sum(1 for f in report.findings if f.severity != "ok")
        self.detail_label.setText(
            tr("health_detail", issues=issues, size=f"{report.junk_bytes / 1024**3:.1f}")
        )

        self.findings_table.setSortingEnabled(False)
        self._clear_action_cells()
        self.findings_table.setRowCount(len(report.findings))
        for row, finding in enumerate(report.findings):
            self._set_finding_row(row, finding)
        self.findings_table.setSortingEnabled(True)

        self.fix_button.setEnabled(report.fixable_count > 0)
        self.export_button.setEnabled(True)
        self.export_button.setEnabled(True)
        if report.fixable_count:
            self.status_label.setText(tr("health_fix_available", count=report.fixable_count))
        else:
            self.status_label.setText(tr("health_nothing"))

    def _set_finding_row(self, row: int, finding: Finding) -> None:
        cat_text, title_text, detail_text = localize_finding(finding)
        category = QTableWidgetItem(cat_text)
        severity_item = QTableWidgetItem(tr(SEVERITY_TR.get(finding.severity, "health_sev_info")))
        severity_item.setData(Qt.ItemDataRole.UserRole, finding.severity)
        severity_item.setForeground(QColor(SEVERITY_COLOR.get(finding.severity, TEXT_DIM)))
        issue = QTableWidgetItem(title_text)
        detail = QTableWidgetItem(detail_text)
        detail.setToolTip(detail_text)
        self.findings_table.setItem(row, 0, category)
        self.findings_table.setItem(row, 1, severity_item)
        self.findings_table.setItem(row, 2, issue)
        self.findings_table.setItem(row, 3, detail)
        self._set_action_cell(row, finding, title_text)

    def _clear_action_cells(self) -> None:
        """Detach and delete the row action widgets.

        Qt keeps the cell-widget pointer inside the table, and neither a row
        resize nor a plain ``setCellWidget`` deletes the old widget, so the table
        must be told to forget every cell before we can safely delete them
        (otherwise restyling hits a dangling pointer).
        """
        for row in range(self.findings_table.rowCount()):
            self.findings_table.setCellWidget(row, 4, None)
        for cell in self._action_cells:
            cell.hide()
            cell.deleteLater()
        self._action_cells = []
        self._action_buttons = []

    def _set_action_cell(self, row: int, finding: Finding, title_text: str) -> None:
        kind, page = action_for(finding)
        self.findings_table.setItem(row, 4, QTableWidgetItem(""))
        if not kind:
            return
        button = QPushButton(tr("health_btn_fix") if kind == "fix" else tr("health_btn_go"))
        button.setProperty("secondary", True)
        button.setFixedHeight(26)
        if kind == "fix":
            button.setToolTip(finding.fix_hint or tr("health_btn_fix"))
            button.clicked.connect(
                lambda _checked=False, f=finding, title=title_text: self.start_fix_one(f, title)
            )
        else:
            button.clicked.connect(
                lambda _checked=False, target=page: self.navigate.emit(target)
            )
        host = QWidget()
        host.setObjectName("healthActionCell")
        row_layout = QHBoxLayout(host)
        row_layout.setContentsMargins(0, 0, 8, 0)
        row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        row_layout.addWidget(button)
        self.findings_table.setCellWidget(row, 4, host)
        self._action_cells.append(host)
        self._action_buttons.append(button)

    # ---------- fix ----------

    def start_fix(self) -> None:
        if self._task is not None or self._report is None:
            return
        if not self._report.fixable_count:
            return
        if not self._ask_confirm(
            tr("health_fix_confirm_title"),
            tr("health_fix_confirm_msg"),
        ):
            return
        self.status_label.setText(tr("health_fixing"))
        self._set_busy(True)
        self._task = Task(self._service.fix_all, parent=self)
        self._task.done.connect(self._after_fix)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def start_fix_one(self, finding: Finding, title: str = "") -> None:
        """Fix just the finding the user picked in its row (after a Yes/No confirmation)."""
        if self._task is not None:
            return
        if not self._ask_confirm(
            tr("health_fix_one_title"),
            tr("health_fix_one_msg", issue=title or finding.title),
        ):
            return
        self.status_label.setText(tr("health_fixing"))
        self._set_busy(True)
        self._task = Task(lambda: self._service.fix_finding(finding), parent=self)
        self._task.done.connect(self._after_fix)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_fix(self, result: object) -> None:
        self._task = None
        if not isinstance(result, FixReport):
            self._set_busy(False)
            self.status_label.setText(tr("health_fix_failed", msg=result))
            return
        if result.reclaimed_bytes or result.files_deleted:
            message = tr(
                "health_freed",
                size=result.reclaimed_bytes / 1024**3,
                files=result.files_deleted,
            )
        elif result.applied:
            message = tr("health_fix_one_done", what=", ".join(result.applied))
        else:
            message = tr("health_nothing")
        if result.errors:
            message += " · " + tr("health_errors_n", count=len(result.errors))
        self.status_label.setText(message)
        self._set_busy(False)
        self.start_scan()

    def _ask_confirm(self, title: str, text: str) -> bool:
        answer = QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    # ---------- export ----------

    def export_report(self) -> None:
        if self._report is None:
            self.status_label.setText(tr("exp_nothing"))
            return
        path = self._ask_save_path(timestamp_name("health_report", "csv"))
        if not path:
            return
        try:
            target = export_health(
                self._report,
                path,
                localize=localize_finding,
                header=(
                    tr("exp_health_category"), tr("exp_health_severity"),
                    tr("exp_health_issue"), tr("exp_health_detail"), tr("exp_health_fixable"),
                ),
            )
        except ReportError as e:
            self.status_label.setText(tr("exp_failed", msg=str(e)))
            return
        self.status_label.setText(tr("exp_done", path=str(target)))

    def _ask_save_path(self, default_name: str) -> str:
        path, selected = QFileDialog.getSaveFileName(
            self, tr("exp_dialog_title"), default_name, tr("exp_filter")
        )
        if not path:
            return ""
        if not Path(path).suffix:
            fmt = "json" if "json" in (selected or "").lower() else "csv"
            path = f"{path}.{fmt}"
        return path

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.fix_button.setEnabled(not busy and self._report is not None and self._report.fixable_count > 0)
        self.export_button.setEnabled(not busy and self._report is not None)
        for button in self._action_buttons:
            button.setEnabled(not busy)
