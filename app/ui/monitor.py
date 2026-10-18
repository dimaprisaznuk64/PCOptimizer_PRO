from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.i18n import tr
from app.sensors import Snapshot

from .components import Bar, CardPanel, Sparkline
from .format import gb, rate, zone_label
from .theme import ACCENT, ACCENT_HOVER, DANGER, OK


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
        self.title_label = label
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self._layout.addLayout(self.body)
        self._layout.addStretch(1)

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())


class CoreBars(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(10)
        self._layout.setVerticalSpacing(8)
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
        for cell in self._cells:
            for w in cell:
                w.hide()
                self._layout.removeWidget(w)
                w.deleteLater()
        self._cells = []
        self._count = count
        columns = 4 if count > 8 else 2
        for i in range(count):
            row, col = divmod(i, columns)
            label = QLabel(str(i))
            label.setObjectName("cardSub")
            if col == 0:
                label.setFixedWidth(18)
            else:  # gap between column groups so "16%" never touches the next index
                label.setFixedWidth(42)
                label.setContentsMargins(24, 0, 0, 0)
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

        title = QLabel(tr("mon_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("mon_desc"))
        desc.setObjectName("pageDesc")
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        grid = QGridLayout()
        grid.setContentsMargins(0, 18, 0, 0)
        grid.setSpacing(12)

        cpu_card = self._build_cpu_card()
        mem_card = self._build_memory_card()
        net_card = self._build_network_card()
        self.disks = CardPanel(tr("mon_storage"))
        self.thermals = CardPanel(tr("mon_thermals"))

        grid.addWidget(cpu_card, 0, 0, 1, 4)
        grid.addWidget(mem_card, 1, 0, 1, 2)
        grid.addWidget(net_card, 1, 2, 1, 2)
        grid.addWidget(self.disks, 2, 0, 1, 2)
        grid.addWidget(self.thermals, 2, 2, 1, 2)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 1)
        layout.addLayout(grid, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

    def _build_cpu_card(self) -> QFrame:
        card = _Card(tr("dash_cpu"))
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

        core_label = QLabel(tr("mon_per_core"))
        core_label.setObjectName("cardTitle")
        card.body.addWidget(core_label)
        card.body.addLayout(row)
        self.cores = CoreBars()
        card.body.addWidget(self.cores)
        self._core_title = core_label
        self._cpu_card = card
        return card

    def _build_memory_card(self) -> QFrame:
        card = _Card(tr("dash_mem"))
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
        self._mem_card = card
        return card

    def _build_network_card(self) -> QFrame:
        card = _Card(tr("dash_net"))
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
        self._net_card = card
        return card

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("mon_title"))
        self._desc.setText(tr("mon_desc"))
        self._cpu_card.set_title(tr("dash_cpu"))
        self._mem_card.set_title(tr("dash_mem"))
        self._net_card.set_title(tr("dash_net"))
        self._core_title.setText(tr("mon_per_core"))
        self.disks.set_title(tr("mon_storage"))
        self.thermals.set_title(tr("mon_thermals"))

    def apply_snapshot(self, s: Snapshot) -> None:
        if s.cpu:
            c = s.cpu
            freq = tr("mon_freq_base", mhz=f"{c.freq_mhz:.0f}") if c.freq_mhz else ""
            self.cpu_value.setText(f"{c.percent:.0f}%")
            self.cpu_sub.setText(tr("mon_cores", physical=c.physical_cores, logical=c.logical_cores) + freq)
            self.cpu_spark.add(c.percent)
            self.cores.set_percents(c.per_core)

        if s.memory:
            m = s.memory
            self.mem_value.setText(f"{m.percent:.0f}%")
            self.mem_sub.setText(tr("mon_used_total", used=gb(m.used), total=gb(m.total), available=gb(m.available)))
            self.mem_bar.set_percent(m.percent)
            self.mem_bar.set_color(_level_color(m.percent))
            self.mem_spark.add(m.percent)
            self.swap_sub.setText(tr("mon_swap", used=gb(m.swap_used), total=gb(m.swap_total), pct=m.swap_percent))
            self.swap_bar.set_percent(m.swap_percent)
            self.swap_bar.set_color(_level_color(m.swap_percent))

        if s.net:
            n = s.net
            self.net_down_value.setText(f"{rate(n.recv_rate)}/s")
            self.net_down_sub.setText(tr("mon_down_sub", packets=f"{n.packets_recv:,}"))
            self.net_down_spark.add(n.recv_rate)
            self.net_up_value.setText(tr("mon_up_sub", rate=rate(n.send_rate), packets=f"{n.packets_sent:,}"))
            self.net_up_spark.add(n.send_rate)
            self.net_total_sub.setText(tr("mon_total_sub", down=gb(n.bytes_recv), up=gb(n.bytes_sent)))

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
                [(zone_label(name), value, f"{value:.0f}°C") for name, value in s.thermal.temperatures]
            )

        if s.errors:
            self.errors.setText(tr("mon_sensors", msg=" · ".join(f"{k}: {v}" for k, v in s.errors.items())))
            self.errors.setVisible(True)
        else:
            self.errors.setText("")
            self.errors.setVisible(False)
