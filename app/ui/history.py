from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.history import PerformanceHistory, downsample, stats
from app.i18n import tr

from .components import MetricCard, PerfChart

_RANGES: tuple[tuple[str, float], ...] = (
    ("hist_range_1h", 60.0),
    ("hist_range_6h", 360.0),
    ("hist_range_24h", 1440.0),
)

_CHART_POINTS = 120


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
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

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
        toolbar.setSpacing(8)
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
        stats_row.setSpacing(10)
        self._cpu_card = MetricCard(tr("hist_cpu"), sparkline=False, bar=False)
        self._ram_card = MetricCard(tr("hist_ram"), sparkline=False, bar=False)
        self._gpu_card = MetricCard(tr("hist_gpu"), sparkline=False, bar=False)
        self._temp_card = MetricCard(tr("hist_temp"), sparkline=False, bar=False)
        for card in (self._cpu_card, self._ram_card, self._gpu_card, self._temp_card):
            stats_row.addWidget(card)
        layout.addLayout(stats_row)

        # Chart
        self._chart = PerfChart(title=tr("hist_chart_title"), points=_CHART_POINTS)
        layout.addWidget(self._chart, 1)

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
        if count == 0:
            self._info.setText(tr("hist_no_data"))
            self._cpu_card.update_metric("—")
            self._ram_card.update_metric("—")
            self._gpu_card.update_metric("—")
            self._temp_card.update_metric("—")
            return

        # Stats
        self._update_stats(self._cpu_card, samples, "cpu")
        self._update_stats(self._ram_card, samples, "ram")
        self._update_stats(self._gpu_card, samples, "gpu")
        self._update_temp_stats(samples)

        self._info.setText(tr("hist_samples", count=count))

        # Chart: push downsampled data
        points = downsample(samples, _CHART_POINTS)
        for s in points:
            self._chart.push(s.ts, cpu=s.cpu, ram=s.ram, gpu=s.gpu)

    @staticmethod
    def _update_stats(card: MetricCard, samples, field: str) -> None:
        result = stats(samples, field)
        if result is None:
            card.update_metric("—")
            return
        _lo, avg, hi = result
        card.update_metric(f"{avg:.0f}%", tr("hist_max_min", max=hi, min=_lo))

    def _update_temp_stats(self, samples) -> None:
        cpu = stats(samples, "temp_cpu")
        gpu = stats(samples, "temp_gpu")
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
        self._refresh()
