"""Recent operations center: a searchable activity feed with export and quick jumps."""

from __future__ import annotations

import csv
import io
import json
import time
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.reports.service import ReportError, format_for_path, timestamp_name, write_report
from app.settings import data_root

from .activity import ActivityLog, Entry
from .components import CardPanel, MetricCard, attach_empty_hint
from .context_menu import TableContextMenu, copy_text
from .sidebar import NAV_KEYS
from .theme import DANGER, OK, PAGE_MARGINS, PAGE_SPACING, SPACING_SM, TEXT_DIM, WARN

LEVEL_ALL = "all"
LEVELS = (LEVEL_ALL, "ok", "warn", "error")
RANGES: tuple[tuple[str, float | None], ...] = (
    ("ops_range_all", None),
    ("ops_range_24h", 24 * 3600.0),
    ("ops_range_7d", 7 * 24 * 3600.0),
)
_COLUMN_KEYS = (
    "ops_col_time",
    "ops_col_level",
    "ops_col_operation",
    "ops_col_details",
    "ops_col_source",
)
_EXPORT_COLUMNS = ("Time", "Level", "Operation", "Details", "Source")
_LEVEL_COLORS = {"ok": OK, "warn": WARN, "error": DANGER}


def filter_operations(
    entries: Sequence[Entry],
    *,
    level: str = LEVEL_ALL,
    query: str = "",
    max_age_s: float | None = None,
    now: float | None = None,
) -> list[Entry]:
    """Pure filter used by the operations page (newest entries first)."""
    terms = query.strip().casefold().split()
    cutoff = None if max_age_s is None else (time.time() if now is None else now) - max_age_s
    result: list[Entry] = []
    for entry in entries:
        if level != LEVEL_ALL and entry.level != level:
            continue
        if cutoff is not None and entry.ts < cutoff:
            continue
        haystack = " ".join((entry.title, entry.detail, entry.source, entry.level)).casefold()
        if terms and not all(term in haystack for term in terms):
            continue
        result.append(entry)
    return result


def operations_records(entries: Sequence[Entry]) -> list[dict[str, str]]:
    return [
        {
            "time": datetime.fromtimestamp(entry.ts).isoformat(timespec="seconds"),
            "level": entry.level,
            "operation": entry.title,
            "details": entry.detail,
            "source": entry.source,
        }
        for entry in entries
    ]


def operations_to_csv(
    entries: Sequence[Entry], *, header: Sequence[str] | None = None
) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header or _EXPORT_COLUMNS)
    for record in operations_records(entries):
        writer.writerow([record[key] for key in ("time", "level", "operation", "details", "source")])
    return buffer.getvalue()


def operations_to_json(entries: Sequence[Entry]) -> str:
    return json.dumps(operations_records(entries), ensure_ascii=False, indent=2)


def _level_text(level: str) -> str:
    return tr(f"ops_level_{level}" if level in ("ok", "warn", "error") else "ops_level_all")


def _source_text(source: str) -> str:
    if not source:
        return "—"
    return tr(dict(NAV_KEYS).get(source, source))


