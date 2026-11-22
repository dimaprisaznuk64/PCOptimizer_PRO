from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.sensors.types import Snapshot
from app.temperature.service import (
    STATUS_DANGER,
    STATUS_OK,
    STATUS_WARN,
    TemperatureReport,
    TemperatureService,
    target_temperatures,
)

from .combos import CompactCombo, tune_combo
from .components import (
    CardTitleLabel,
    MetricCard,
    align_numeric_headers,
    attach_empty_hint,
)
from .format import temp_text
from .tasks import Task
from .theme import ACCENT, C2, C3, CARD_PADDING, DANGER, OK, PAGE_MARGINS, PAGE_SPACING, WARN

COLUMN_KEYS: tuple[str, ...] = (
    "temp_col_source",
    "temp_col_current",
    "temp_col_peak",
    "temp_col_avg",
    "temp_col_max",
    "temp_col_status",
)

_RANGES: tuple[tuple[str, float], ...] = (
    ("temp_range_1h", 60.0),
    ("temp_range_6h", 360.0),
    ("temp_range_24h", 1440.0),
    ("temp_range_7d", 10080.0),
)

_CARD_KEYS: tuple[str, ...] = (
    "temp_metric_system",
    "temp_metric_gpu",
    "temp_metric_hotspot",
    "temp_metric_clock",
)


