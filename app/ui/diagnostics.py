from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.diagnostics import DiagnosticsReport, DiagnosticsService
from app.i18n import tr

from .components import attach_empty_hint
from .format import size as fmt_size
from .tasks import Task
from .theme import DANGER, OK, WARN

DISK_COLUMN_KEYS = (
    "diag_col_name",
    "diag_col_type",
    "diag_col_size",
    "diag_col_temp",
    "diag_col_wear",
    "diag_col_hours",
    "diag_col_health",
)
EVENT_COLUMN_KEYS = (
    "diag_col_time",
    "diag_col_level",
    "diag_col_source",
    "diag_col_id",
    "diag_col_message",
)

LOG_CHOICES = ("System", "Application")
LEVEL_CHOICES = ((1, 2), (1, 2, 3), (1, 2, 3, 4))

_LOG_KEYS = {"System": "diag_log_system", "Application": "diag_log_application"}
_LEVEL_KEYS = {
    (1, 2): "diag_level_errors",
    (1, 2, 3): "diag_level_warnings",
    (1, 2, 3, 4): "diag_level_all",
}
_EVENT_LEVEL_KEYS = {
    "critical": "diag_lvl_critical",
    "error": "diag_lvl_error",
    "warning": "diag_lvl_warning",
    "information": "diag_lvl_information",
    "verbose": "diag_lvl_verbose",
}
_EVENT_LEVEL_COLORS = {
    "critical": DANGER,
    "error": DANGER,
    "warning": WARN,
}
_HEALTH_KEYS = {
    "healthy": "diag_health_healthy",
    "warning": "diag_health_warning",
    "unhealthy": "diag_health_unhealthy",
    "unknown": "diag_health_unknown",
}
_HEALTH_COLORS = {
    "healthy": OK,
    "warning": WARN,
    "unhealthy": DANGER,
}

_MISSING = "—"


def _event_level_text(name: str, level: int) -> str:
    key = _EVENT_LEVEL_KEYS.get(name)
    return tr(key) if key else str(level)


def _health_text(health: str) -> str:
    return tr(_HEALTH_KEYS.get(health, "diag_health_unknown"))


def _percent(value: int | None) -> str:
    return _MISSING if value is None else f"{value}%"


def _hours(value: int | None) -> str:
    return _MISSING if value is None else f"{value} h"


def _temperature(value: int | None) -> str:
    return _MISSING if value is None else f"{value}°C"


