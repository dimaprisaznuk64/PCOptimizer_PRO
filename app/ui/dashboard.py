from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from app.sensors import Snapshot

from .components import CardPanel, MetricCard, ValueListCard
from .format import gb as _gb
from .format import rate as _rate


class DashboardPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(6)

        title = QLabel("Dashboard")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("Live system metrics — updates every second")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        grid = QGridLayout()
        grid.setContentsMargins(0, 18, 0, 0)
        grid.setSpacing(12)

        self.cpu = MetricCard("CPU")
        self.ram = MetricCard("RAM")
        self.gpu = MetricCard("GPU")
        self.net = MetricCard("Network", sparkline=True, bar=False)

        self.disks = CardPanel("Storage")
        self.thermal = ValueListCard("Thermals")

        grid.addWidget(self.cpu, 0, 0)
        grid.addWidget(self.ram, 0, 1)
        grid.addWidget(self.gpu, 0, 2)
        grid.addWidget(self.net, 0, 3)
        grid.addWidget(self.disks, 1, 0, 1, 3)
        grid.addWidget(self.thermal, 1, 3)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        grid.setColumnStretch(3, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)
        layout.addLayout(grid, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

        self._net_total_sent = 0.0
        self._net_total_recv = 0.0

    def apply_snapshot(self, s: Snapshot) -> None:
        if s.cpu:
            c = s.cpu
            freq = f" · {c.freq_mhz:.0f}MHz" if c.freq_mhz else ""
            self.cpu.update_metric(
                f"{c.percent:.0f}%",
                f"{c.physical_cores}/{c.logical_cores} cores{freq}",
                percent=c.percent,
                spark=c.percent,
            )

        if s.memory:
            m = s.memory
            self.ram.update_metric(
                f"{m.percent:.0f}%",
                f"{_gb(m.used)} used / {_gb(m.total)} · swap {m.swap_percent:.0f}%",
                percent=m.percent,
                spark=m.percent,
            )

        g = s.gpu
        if g:
            vram_percent = 100.0 * g.memory_used / g.memory_total if g.memory_total else None
            temp = f"{g.temperature:.0f}C" if g.temperature is not None else "?"
            power = f"{g.power_w:.0f}W" if g.power_w is not None else "?"
            self.gpu.update_metric(
                f"{g.utilization:.0f}%",
                f"VRAM {_gb(g.memory_used)}/{_gb(g.memory_total)} · {temp} · {power}",
                percent=vram_percent,
                spark=g.utilization,
            )
        else:
            self.gpu.update_metric("—", "no GPU data")

        if s.net:
            n = s.net
            self.net.update_metric(
                f"{_rate(n.recv_rate)}/s",
                f"up {_rate(n.send_rate)}/s · total ↓{_gb(n.bytes_recv)} ↑{_gb(n.bytes_sent)}",
                percent=None,
                spark=n.recv_rate,
            )

        if s.disks:
            rows = [
                (d.mountpoint.rstrip("\\/") or d.device, d.percent, f"{_gb(d.used)} / {_gb(d.total)}")
                for d in s.disks
            ]
            self.disks.set_rows(rows)

        if s.thermal:
            self.thermal.set_values([(name, f"{value:.0f}C") for name, value in s.thermal.temperatures])

        if s.errors:
            self.errors.setText("Sensors: " + " · ".join(f"{k}: {v}" for k, v in s.errors.items()))
            self.errors.setVisible(True)
        else:
            self.errors.setVisible(False)
            self.errors.setText("")
