from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.sensors import Snapshot

from .components import Bar, CardPanel, Sparkline
from .format import gb, rate

ACCENT = "#4f8cff"
ACCENT_HOVER = "#6ba0ff"
DANGER = "#e5534b"
OK = "#3fb950"


def _level_color(percent: float | None) -> str:
    if percent is None:
        return ACCENT
    if percent >= 90:
        return DANGER
    if percent >= 70:
        return ACCENT
    return ACCENT_HOVER


class _Card(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(8)
        label = QLabel(title.upper())
        label.setObjectName("cardTitle")
        self._layout.addWidget(label)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self._layout.addLayout(self.body)
        self._layout.addStretch(1)


class CoreBars(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(4)
        self._cells: list[tuple[QLabel, Bar, QLabel]] = []
        self._count = 0

    def set_percents(self, percents: tuple[float, ...]) -> None:
        if len(percents) != self._count:
            self._rebuild(len(percents))
        for index, (label, bar, text) in enumerate(self._cells):
            if index >= len(percents):
                label.setVisible(False)
                bar.setVisible(False)
                text.setVisible(False)
                continue
            value = percents[index]
            label.setVisible(True)
            bar.setVisible(True)
            text.setVisible(True)
            bar.set_percent(value)
            bar.set_color(_level_color(value))
            text.setText(f"{value:.0f}%")

    def _rebuild(self, count: int) -> None:
        for label, bar, text in self._cells:
            label.deleteLater()
            bar.deleteLater()
            text.deleteLater()
        self._cells = []
        self._count = count
        columns = 4 if count > 8 else 2
        for i in range(count):
            row, col = divmod(i, columns)
            label = QLabel(str(i))
            label.setObjectName("cardSub")
            label.setFixedWidth(16)
            bar = Bar(ACCENT)
            text = QLabel("")
            text.setObjectName("cardSub")
            text.setFixedWidth(40)
            text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._layout.addWidget(label, row, col * 3)
            self._layout.addWidget(bar, row, col * 3 + 1)
            self._layout.addWidget(text, row, col * 3 + 2)
            self._layout.setColumnStretch(col * 3 + 1, 1)
            self._cells.append((label, bar, text))


class MonitorPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(6)

        title = QLabel("System Monitor")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel("CPU, memory, storage and network detail — updates every second")
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        grid = QGridLayout()
        grid.setContentsMargins(0, 18, 0, 0)
        grid.setSpacing(12)

        cpu_card = self._build_cpu_card()
        mem_card = self._build_memory_card()
        net_card = self._build_network_card()
        self.disks = CardPanel("Storage")
        self.thermals = CardPanel("Thermals")

        grid.addWidget(cpu_card, 0, 0, 1, 4)
        grid.addWidget(mem_card, 1, 0, 1, 2)
        grid.addWidget(net_card, 1, 2, 1, 2)
        grid.addWidget(self.disks, 2, 0, 1, 2)
        grid.addWidget(self.thermals, 2, 2, 1, 2)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        grid.setRowStretch(0, 5)
        grid.setRowStretch(1, 3)
        grid.setRowStretch(2, 3)
        layout.addLayout(grid, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

    def _build_cpu_card(self) -> QFrame:
        card = _Card("CPU")
        row = QGridLayout()
        row.setSpacing(16)

        summary = QVBoxLayout()
        summary.setSpacing(4)
        self.cpu_value = QLabel("—")
        self.cpu_value.setObjectName("cardValue")
        summary.addWidget(self.cpu_value)
        self.cpu_sub = QLabel("")
        self.cpu_sub.setObjectName("cardSub")
        summary.addWidget(self.cpu_sub)
        summary.addStretch(1)
        box = QWidget()
        box.setLayout(summary)
        box.setFixedWidth(200)
        row.addWidget(box, 0, 0)

        self.cpu_spark = Sparkline(ACCENT, points=180, height=96)
        row.addWidget(self.cpu_spark, 0, 1)

        core_label = QLabel("PER-CORE USAGE")
        core_label.setObjectName("cardTitle")
        card.body.addWidget(core_label)
        card.body.addLayout(row)
        self.cores = CoreBars()
        card.body.addWidget(self.cores)
        return card

    def _build_memory_card(self) -> QFrame:
        card = _Card("Memory")
        self.mem_value = QLabel("—")
        self.mem_value.setObjectName("cardValue")
        card.body.addWidget(self.mem_value)
        self.mem_sub = QLabel("")
        self.mem_sub.setObjectName("cardSub")
        card.body.addWidget(self.mem_sub)
        self.mem_bar = Bar(ACCENT, height=10)
        card.body.addWidget(self.mem_bar)
        self.mem_spark = Sparkline(ACCENT, points=90, height=44)
        card.body.addWidget(self.mem_spark)
        self.swap_sub = QLabel("")
        self.swap_sub.setObjectName("cardSub")
        card.body.addWidget(self.swap_sub)
        self.swap_bar = Bar(ACCENT_HOVER, height=8)
        card.body.addWidget(self.swap_bar)
        return card

    def _build_network_card(self) -> QFrame:
        card = _Card("Network")
        self.net_down_value = QLabel("—")
        self.net_down_value.setObjectName("cardValue")
        card.body.addWidget(self.net_down_value)
        self.net_down_sub = QLabel("")
        self.net_down_sub.setObjectName("cardSub")
        card.body.addWidget(self.net_down_sub)
        self.net_down_spark = Sparkline(OK, points=90, height=40)
        card.body.addWidget(self.net_down_spark)
        self.net_up_value = QLabel("")
        self.net_up_value.setObjectName("cardRow")
        card.body.addWidget(self.net_up_value)
        self.net_up_spark = Sparkline(ACCENT, points=90, height=28)
        card.body.addWidget(self.net_up_spark)
        self.net_total_sub = QLabel("")
        self.net_total_sub.setObjectName("cardSub")
        self.net_total_sub.setWordWrap(True)
        card.body.addWidget(self.net_total_sub)
        return card

    def apply_snapshot(self, s: Snapshot) -> None:
        if s.cpu:
            c = s.cpu
            freq = f" · {c.freq_mhz:.0f}MHz" if c.freq_mhz else ""
            self.cpu_value.setText(f"{c.percent:.0f}%")
            self.cpu_sub.setText(f"{c.physical_cores} cores / {c.logical_cores} threads{freq}")
            self.cpu_spark.add(c.percent)
            self.cores.set_percents(c.per_core)

        if s.memory:
            m = s.memory
            self.mem_value.setText(f"{m.percent:.0f}%")
            self.mem_sub.setText(f"{gb(m.used)} used / {gb(m.total)} · {gb(m.available)} available")
            self.mem_bar.set_percent(m.percent)
            self.mem_bar.set_color(_level_color(m.percent))
            self.mem_spark.add(m.percent)
            self.swap_sub.setText(f"Swap {gb(m.swap_used)} / {gb(m.swap_total)} · {m.swap_percent:.0f}%")
            self.swap_bar.set_percent(m.swap_percent)
            self.swap_bar.set_color(_level_color(m.swap_percent))

        if s.net:
            n = s.net
            self.net_down_value.setText(f"{rate(n.recv_rate)}/s")
            self.net_down_sub.setText(f"download · {n.packets_recv:,} packets")
            self.net_down_spark.add(n.recv_rate)
            self.net_up_value.setText(f"↑ {rate(n.send_rate)}/s · {n.packets_sent:,} packets")
            self.net_up_spark.add(n.send_rate)
            self.net_total_sub.setText(f"total ↓{gb(n.bytes_recv)} ↑{gb(n.bytes_sent)}")

        if s.disks:
            rows = [
                (
                    d.mountpoint.rstrip("\\/") or d.device,
                    d.percent,
                    f"{gb(d.used)} / {gb(d.total)} · {d.fstype}",
                )
                for d in s.disks
            ]
            self.disks.set_rows(rows)

        if s.thermal:
            self.thermals.set_rows(
                [(name, value, f"{value:.0f}C") for name, value in s.thermal.temperatures]
            )

        if s.errors:
            self.errors.setText("Sensors: " + " · ".join(f"{k}: {v}" for k, v in s.errors.items()))
            self.errors.setVisible(True)
        else:
            self.errors.setText("")
            self.errors.setVisible(False)