class DiagnosticsPage(QWidget):
    def __init__(
        self, service: DiagnosticsService | None = None, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or DiagnosticsService()
        self._task: Task | None = None
        self._report: DiagnosticsReport | None = None
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("diag_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("diag_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_button = QPushButton(tr("diag_refresh"))
        self.refresh_button.setProperty("primary", True)
        self.refresh_button.clicked.connect(self.start_load)
        toolbar.addWidget(self.refresh_button)
        self.status_label = QLabel(tr("diag_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Vertical)

        self.disk_card, self.disk_title, self.disk_table = self._make_table(
            "diag_disk_title", DISK_COLUMN_KEYS, "diag_disk_empty"
        )
        splitter.addWidget(self.disk_card)

        evt_card = QFrame()
        evt_card.setObjectName("card")
        evt_layout = QVBoxLayout(evt_card)
        evt_layout.setContentsMargins(18, 14, 18, 14)
        evt_layout.setSpacing(8)

        evt_head = QHBoxLayout()
        evt_head.setSpacing(8)
        evt_title = QLabel(tr("diag_evt_title").upper())
        evt_title.setObjectName("cardTitle")
        evt_head.addWidget(evt_title)
        evt_head.addStretch(1)

        self.log_combo = QComboBox()
        for log in LOG_CHOICES:
            self.log_combo.addItem(tr(_LOG_KEYS[log]), log)
        evt_head.addWidget(self.log_combo)

        self.level_combo = QComboBox()
        for levels in LEVEL_CHOICES:
            self.level_combo.addItem(tr(_LEVEL_KEYS[levels]), levels)
        evt_head.addWidget(self.level_combo)

        self.events_button = QPushButton(tr("diag_evt_btn"))
        self.events_button.setProperty("secondary", True)
        self.events_button.clicked.connect(self.start_load)
        evt_head.addWidget(self.events_button)
        evt_layout.addLayout(evt_head)

        self.events_table = self._build_table(EVENT_COLUMN_KEYS, "diag_evt_none")
        evt_layout.addWidget(self.events_table, 1)

        self.events_title = evt_title
        splitter.addWidget(evt_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        layout.addWidget(splitter, 1)

    # ---------- table helpers ----------

    def _build_table(self, column_keys: tuple[str, ...], hint: str) -> QTableWidget:
        table = QTableWidget(0, len(column_keys))
        attach_empty_hint(table, hint)
        table.setHorizontalHeaderLabels([tr(k) for k in column_keys])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(120)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in range(len(column_keys) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(column_keys) - 1, QHeaderView.ResizeMode.Stretch)
        return table

    def _make_table(self, title_key: str, column_keys: tuple[str, ...], hint: str):
        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(18, 14, 18, 14)
        body.setSpacing(8)

        title = QLabel(tr(title_key).upper())
        title.setObjectName("cardTitle")
        body.addWidget(title)

        table = self._build_table(column_keys, hint)
        body.addWidget(table, 1)
        return card, title, table

    # ---------- loading ----------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded and self._task is None:
            self.start_load()

    def start_load(self) -> None:
        if self._task is not None:
            return
        log_name = self.log_combo.currentData() or "System"
        levels = tuple(self.level_combo.currentData() or (1, 2))
        self.status_label.setText(tr("diag_loading"))
        self._set_busy(True)
        self._task = Task(lambda: self._service.report(log_name, levels), parent=self)
        self._task.done.connect(self._apply_report)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _apply_report(self, report: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(report, DiagnosticsReport):
            self.status_label.setText(tr("diag_failed", msg=report))
            return
        self._report = report
        self._loaded = True
        self._render()
        if report.errors:
            self.status_label.setText(tr("diag_partial", count=len(report.errors)))
        else:
            self.status_label.setText(tr("diag_loaded"))

    def _on_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("diag_failed", msg=message))

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.events_button.setEnabled(not busy)
        self.log_combo.setEnabled(not busy)
        self.level_combo.setEnabled(not busy)

    # ---------- rendering ----------

    def _render(self) -> None:
        if self._report is None:
            return
        self._render_disks(self._report)
        self._render_events(self._report)

    def _render_disks(self, report: DiagnosticsReport) -> None:
        disks = report.disks
        self.disk_table.setRowCount(len(disks))
        for row, disk in enumerate(disks):
            values = (
                disk.name,
                disk.media,
                fmt_size(disk.size_bytes) if disk.size_bytes else _MISSING,
                _temperature(disk.temperature_c),
                _percent(disk.wear_percent),
                _hours(disk.power_on_hours),
                _health_text(disk.health),
            )
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                if col == len(values) - 1:
                    color = _HEALTH_COLORS.get(disk.health)
                    if color:
                        item.setForeground(QColor(color))
                self.disk_table.setItem(row, col, item)

    def _render_events(self, report: DiagnosticsReport) -> None:
        events = report.events
        self.events_table.setRowCount(len(events))
        for row, event in enumerate(events):
            name = _event_level_text(event.level_name, event.level)
            cells = (
                QTableWidgetItem(event.time),
                QTableWidgetItem(name),
                QTableWidgetItem(event.source),
                QTableWidgetItem(str(event.event_id) if event.event_id else ""),
                QTableWidgetItem(event.message),
            )
            color = _EVENT_LEVEL_COLORS.get(event.level_name)
            if color is not None:
                cells[1].setForeground(QColor(color))
                cells[0].setForeground(QColor(color))
            cells[4].setToolTip(event.message)
            for col, item in enumerate(cells):
                self.events_table.setItem(row, col, item)

    # ---------- i18n ----------

    def retranslate(self) -> None:
        self._title.setText(tr("diag_title"))
        self._desc.setText(tr("diag_desc"))
        self.refresh_button.setText(tr("diag_refresh"))
        self.disk_title.setText(tr("diag_disk_title").upper())
        self.events_title.setText(tr("diag_evt_title").upper())
        self.events_button.setText(tr("diag_evt_btn"))
        for index, log in enumerate(LOG_CHOICES):
            self.log_combo.setItemText(index, tr(_LOG_KEYS[log]))
        for index, levels in enumerate(LEVEL_CHOICES):
            self.level_combo.setItemText(index, tr(_LEVEL_KEYS[levels]))
        self.disk_table.setHorizontalHeaderLabels([tr(k) for k in DISK_COLUMN_KEYS])
        self.events_table.setHorizontalHeaderLabels([tr(k) for k in EVENT_COLUMN_KEYS])
        if self._report is not None:
            self._render()