class OperationsPage(QWidget):
    """Full activity history with filters, details, export and page navigation."""

    navigate = Signal(str)

    def __init__(self, log: ActivityLog | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._log = log or ActivityLog.instance()
        self._visible: list[Entry] = []
        self._selected_ts: float | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)

        self.title_label = QLabel(tr("ops_title"))
        self.title_label.setObjectName("pageTitle")
        layout.addWidget(self.title_label)
        self.desc_label = QLabel(tr("ops_desc"))
        self.desc_label.setObjectName("pageDesc")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)

        summary = QHBoxLayout()
        summary.setSpacing(SPACING_SM)
        self.cards: dict[str, MetricCard] = {}
        for level in ("all", "ok", "warn", "error"):
            color = _LEVEL_COLORS.get(level, TEXT_DIM)
            card = MetricCard(tr(f"ops_stat_{level}"), sparkline=False, bar=False, color=color)
            self.cards[level] = card
            summary.addWidget(card)
        layout.addLayout(summary)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACING_SM)
        self.search = QLineEdit()
        self.search.setPlaceholderText(tr("ops_search"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refresh)
        toolbar.addWidget(self.search, 2)

        self.level_combo = QComboBox()
        self.level_combo.addItems([tr(f"ops_filter_{level}") for level in LEVELS])
        self.level_combo.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.level_combo)

        self.range_combo = QComboBox()
        self.range_combo.addItems([tr(key) for key, _seconds in RANGES])
        self.range_combo.currentIndexChanged.connect(self._refresh)
        toolbar.addWidget(self.range_combo)

        self.open_button = QPushButton(tr("ops_open"))
        self.open_button.setProperty("secondary", True)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self.open_source)
        toolbar.addWidget(self.open_button)

        self.mark_button = QPushButton(tr("ops_mark_read"))
        self.mark_button.setProperty("secondary", True)
        self.mark_button.clicked.connect(self._log.mark_all_read)
        toolbar.addWidget(self.mark_button)

        self.export_button = QPushButton(tr("ops_export"))
        self.export_button.setProperty("secondary", True)
        self.export_button.clicked.connect(self.export_report)
        toolbar.addWidget(self.export_button)

        self.clear_button = QPushButton(tr("ops_clear"))
        self.clear_button.setProperty("secondary", True)
        self.clear_button.clicked.connect(self.clear_history)
        toolbar.addWidget(self.clear_button)
        layout.addLayout(toolbar)

        self.log_card = CardPanel(tr("ops_log_title"))
        layout.addWidget(self.log_card, 1)
        self.table = QTableWidget(0, len(_COLUMN_KEYS))
        self.table.setHorizontalHeaderLabels([tr(key) for key in _COLUMN_KEYS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.doubleClicked.connect(lambda: self.open_source())
        self._context_menu = TableContextMenu(self.table)
        self._context_menu.add(lambda: tr("ctx_open_page"), self._open_entry, enabled=self._can_open)
        self._context_menu.add(lambda: tr("ctx_mark_read"), self._mark_entry_read)
        self._context_menu.add(lambda: tr("ctx_copy_detail"), self._copy_entry_detail)
        self.log_card.body.addWidget(self.table)
        attach_empty_hint(self.table, "ops_empty")

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)

        self.detail_label = QLabel(tr("ops_detail_hint"))
        self.detail_label.setObjectName("cardSub")
        self.detail_label.setWordWrap(True)
        self.log_card.body.addWidget(self.detail_label)

        self.status_label = QLabel("")
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self._log.changed.connect(self._refresh)
        self._refresh()

    @property
    def log(self) -> ActivityLog:
        return self._log

    def _level_at(self, index: int) -> str:
        return LEVELS[max(0, min(index, len(LEVELS) - 1))]

    def _max_age(self) -> float | None:
        index = max(0, min(self.range_combo.currentIndex(), len(RANGES) - 1))
        return RANGES[index][1]

    def _selected_entry(self) -> Entry | None:
        row = self.table.currentRow()
        if 0 <= row < len(self._visible):
            return self._visible[row]
        return None

    def _entry_at(self, row: int) -> Entry | None:
        if 0 <= row < len(self._visible):
            return self._visible[row]
        return None

    def _can_open(self, row: int) -> bool:
        entry = self._entry_at(row)
        return entry is not None and entry.source in dict(NAV_KEYS)

    def _open_entry(self, row: int) -> None:
        entry = self._entry_at(row)
        if entry is None or entry.source not in dict(NAV_KEYS):
            return
        self.table.selectRow(row)
        self._log.mark_read(entry.ts)
        self.navigate.emit(entry.source)

    def _mark_entry_read(self, row: int) -> None:
        entry = self._entry_at(row)
        if entry is not None:
            self._log.mark_read(entry.ts)
            self._refresh()

    def _copy_entry_detail(self, row: int) -> None:
        entry = self._entry_at(row)
        if entry is not None:
            copy_text(f"{entry.title}\n{entry.detail}")

    def _refresh(self, *_args) -> None:
        all_entries = self._log.entries(limit=None)
        for level, card in self.cards.items():
            count = len(all_entries) if level == LEVEL_ALL else sum(1 for e in all_entries if e.level == level)
            card.update_metric(str(count))

        self._visible = filter_operations(
            all_entries,
            level=self._level_at(self.level_combo.currentIndex()),
            query=self.search.text(),
            max_age_s=self._max_age(),
        )
        self.table.setRowCount(0)
        for row, entry in enumerate(self._visible):
            self.table.insertRow(row)
            cells = (
                QTableWidgetItem(entry.time_text),
                QTableWidgetItem(_level_text(entry.level)),
                QTableWidgetItem(entry.title),
                QTableWidgetItem(entry.detail),
                QTableWidgetItem(_source_text(entry.source)),
            )
            cells[1].setForeground(QColor(_LEVEL_COLORS.get(entry.level, TEXT_DIM)))
            for column, cell in enumerate(cells):
                self.table.setItem(row, column, cell)
            if entry.ts == self._selected_ts:
                self.table.selectRow(row)
        self.status_label.setText(
            tr("ops_status", count=len(self._visible), total=len(all_entries))
        )
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        entry = self._selected_entry()
        if entry is None:
            self.detail_label.setText(tr("ops_detail_hint"))
            self.open_button.setEnabled(False)
            self._selected_ts = None
            return
        self._selected_ts = entry.ts
        stamp = datetime.fromtimestamp(entry.ts).strftime("%Y-%m-%d %H:%M:%S")
        self.detail_label.setText(
            f"{stamp} · {_level_text(entry.level)} · {entry.title}\n{entry.detail or tr('ops_no_detail')}"
        )
        self.open_button.setEnabled(entry.source in dict(NAV_KEYS))

    def open_source(self) -> None:
        """Jump to the page that produced the selected operation."""
        entry = self._selected_entry()
        if entry is None or entry.source not in dict(NAV_KEYS):
            return
        self._log.mark_read(entry.ts)
        self.navigate.emit(entry.source)

    @staticmethod
    def _ask_confirm() -> bool:
        return (
            QMessageBox.question(
                None,
                tr("ops_clear"),
                tr("ops_confirm_clear"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def clear_history(self) -> None:
        if self._visible and not self._ask_confirm():
            return
        self._log.clear()
        self.status_label.setText(tr("ops_cleared"))

    @staticmethod
    def _ask_save_path(default_name: str) -> tuple[str, str]:
        path, selected = QFileDialog.getSaveFileName(
            None,
            tr("ops_export_title"),
            str(data_root() / "exports" / default_name),
            tr("ops_export_filter"),
        )
        return path, selected

    def export_report(self) -> None:
        if not self._visible:
            self.status_label.setText(tr("ops_export_nothing"))
            return
        path, selected = self._ask_save_path(timestamp_name("operations", "csv"))
        if not path:
            return
        fmt = "json" if "json" in selected.casefold() else format_for_path(path)
        if not Path(path).suffix:
            path = f"{path}.{fmt}"
        fmt = format_for_path(path)
        text = operations_to_json(self._visible) if fmt == "json" else operations_to_csv(
            self._visible,
            header=tuple(
                tr(f"ops_exp_col_{column}")
                for column in ("time", "level", "operation", "details", "source")
            ),
        )
        try:
            write_report(path, text, fmt)
        except ReportError as exc:
            self.status_label.setText(tr("ops_export_failed", msg=str(exc)))
            return
        self.status_label.setText(tr("ops_export_done", path=str(path)))

    def retranslate(self) -> None:
        self.title_label.setText(tr("ops_title"))
        self.desc_label.setText(tr("ops_desc"))
        for level, card in self.cards.items():
            card.set_title(tr(f"ops_stat_{level}"))
        self.search.setPlaceholderText(tr("ops_search"))
        level_index = self.level_combo.currentIndex()
        range_index = self.range_combo.currentIndex()
        self.level_combo.blockSignals(True)
        self.level_combo.clear()
        self.level_combo.addItems([tr(f"ops_filter_{level}") for level in LEVELS])
        self.level_combo.setCurrentIndex(max(0, min(level_index, len(LEVELS) - 1)))
        self.level_combo.blockSignals(False)
        self.range_combo.blockSignals(True)
        self.range_combo.clear()
        self.range_combo.addItems([tr(key) for key, _seconds in RANGES])
        self.range_combo.setCurrentIndex(max(0, min(range_index, len(RANGES) - 1)))
        self.range_combo.blockSignals(False)
        self.open_button.setText(tr("ops_open"))
        self.mark_button.setText(tr("ops_mark_read"))
        self.export_button.setText(tr("ops_export"))
        self.clear_button.setText(tr("ops_clear"))
        self.log_card.set_title(tr("ops_log_title"))
        self.table.setHorizontalHeaderLabels([tr(key) for key in _COLUMN_KEYS])
        self._refresh()