class TemperaturePage(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        service: TemperatureService | None = None,
        history: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or TemperatureService(history=history)
        self._report: TemperatureReport | None = None
        self._history_report: TemperatureReport | None = None
        self._snapshot: Snapshot | None = None
        self._peaks: dict[tuple[str, int], float] = {}
        self._series: dict[str, list[float]] = {}
        self._task: Task | None = None
        self._request_id = 0
        self._history_loaded = False
        self._current_minutes = 360.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)

        self.pageTitle = QLabel(tr("temp_title"))
        self.pageTitle.setObjectName("pageTitle")
        layout.addWidget(self.pageTitle)
        self.pageDesc = QLabel(tr("temp_desc"))
        self.pageDesc.setObjectName("pageDesc")
        layout.addWidget(self.pageDesc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)
        self._range_label = QLabel(tr("temp_range_label"))
        toolbar.addWidget(self._range_label)
        self.range_combo = CompactCombo()
        for key, _minutes in _RANGES:
            self.range_combo.addItem(tr(key))
        self.range_combo.setCurrentIndex(1)
        self.range_combo.currentIndexChanged.connect(self._on_range_changed)
        tune_combo(self.range_combo, width=150)
        toolbar.addWidget(self.range_combo)
        self.refresh_button = QPushButton(tr("temp_refresh"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self._load_history)
        toolbar.addWidget(self.refresh_button)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        targets = QFrame()
        targets.setObjectName("card")
        targets_layout = QHBoxLayout(targets)
        targets_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        targets_layout.setSpacing(12)
        self._target_labels: dict[str, tuple[QLabel, QLabel]] = {}
        for kind, key in (
            ("cpu", "temp_target_cpu"),
            ("board", "temp_target_board"),
            ("gpu", "temp_target_gpu"),
        ):
            column = QVBoxLayout()
            column.setSpacing(2)
            title = QLabel(tr(key))
            title.setObjectName("cardRow")
            value = QLabel("—")
            value.setObjectName("cardValue")
            value.setMinimumWidth(0)
            value.setWordWrap(True)
            column.addWidget(title)
            column.addWidget(value, 1)
            targets_layout.addLayout(column, 1)
            self._target_labels[kind] = (title, value)
        layout.addWidget(targets)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.system_card = MetricCard(
            tr("temp_metric_system"), sparkline=True, bar=False, color=WARN
        )
        self.gpu_card = MetricCard(tr("temp_metric_gpu"), sparkline=True, bar=False, color=C3)
        self.hotspot_card = MetricCard(
            tr("temp_metric_hotspot"), sparkline=True, bar=False, color=ACCENT
        )
        self.clock_card = MetricCard(tr("temp_metric_clock"), sparkline=False, bar=False, color=C2)
        for card in (
            self.system_card,
            self.gpu_card,
            self.hotspot_card,
            self.clock_card,
        ):
            cards.addWidget(card)
        layout.addLayout(cards)

        results = QFrame()
        results.setObjectName("card")
        results_layout = QVBoxLayout(results)
        results_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        results_layout.setSpacing(8)
        self._results_title = CardTitleLabel(tr("temp_results_title"))
        results_layout.addWidget(self._results_title)

        self.table = QTableWidget(0, len(COLUMN_KEYS))
        self.table.setHorizontalHeaderLabels([tr(key) for key in COLUMN_KEYS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(180)
        attach_empty_hint(self.table, "temp_empty")
        header = self.table.horizontalHeader()
        for column in range(len(COLUMN_KEYS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        align_numeric_headers(self.table, (1, 2, 3, 4))
        results_layout.addWidget(self.table, 1)

        self._legend = QLabel("")
        self._legend.setObjectName("cardSub")
        results_layout.addWidget(self._legend)
        layout.addWidget(results, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

        self._update_legend()
        self._render_cards(None)
        self._render_targets(None)

    def apply_snapshot(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        report = self._service.readings_from_snapshot(snapshot)
        self._report = report
        for index, reading in enumerate(report.readings):
            if reading.current is not None:
                key = (reading.kind, index)
                previous = self._peaks.get(key, reading.current)
                self._peaks[key] = max(previous, reading.current)
        self._render_report(report, self._peaks)
        self._render_cards(report)
        self._render_targets(snapshot)
        self._show_errors(report.errors)

    def retranslate(self) -> None:
        self.pageTitle.setText(tr("temp_title"))
        self.pageDesc.setText(tr("temp_desc"))
        for kind, key in (
            ("cpu", "temp_target_cpu"),
            ("board", "temp_target_board"),
            ("gpu", "temp_target_gpu"),
        ):
            self._target_labels[kind][0].setText(tr(key))
        self._range_label.setText(tr("temp_range_label"))
        index = self.range_combo.currentIndex()
        self.range_combo.blockSignals(True)
        for i, (key, _minutes) in enumerate(_RANGES):
            self.range_combo.setItemText(i, tr(key))
        self.range_combo.setCurrentIndex(index)
        self.range_combo.blockSignals(False)
        self.refresh_button.setText(tr("temp_refresh"))
        self._results_title.setText(tr("temp_results_title"))
        self.table.setHorizontalHeaderLabels([tr(key) for key in COLUMN_KEYS])
        align_numeric_headers(self.table, (1, 2, 3, 4))
        self.system_card.set_title(tr(_CARD_KEYS[0]))
        self.gpu_card.set_title(tr(_CARD_KEYS[1]))
        self.hotspot_card.set_title(tr(_CARD_KEYS[2]))
        self.clock_card.set_title(tr(_CARD_KEYS[3]))
        report = self._report
        peaks: dict[tuple[str, int], float] | None = None
        if self._snapshot is not None:
            report = self._service.readings_from_snapshot(self._snapshot, record=False)
            self._report = report
            peaks = self._peaks
        elif self._history_report is not None:
            report = self._service.from_history(self._current_minutes)
            self._report = report
        self._update_legend()
        self._render_report(report, peaks)
        self._render_cards(report)
        self._render_targets(self._snapshot)
        self._show_errors(report.errors if report else ())

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._history_loaded:
            self._history_loaded = True
            self._load_history()

    def _load_history(self) -> None:
        if self._task is not None:
            return
        index = max(0, self.range_combo.currentIndex())
        _key, minutes = _RANGES[index]
        self._current_minutes = minutes
        self._request_id += 1
        token = self._request_id
        service = self._service
        service.invalidate_cache()

        def load() -> tuple[int, TemperatureReport, dict[str, list[float]]]:
            return token, service.from_history(minutes), service.history_series(minutes)

        task = Task(load, self)
        self._task = task
        task.done.connect(self._on_history)
        task.failed.connect(self._on_history_error)
        task.finished.connect(self._clear_task)
        task.finished.connect(task.deleteLater)
        task.start()

    def _on_range_changed(self, _index: int) -> None:
        self._load_history()

    def _clear_task(self) -> None:
        self._task = None

    def _on_history(self, result: object) -> None:
        if not isinstance(result, tuple) or len(result) != 3:
            return
        token, report, series = result
        if token != self._request_id or not isinstance(report, TemperatureReport):
            return
        self._series = series if isinstance(series, dict) else {}
        self._history_report = report
        for key, card in (
            ("system", self.system_card),
            ("gpu", self.gpu_card),
            ("hotspot", self.hotspot_card),
        ):
            if card.spark is None:
                continue
            card.spark.reset()
            for value in self._series.get(key, ()):
                card.spark.add(value)
        if self._snapshot is None:
            self._report = report
            self._render_report(report)
            self._render_cards(report)
            self._show_errors(report.errors)

    def _on_history_error(self, message: str) -> None:
        self._show_errors((message,))

    def _render_report(
        self,
        report: TemperatureReport | None,
        peaks: dict[tuple[str, int], float] | None = None,
    ) -> None:
        readings = report.readings if report else ()
        self.table.setRowCount(len(readings))
        for row, reading in enumerate(readings):
            peak = reading.peak
            if peaks is not None:
                peak = peaks.get((reading.kind, row), peak)
            values = (
                reading.source,
                temp_text(reading.current) if reading.available else "—",
                temp_text(peak) if peak is not None else "—",
                temp_text(reading.avg) if reading.avg is not None else "—",
                temp_text(reading.max) if reading.max is not None else "—",
                tr(f"temp_status_{reading.status.lower()}"),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in (1, 2, 3, 4):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if column == 5:
                    color = {
                        STATUS_DANGER: DANGER,
                        STATUS_WARN: WARN,
                        STATUS_OK: OK,
                    }.get(reading.status, OK)
                    item.setForeground(QColor(color))
                self.table.setItem(row, column, item)

    def _render_cards(self, report: TemperatureReport | None) -> None:
        system = self._pick(report, "system")
        gpu = self._pick(report, "gpu")
        hotspot = self._pick(report, "hotspot")
        self._set_card(self.system_card, system)
        self._set_card(self.gpu_card, gpu)
        self._set_card(self.hotspot_card, hotspot)

        clock = "—"
        snapshot = self._snapshot
        if snapshot is not None:
            gpus = [g for g in snapshot.gpus if not getattr(g, "stale", False)]
            if gpus:
                limited = any(bool(getattr(g, "throttling", False)) for g in gpus)
                clock = tr("gpu_throttling") if limited else tr("gpu_throttle_none")
        self._set_card_text(self.clock_card, clock, "")

    def _render_targets(self, snapshot: Snapshot | None) -> None:
        targets = target_temperatures(snapshot) if snapshot is not None else {}
        for kind, (title, value) in self._target_labels.items():
            current, source = targets.get(kind, (None, ""))
            value.setText(temp_text(current))
            title.setToolTip(source)

    def _set_card(self, card: MetricCard, reading) -> None:
        if reading is None or not reading.available or reading.current is None:
            self._set_card_text(card, "—", tr("no_data"))
            return
        self._set_card_text(card, temp_text(reading.current), self._status_text(reading.status))

    @staticmethod
    def _set_card_text(card: MetricCard, value: str, sub: str) -> None:
        card.value.setText(value)
        card.sub.setText(sub)
        card.sub.setVisible(bool(sub))

    @staticmethod
    def _status_text(status: str) -> str:
        return tr(f"temp_status_{status.lower()}")

    @staticmethod
    def _pick(report: TemperatureReport | None, kind: str):
        if report is None:
            return None
        candidates = [r for r in report.readings if r.kind == kind]
        values = [r for r in candidates if r.current is not None]
        return max(values, key=lambda r: r.current or 0.0) if values else None

    def _update_legend(self) -> None:
        system_warn, system_danger = self._service.thresholds()["system"]
        gpu_warn, gpu_danger = self._service.thresholds()["gpu"]
        self._legend.setText(
            f"{tr('therm_zone', n='max')}: {system_warn:.0f}/{system_danger:.0f}°C · "
            f"{tr('temp_src_gpu_core')}: {gpu_warn:.0f}/{gpu_danger:.0f}°C"
        )

    def _show_errors(self, errors: tuple[str, ...]) -> None:
        if errors:
            self.errors.setText(tr("mon_sensors", msg=" · ".join(errors)))
            self.errors.setVisible(True)
        else:
            self.errors.clear()
            self.errors.setVisible(False)
