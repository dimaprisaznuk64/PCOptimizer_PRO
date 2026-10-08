from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
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

from .tasks import Task

HEALTH_COLUMNS = ("Category", "Severity", "Issue", "Details")

SEVERITY_COLOR = {
    "critical": "#ff5c5c",
    "warning": "#ffb03a",
    "info": "#4f8cff",
    "ok": "#39d98a",
}


class HealthPage(QWidget):
    def __init__(self, service: HealthService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or HealthService()
        self._task: Task | None = None
        self._report: HealthReport | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("PC Health")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "One-click scan of your system. FIX ALL only removes temporary files and caches — "
            "every other recommendation is advisory and reversible."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        score_card = QFrame()
        score_card.setObjectName("card")
        score_layout = QHBoxLayout(score_card)
        score_layout.setContentsMargins(18, 16, 18, 16)
        score_layout.setSpacing(20)

        self.score_label = QLabel("—")
        self.score_label.setObjectName("scoreValue")
        self.score_label.setMinimumWidth(120)
        score_layout.addWidget(self.score_label)

        text_box = QVBoxLayout()
        text_box.setSpacing(2)
        self.grade_label = QLabel("Not scanned yet")
        self.grade_label.setObjectName("cardValue")
        text_box.addWidget(self.grade_label)
        self.detail_label = QLabel("Run SCAN MY PC to score this machine.")
        self.detail_label.setObjectName("cardSub")
        self.detail_label.setWordWrap(True)
        text_box.addWidget(self.detail_label)
        score_layout.addLayout(text_box, 1)

        buttons = QVBoxLayout()
        buttons.setSpacing(6)
        self.scan_button = QPushButton("SCAN MY PC")
        self.scan_button.clicked.connect(self.start_scan)
        buttons.addWidget(self.scan_button)
        self.fix_button = QPushButton("FIX ALL")
        self.fix_button.setProperty("secondary", True)
        self.fix_button.setEnabled(False)
        self.fix_button.clicked.connect(self.start_fix)
        buttons.addWidget(self.fix_button)
        score_layout.addLayout(buttons)
        layout.addWidget(score_card)

        self.findings_table = QTableWidget(0, len(HEALTH_COLUMNS))
        self.findings_table.setHorizontalHeaderLabels(HEALTH_COLUMNS)
        self.findings_table.verticalHeader().setVisible(False)
        self.findings_table.setShowGrid(False)
        self.findings_table.setAlternatingRowColors(True)
        self.findings_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.findings_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.findings_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.findings_table, 1)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

    @property
    def service(self) -> HealthService:
        return self._service

    # ---------- scan ----------

    def start_scan(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Scanning your PC…")
        self._set_busy(True)
        self._task = Task(self._service.scan, parent=self)
        self._task.done.connect(self._after_scan)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_scan(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, HealthReport):
            self.status_label.setText(f"Scan failed: {result}")
            return
        self._report = result
        self._render_report(result)

    def _render_report(self, report: HealthReport) -> None:
        self.score_label.setText(str(report.score))
        self.grade_label.setText(f"{report.grade}")
        issues = sum(1 for f in report.findings if f.severity != "ok")
        self.detail_label.setText(
            f"{issues} issue(s) found · temporary files: {report.junk_bytes / 1024**3:.2f} GB"
        )

        self.findings_table.setSortingEnabled(False)
        self.findings_table.setRowCount(len(report.findings))
        for row, finding in enumerate(report.findings):
            self._set_finding_row(row, finding)
        self.findings_table.setSortingEnabled(True)

        self.fix_button.setEnabled(report.fixable_count > 0)
        if report.fixable_count:
            self.status_label.setText(f"{report.fixable_count} automatic fix(es) available")
        else:
            self.status_label.setText("Nothing to fix automatically")

    def _set_finding_row(self, row: int, finding: Finding) -> None:
        category = QTableWidgetItem(finding.category)
        severity = QTableWidgetItem(finding.severity.upper())
        severity.setForeground(QColor(SEVERITY_COLOR.get(finding.severity, "#c9d1d9")))
        issue = QTableWidgetItem(finding.title)
        detail = QTableWidgetItem(finding.detail)
        detail.setToolTip(finding.fix_hint or finding.detail)
        self.findings_table.setItem(row, 0, category)
        self.findings_table.setItem(row, 1, severity)
        self.findings_table.setItem(row, 2, issue)
        self.findings_table.setItem(row, 3, detail)

    # ---------- fix ----------

    def start_fix(self) -> None:
        if self._task is not None or self._report is None:
            return
        if not self._report.fixable_count:
            return
        if not self._ask_confirm(
            "FIX ALL",
            "This removes temporary files and caches (the Recycle Bin is kept).\n\nContinue?",
        ):
            return
        self.status_label.setText("Applying fixes…")
        self._set_busy(True)
        self._task = Task(self._service.fix_all, parent=self)
        self._task.done.connect(self._after_fix)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_fix(self, result: object) -> None:
        self._task = None
        if not isinstance(result, FixReport):
            self._set_busy(False)
            self.status_label.setText(f"Fix failed: {result}")
            return
        reclaimed = result.reclaimed_bytes / 1024**3
        self.status_label.setText(
            f"Freed {reclaimed:.2f} GB ({result.files_deleted} files)"
            + (f" · {len(result.errors)} error(s)" if result.errors else "")
        )
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

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.fix_button.setEnabled(not busy and self._report is not None and self._report.fixable_count > 0)
