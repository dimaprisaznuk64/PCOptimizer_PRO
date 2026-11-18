from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.processes.service import ProcessService
from app.sensors import Snapshot

from .components import (
    Bar,
    CardPanel,
    CardTitleLabel,
    Sparkline,
    align_numeric_headers,
    attach_empty_hint,
)
from .format import gb, rate, temp_text, zone_label
from .tasks import Task
from .theme import ACCENT, ACCENT_HOVER, CARD_PADDING, DANGER, OK, PAGE_MARGINS, PAGE_SPACING


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
        self._layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        self._layout.setSpacing(8)
        label = CardTitleLabel(title)
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
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        process_service: ProcessService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._process_service = process_service or ProcessService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)

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
        self.proc_card = self._build_process_card()

        grid.addWidget(cpu_card, 0, 0, 1, 4)
        grid.addWidget(mem_card, 1, 0, 1, 2)
        grid.addWidget(net_card, 1, 2, 1, 2)
        grid.addWidget(self.disks, 2, 0, 1, 2)
        grid.addWidget(self.thermals, 2, 2, 1, 2)
        grid.addWidget(self.proc_card, 3, 0, 1, 4)
        for col in range(4):
            grid.setColumnStretch(col, 1)
        grid.setRowStretch(0, 0)
        grid.setRowStretch(1, 1)
        grid.setRowStretch(2, 1)
        grid.setRowStretch(3, 1)
        layout.addLayout(grid, 1)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

        self._proc_task: Task | None = None
        self._proc_error_msg = ""
        self._proc_timer = QTimer(self)
        self._proc_timer.setInterval(5000)
        self._proc_timer.timeout.connect(self.refresh_memory_processes)

        self._cpu_peak = 0.0
        self._mem_peak = 0.0
        self._temp_peak: float | None = None
        self._commit_used: int | None = None
        self._commit_limit: int | None = None

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

        core_label = CardTitleLabel(tr("mon_per_core"))
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
        self.commit_sub = QLabel("")
        self.commit_sub.setObjectName("cardSub")
        self.commit_sub.setVisible(False)
        card.body.addWidget(self.commit_sub)
        self._mem_card = card
        return card

    def _build_process_card(self) -> QFrame:
        card = _Card(tr("mon_top_processes"))
        self.proc_table = QTableWidget(0, 3)
        self.proc_table.setObjectName("processMemoryTable")
        self.proc_table.setHorizontalHeaderLabels(
            [
                tr("mon_proc_col_name"),
                tr("mon_proc_col_memory"),
                tr("mon_proc_col_percent"),
            ]
        )
        align_numeric_headers(self.proc_table, (1, 2))
        header = self.proc_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.proc_table.verticalHeader().setVisible(False)
        self.proc_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.proc_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.proc_table.setMinimumHeight(170)
        card.body.addWidget(self.proc_table)
        self.proc_empty = attach_empty_hint(self.proc_table, "mon_proc_empty")
        self.proc_status = QLabel("")
        self.proc_status.setObjectName("errorLine")
        self.proc_status.setVisible(False)
        card.body.addWidget(self.proc_status)
        self._proc_card = card
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

    def _update_commit_label(self) -> None:
        if self._commit_used is None or self._commit_limit is None:
            self.commit_sub.setText("")
            self.commit_sub.setVisible(False)
            return
        self.commit_sub.setText(
            tr("mon_commit", used=gb(self._commit_used), limit=gb(self._commit_limit))
        )
        self.commit_sub.setVisible(True)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._proc_timer.isActive():
            self.refresh_memory_processes()
            self._proc_timer.start()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._proc_timer.stop()

    def refresh_memory_processes(self) -> None:
        if self._proc_task is not None and self._proc_task.isRunning():
            return
        task = Task(self._process_service.top_by_memory, self)
        self._proc_task = task
        task.done.connect(self._render_top_processes)
        task.failed.connect(self._show_process_error)
        task.finished.connect(self._clear_process_task)
        task.finished.connect(task.deleteLater)
        task.start()

    def _clear_process_task(self) -> None:
        self._proc_task = None

    def _render_top_processes(self, rows) -> None:
        self.proc_table.setRowCount(0)
        for row_index, proc in enumerate(rows or []):
            self.proc_table.insertRow(row_index)
            values = (proc.name, gb(proc.memory_bytes), f"{proc.memory_percent:.1f}%")
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if col:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.proc_table.setItem(row_index, col, item)
        self._proc_error_msg = ""
        self.proc_status.setText("")
        self.proc_status.setVisible(False)

    def _show_process_error(self, msg: str) -> None:
        self._proc_error_msg = msg
        self.proc_status.setText(tr("mon_proc_failed", msg=msg))
        self.proc_status.setVisible(True)

    def _set_process_headers(self) -> None:
        self.proc_table.setHorizontalHeaderLabels(
            [
                tr("mon_proc_col_name"),
                tr("mon_proc_col_memory"),
                tr("mon_proc_col_percent"),
            ]
        )
        align_numeric_headers(self.proc_table, (1, 2))

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("mon_title"))
        self._desc.setText(tr("mon_desc"))
        self._cpu_card.set_title(tr("dash_cpu"))
        self._mem_card.set_title(tr("dash_mem"))
        self._net_card.set_title(tr("dash_net"))
        self._proc_card.set_title(tr("mon_top_processes"))
        self._set_process_headers()
        if self._proc_error_msg:
            self.proc_status.setText(tr("mon_proc_failed", msg=self._proc_error_msg))
        self._core_title.setText(tr("mon_per_core"))
        self.disks.set_title(tr("mon_storage"))
        self.thermals.set_title(
            tr("mon_thermals")
            + (tr("mon_peak", value=temp_text(self._temp_peak)) if self._temp_peak is not None else "")
        )
        self._update_commit_label()

    def apply_snapshot(self, s: Snapshot) -> None:
        if s.cpu:
            c = s.cpu
            freq = tr("mon_freq_base", mhz=f"{c.freq_mhz:.0f}") if c.freq_mhz else ""
            self._cpu_peak = max(self._cpu_peak, c.percent)
            self.cpu_value.setText(f"{c.percent:.0f}%")
            self.cpu_sub.setText(
                tr("mon_cores", physical=c.physical_cores, logical=c.logical_cores)
                + freq
                + tr("mon_peak", value=f"{self._cpu_peak:.0f}%")
            )
            self.cpu_spark.add(c.percent)
            self.cores.set_percents(c.per_core)

        if s.memory:
            m = s.memory
            self._mem_peak = max(self._mem_peak, m.percent)
            self.mem_value.setText(f"{m.percent:.0f}%")
            self.mem_sub.setText(
                tr("mon_used_total", used=gb(m.used), total=gb(m.total), available=gb(m.available))
                + tr("mon_peak", value=f"{self._mem_peak:.0f}%")
            )
            self.mem_bar.set_percent(m.percent)
            self.mem_bar.set_color(_level_color(m.percent))
            self.mem_spark.add(m.percent)
            self.swap_sub.setText(tr("mon_swap", used=gb(m.swap_used), total=gb(m.swap_total), pct=m.swap_percent))
            self.swap_bar.set_percent(m.swap_percent)
            self.swap_bar.set_color(_level_color(m.swap_percent))
            self._commit_used = m.commit_used
            self._commit_limit = m.commit_limit
            self._update_commit_label()

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
            temperatures = tuple(value for _, value in s.thermal.temperatures)
            if temperatures:
                self._temp_peak = max(self._temp_peak or max(temperatures), max(temperatures))
            self.thermals.set_rows(
                [(zone_label(name), value, f"{value:.0f}°C") for name, value in s.thermal.temperatures]
            )
            self.thermals.set_title(
                tr("mon_thermals")
                + (tr("mon_peak", value=temp_text(self._temp_peak)) if self._temp_peak is not None else "")
            )

        shown_errors = {k: v for k, v in s.errors.items() if k != "thermal"}
        if shown_errors:
            self.errors.setText(tr("mon_sensors", msg=" · ".join(f"{k}: {v}" for k, v in shown_errors.items())))
            self.errors.setVisible(True)
        else:
            self.errors.setText("")
            self.errors.setVisible(False)
