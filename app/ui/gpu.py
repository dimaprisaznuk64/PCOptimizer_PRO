from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.sensors import GpuStat, Snapshot

from .components import MetricCard
from .format import gb

VRAM_COLOR = "#9b6dff"
TEMP_COLOR = "#f0a03a"
POWER_COLOR = "#3fb950"


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
        self.util = MetricCard("Utilization", sparkline=True, bar=True)
        self.vram = MetricCard("VRAM", sparkline=True, bar=True, color=VRAM_COLOR)
        self.temp = MetricCard("Temperature", sparkline=True, bar=False, color=TEMP_COLOR)
        self.power = MetricCard("Power", sparkline=True, bar=True, color=POWER_COLOR)
        grid.addWidget(self.util, 0, 0)
        grid.addWidget(self.vram, 0, 1)
        grid.addWidget(self.temp, 0, 2)
        grid.addWidget(self.power, 0, 3)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)

    def update_gpu(self, g: GpuStat) -> None:
        self.name.setText(f"GPU {g.index} · {g.name}")

        details: list[str] = []
        details.append(f"fan {f'{g.fan_percent:.0f}%' if g.fan_percent is not None else 'n/a'}")
        if g.clock_mhz is not None:
            details.append(f"clock {g.clock_mhz:.0f}MHz")
        if g.power_limit_w is not None:
            details.append(f"power limit {g.power_limit_w:.0f}W")
        self.info.setText(" · ".join(details))

        self.util.update_metric(
            f"{g.utilization:.0f}%",
            "core utilization",
            percent=g.utilization,
            spark=g.utilization,
        )

        vram_percent = 100.0 * g.memory_used / g.memory_total if g.memory_total else 0.0
        self.vram.update_metric(
            f"{g.memory_used / 1024**3:.1f}GB",
            f"of {gb(g.memory_total)} · {vram_percent:.0f}% used",
            percent=vram_percent,
            spark=vram_percent,
        )

        self.temp.update_metric(
            "—" if g.temperature is None else f"{g.temperature:.0f}C",
            "GPU temperature",
            percent=None,
            spark=g.temperature,
        )

        power_percent = None
        power_sub = "power draw"
        if g.power_w is not None and g.power_limit_w:
            power_percent = 100.0 * g.power_w / g.power_limit_w
            power_sub = f"of {g.power_limit_w:.0f}W limit"
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

        title = QLabel("GPU Monitor")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("NVIDIA utilization, VRAM, temperature, power and fan via NVML")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        self._panels_layout = QVBoxLayout()
        self._panels_layout.setSpacing(12)
        self._panels_layout.setContentsMargins(0, 18, 0, 0)
        layout.addLayout(self._panels_layout, 1)

        self.empty = QLabel("Waiting for GPU data…")
        self.empty.setObjectName("cardSub")
        self._panels_layout.addWidget(self.empty)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

        self._panels: list[GpuPanel] = []

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
        for panel, gpu in zip(self._panels, gpus):
            panel.update_gpu(gpu)

        if not gpus:
            reason = s.errors.get("nvml") or s.errors.get("gpu") or "no NVIDIA GPU data in this snapshot"
            self.empty.setText(reason)
        self.empty.setVisible(not gpus)

        if s.errors:
            self.errors.setText("Sensors: " + " · ".join(f"{k}: {v}" for k, v in s.errors.items()))
            self.errors.setVisible(True)
        else:
            self.errors.setText("")
            self.errors.setVisible(False)
