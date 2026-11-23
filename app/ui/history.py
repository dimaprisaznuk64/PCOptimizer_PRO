from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
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

from app.history import PerformanceHistory, downsample, stats, top_process_summary
from app.i18n import tr

from .components import (
    CardTitleLabel,
    MetricCard,
    PerfChart,
    align_numeric_headers,
    attach_empty_hint,
)
from .theme import CARD_PADDING, PAGE_MARGINS, SPACING_MD, SPACING_SM

_RANGES: tuple[tuple[str, float], ...] = (
    ("hist_range_1h", 60.0),
    ("hist_range_6h", 360.0),
    ("hist_range_24h", 1440.0),
    ("hist_range_7d", 10080.0),
)

_CHART_POINTS = 120
_PROC_COLUMN_KEYS = (
    "hist_proc_col_name",
    "hist_proc_col_latest",
    "hist_proc_col_peak",
    "hist_proc_col_samples",
)


class HistoryPage(QWidget):
    """Persistent performance history: charts + stats for CPU / RAM / GPU / Temp."""

    def __init__(
        self,
        history: PerformanceHistory | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._history = history or PerformanceHistory()
        self._minutes = 360.0  # default 6 h

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(SPACING_MD)

        title = QLabel(tr("hist_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("hist_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        # Toolbar: range buttons + sample info
        toolbar = QHBoxLayout()
        toolbar.setSpacing(SPACING_SM)
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._range_buttons: dict[str, QPushButton] = {}
        for key, minutes in _RANGES:
            btn = QPushButton(tr(key))
            btn.setProperty("secondary", True)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, m=minutes, k=key: self._set_range(m, k))
            self._group.addButton(btn)
            toolbar.addWidget(btn)
            self._range_buttons[key] = btn
        self._range_buttons["hist_range_6h"].setChecked(True)

        self._info = QLabel("")
        self._info.setObjectName("cardSub")
        toolbar.addWidget(self._info, 1)
        layout.addLayout(toolbar)

        # Stats row
        stats_row = QHBoxLayout()
        stats_row.setSpacing(SPACING_MD)
        self._cpu_card = MetricCard(tr("hist_cpu"), sparkline=False, bar=False)
        self._ram_card = MetricCard(tr("hist_ram"), sparkline=False, bar=False)
        self._gpu_card = MetricCard(tr("hist_gpu"), sparkline=False, bar=False)
        self._temp_card = MetricCard(tr("hist_temp"), sparkline=False, bar=False)
        self._commit_card = MetricCard(tr("hist_commit"), sparkline=False, bar=False)
        self._hotspot_card = MetricCard(tr("hist_hotspot"), sparkline=False, bar=False)
        for card in (
            self._cpu_card,
            self._ram_card,
            self._gpu_card,
            self._temp_card,
            self._commit_card,
            self._hotspot_card,
        ):
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Chart
        self._chart = PerfChart(title=tr("hist_chart_title"), points=_CHART_POINTS)
        layout.addWidget(self._chart, 1)

        proc_card = QFrame()
        proc_card.setObjectName("card")
        proc_layout = QVBoxLayout(proc_card)
        proc_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        proc_layout.setSpacing(SPACING_SM)
        self._proc_title = CardTitleLabel(tr("hist_proc_title"))
        proc_layout.addWidget(self._proc_title)
        self.proc_table = QTableWidget(0, len(_PROC_COLUMN_KEYS))
        self.proc_table.setHorizontalHeaderLabels([tr(k) for k in _PROC_COLUMN_KEYS])
        self.proc_table.verticalHeader().setVisible(False)
        self.proc_table.setShowGrid(False)
        self.proc_table.setAlternatingRowColors(True)
        self.proc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proc_table.setMinimumHeight(120)
        self.proc_table.setMaximumHeight(180)
        attach_empty_hint(self.proc_table, "hist_proc_empty")
        proc_header = self.proc_table.horizontalHeader()
        for col in range(len(_PROC_COLUMN_KEYS)):
            proc_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        proc_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        align_numeric_headers(self.proc_table, (1, 2, 3))
        proc_layout.addWidget(self.proc_table)
        layout.addWidget(proc_card, 0)

        self._refresh()

    @property
    def history(self) -> PerformanceHistory:
        return self._history

    # ---------- data ----------

    def _set_range(self, minutes: float, key: str) -> None:
        self._minutes = minutes
        btn = self._range_buttons.get(key)
        if btn is not None:
            btn.setChecked(True)
        self._refresh()

    def _refresh(self) -> None:
        samples = self._history.query(self._minutes)
        count = len(samples)
        self.proc_table.setRowCount(0)
        self._chart.clear()
        if count == 0:
            self._info.setText(tr("hist_no_data"))
            self._cpu_card.update_metric("—")
            self._ram_card.update_metric("—")
            self._gpu_card.update_metric("—")
            self._temp_card.update_metric("—")
            self._commit_card.update_metric("—")
            self._hotspot_card.update_metric("—")
            return

        # Stats
        self._update_stats(self._cpu_card, samples, "cpu")
        self._update_stats(self._ram_card, samples, "ram")
        self._update_stats(self._gpu_card, samples, "gpu")
        self._update_temp_stats(samples)
        self._update_scalar_stats(self._commit_card, samples, "commit_percent", "%")
        self._update_scalar_stats(self._hotspot_card, samples, "gpu_hotspot", "°C")

        self._info.setText(tr("hist_samples", count=count))

        # Chart: push downsampled data
        points = downsample(samples, _CHART_POINTS)
        for s in points:
            self._chart.push(s.ts, cpu=s.cpu, ram=s.ram, gpu=s.gpu)
        self._render_processes(samples)

    def _render_processes(self, samples) -> None:
        rows = top_process_summary(samples)
        self.proc_table.setRowCount(len(rows))
        for row_index, (name, latest, peak, samples_count) in enumerate(rows):
            latest_text = f"{latest:.0f} MB" if latest is not None else "—"
            values = (name, latest_text, f"{peak:.0f} MB", str(samples_count))
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.proc_table.setItem(row_index, col, item)

    @staticmethod
    def _update_stats(card: MetricCard, samples, field: str) -> None:
        result = stats(samples, field)
        if result is None:
            card.update_metric("—")
            return
        _lo, avg, hi = result
        card.update_metric(f"{avg:.0f}%", tr("hist_max_min", max=hi, min=_lo))

    @staticmethod
    def _update_scalar_stats(card: MetricCard, samples, field: str, suffix: str) -> None:
        result = stats(samples, field)
        if result is None:
            card.update_metric("—")
            return
        _lo, avg, hi = result
        card.update_metric(f"{avg:.0f}{suffix}", tr("hist_max_only", max=hi))

    def _update_temp_stats(self, samples) -> None:
        cpu = stats(samples, "temp_cpu")
        gpu = stats(samples, "temp_gpu")
        hotspot = stats(samples, "gpu_hotspot")
        parts: list[str] = []
        avg_all: list[float] = []
        max_all: list[float] = []
        if cpu is not None:
            _lo, avg, hi = cpu
            parts.append(f"CPU {avg:.0f}°C")
            avg_all.append(avg)
            max_all.append(hi)
        if gpu is not None:
            _lo, avg, hi = gpu
            parts.append(f"GPU {avg:.0f}°C")
            avg_all.append(avg)
            max_all.append(hi)
        if hotspot is not None:
            _lo, avg, hi = hotspot
            parts.append(f"Hotspot {avg:.0f}°C")
            avg_all.append(avg)
            max_all.append(hi)
        if not avg_all:
            self._temp_card.update_metric("—")
            return
        avg_total = sum(avg_all) / len(avg_all)
        max_total = max(max_all)
        self._temp_card.update_metric(
            f"{avg_total:.0f}°C",
            tr("hist_max_only", max=max_total),
        )

    # ---------- i18n ----------

    def retranslate(self) -> None:
        self._title.setText(tr("hist_title"))
        self._desc.setText(tr("hist_desc"))
        for key, _minutes in _RANGES:
            btn = self._range_buttons.get(key)
            if btn is not None:
                btn.setText(tr(key))
        self._chart.set_title(tr("hist_chart_title"))
        self._cpu_card.set_title(tr("hist_cpu"))
        self._ram_card.set_title(tr("hist_ram"))
        self._gpu_card.set_title(tr("hist_gpu"))
        self._temp_card.set_title(tr("hist_temp"))
        self._commit_card.set_title(tr("hist_commit"))
        self._hotspot_card.set_title(tr("hist_hotspot"))
        self._proc_title.setText(tr("hist_proc_title"))
        self.proc_table.setHorizontalHeaderLabels([tr(k) for k in _PROC_COLUMN_KEYS])
        align_numeric_headers(self.proc_table, (1, 2, 3))
        self._refresh()
