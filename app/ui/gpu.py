from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.i18n import tr
from app.sensors import GpuStat, Snapshot

from .components import GaugeCard
from .format import gb
from .theme import C2 as VRAM_COLOR
from .theme import C3 as TEMP_COLOR
from .theme import C4 as POWER_COLOR
from .theme import fs


class GpuPanel(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        header = QVBoxLayout()
        header.setSpacing(2)
        self.name = QLabel("GPU")
        self.name.setObjectName("gpuName")
        header.addWidget(self.name)
        self.info = QLabel("")
        self.info.setObjectName("cardSub")
        header.addWidget(self.info)
        header.addStretch(1)
        head_widget = QWidget()
        head_widget.setLayout(header)
        layout.addWidget(head_widget)

        grid = QGridLayout()
        grid.setSpacing(12)
        self.util = GaugeCard(tr("gpu_util"), "gpu", caption=tr("gpu_caption_core"))
        self.vram = GaugeCard(tr("gpu_vram"), "ram", caption=tr("gpu_caption_mem"), color=VRAM_COLOR)
        self.temp = GaugeCard(tr("gpu_temp"), "monitor", caption=tr("gpu_caption_temp"), color=TEMP_COLOR)
        self.power = GaugeCard(tr("gpu_power"), "optimizer", caption=tr("gpu_caption_draw"), color=POWER_COLOR)
        for card in (self.util, self.vram, self.temp, self.power):
            card.more.setVisible(False)
        grid.addWidget(self.util, 0, 0)
        grid.addWidget(self.vram, 0, 1)
        grid.addWidget(self.temp, 1, 0)
        grid.addWidget(self.power, 1, 1)
        for col in range(2):
            grid.setColumnStretch(col, 1)
        for row in range(2):
            grid.setRowStretch(row, 1)
        layout.addLayout(grid, 1)

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self.util.set_title(tr("gpu_util"))
        self.vram.set_title(tr("gpu_vram"))
        self.temp.set_title(tr("gpu_temp"))
        self.power.set_title(tr("gpu_power"))
        self.util.set_caption(tr("gpu_caption_core"))
        self.vram.set_caption(tr("gpu_caption_mem"))
        self.temp.set_caption(tr("gpu_caption_temp"))
        self.power.set_caption(tr("gpu_caption_draw"))

    def update_gpu(self, g: GpuStat) -> None:
        self.name.setText(f"GPU {g.index} · {g.name}")

        details: list[str] = []
        fan = f"{g.fan_percent:.0f}%" if g.fan_percent is not None else tr("gpu_na")
        details.append(tr("gpu_fan") + f" {fan}")
        if g.clock_mhz is not None:
            details.append(tr("gpu_clock") + f" {g.clock_mhz:.0f}MHz")
        if g.power_limit_w is not None:
            details.append(tr("gpu_power_limit") + f" {g.power_limit_w:.0f}W")
        self.info.setText(" · ".join(details))

        self.util.update_metric(
            f"{g.utilization:.0f}%",
            tr("gpu_core_util"),
            percent=g.utilization,
            spark=g.utilization,
        )

        vram_percent = 100.0 * g.memory_used / g.memory_total if g.memory_total else 0.0
        self.vram.update_metric(
            f"{g.memory_used / 1024**3:.1f}GB",
            tr("gpu_of_total", total=gb(g.memory_total), pct=vram_percent),
            percent=vram_percent,
            spark=vram_percent,
        )

        self.temp.update_metric(
            "—" if g.temperature is None else f"{g.temperature:.0f}C",
            tr("gpu_temp_sub"),
            percent=g.temperature,
            spark=g.temperature,
        )

        power_percent = None
        power_sub = tr("gpu_power_sub")
        if g.power_w is not None and g.power_limit_w:
            power_percent = 100.0 * g.power_w / g.power_limit_w
            power_sub = tr("gpu_of_limit", limit=g.power_limit_w)
        self.power.update_metric(
            "—" if g.power_w is None else f"{g.power_w:.0f}W",
            power_sub,
            percent=power_percent,
            spark=g.power_w,
        )


class GpuPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(6)

        title = QLabel(tr("gpu_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("gpu_desc"))
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        self._panels_layout = QVBoxLayout()
        self._panels_layout.setSpacing(12)
        self._panels_layout.setContentsMargins(0, 18, 0, 0)
        layout.addLayout(self._panels_layout, 1)

        self.empty = QLabel(tr("gpu_waiting"))
        self.empty.setObjectName("cardSub")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet(f"font-size: {fs(14)}px;")
        self._panels_layout.addWidget(self.empty, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

        self._panels: list[GpuPanel] = []

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("gpu_title"))
        self._desc.setText(tr("gpu_desc"))
        for panel in self._panels:
            panel.retranslate()

    def _rebuild(self, count: int) -> None:
        for panel in self._panels:
            self._panels_layout.removeWidget(panel)
            panel.deleteLater()
        self._panels = [GpuPanel() for _ in range(count)]
        for panel in self._panels:
            self._panels_layout.addWidget(panel)
        self.empty.setVisible(count == 0)

    def apply_snapshot(self, s: Snapshot) -> None:
        gpus = sorted(s.gpus, key=lambda g: g.index)
        if len(gpus) != len(self._panels):
            self._rebuild(len(gpus))
        for panel, gpu in zip(self._panels, gpus, strict=False):
            panel.update_gpu(gpu)

        if not gpus:
            reason = s.errors.get("nvml") or s.errors.get("gpu")
            self.empty.setText(tr("gpu_unavailable", reason=reason) if reason else tr("gpu_no_data"))
        self.empty.setVisible(not gpus)

        # When no GPU is shown, the placeholder above already explains the sensor error.
        shown_errors = {k: v for k, v in s.errors.items() if gpus or k not in ("nvml", "gpu")}
        if shown_errors:
            self.errors.setText(tr("mon_sensors", msg=" · ".join(f"{k}: {v}" for k, v in shown_errors.items())))
            self.errors.setVisible(True)
        else:
            self.errors.setText("")
            self.errors.setVisible(False)
