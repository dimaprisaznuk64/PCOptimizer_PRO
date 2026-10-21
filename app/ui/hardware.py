from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.hardware import HardwareReport, HardwareService
from app.i18n import tr

from .components import CardTitleLabel, ValueListCard, attach_empty_hint
from .format import size as fmt_size
from .tasks import Task
from .theme import CARD_PADDING

MEM_COLUMN_KEYS = (
    "hw_col_slot",
    "hw_col_capacity",
    "hw_col_speed",
    "hw_col_type",
    "hw_col_manufacturer",
    "hw_col_part",
)
DISK_COLUMN_KEYS = (
    "hw_col_model",
    "hw_col_size",
    "hw_col_interface",
    "hw_col_media",
    "hw_col_serial",
)

_MISSING = "—"

# Fixed column widths keep the tables shrinkable on narrow windows - with
# ``ResizeToContents`` a long serial or part number would force the page
# into a horizontal scrollbar. The column marked "stretch" takes the slack.
_MEM_WIDTHS = {0: 62, 1: 92, 2: 84, 3: 84, 4: "stretch", 5: 120}
_DISK_WIDTHS = {0: "stretch", 1: 92, 2: 96, 3: 84, 4: 120}


def _val(text: str) -> str:
    return text if text else _MISSING


def _mhz(value: int) -> str:
    return _MISSING if not value else f"{value} MHz"


class HardwarePage(QWidget):
    def __init__(self, service: HardwareService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or HardwareService()
        self._task: Task | None = None
        self._report: HardwareReport | None = None
        self._loaded = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("hw_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("hw_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_button = QPushButton(tr("hw_refresh"))
        self.refresh_button.setProperty("primary", True)
        self.refresh_button.clicked.connect(self.start_load)
        toolbar.addWidget(self.refresh_button)
        self.status_label = QLabel(tr("hw_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        container = QWidget()
        container.setObjectName("page")
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        self.system_card = ValueListCard(tr("hw_system"))
        self.cpu_card = ValueListCard(tr("hw_cpu"))
        self.memory_card = ValueListCard(tr("hw_memory"))
        self.gpu_card = ValueListCard(tr("hw_gpu"))
        self.board_card = ValueListCard(tr("hw_board"))
        self.bios_card = ValueListCard(tr("hw_bios"))
        grid.addWidget(self.system_card, 0, 0)
        grid.addWidget(self.cpu_card, 0, 1)
        grid.addWidget(self.memory_card, 1, 0)
        grid.addWidget(self.gpu_card, 1, 1)
        grid.addWidget(self.board_card, 2, 0)
        grid.addWidget(self.bios_card, 2, 1)

        self.modules_card, self.modules_title, self.modules_table = self._make_table(
            "hw_modules", MEM_COLUMN_KEYS, "hw_empty", _MEM_WIDTHS
        )
        grid.addWidget(self.modules_card, 3, 0, 1, 2)

        self.disks_card, self.disks_title, self.disks_table = self._make_table(
            "hw_disks", DISK_COLUMN_KEYS, "hw_empty", _DISK_WIDTHS
        )
        grid.addWidget(self.disks_card, 4, 0, 1, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(5, 1)
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

    # ---------- table card helper ----------

    def _make_table(
        self,
        title_key: str,
        column_keys: tuple[str, ...],
        hint: str,
        widths: dict[int, int | str],
    ):
        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        body.setSpacing(8)

        title = CardTitleLabel(tr(title_key))
        body.addWidget(title)

        table = QTableWidget(0, len(column_keys))
        attach_empty_hint(table, hint)
        table.setHorizontalHeaderLabels([tr(k) for k in column_keys])
        table.verticalHeader().setVisible(False)
        table.setShowGrid(False)
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setMinimumHeight(120)
        header = table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in range(len(column_keys)):
            width = widths.get(col, 110)
            if width == "stretch":
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.Interactive)
                table.setColumnWidth(col, int(width))
        body.addWidget(table, 1)
        return card, title, table

    # ---------- loading ----------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded and self._task is None:
            self.start_load()

    def start_load(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("hw_loading"))
        self.refresh_button.setEnabled(False)
        self._task = Task(self._service.report, parent=self)
        self._task.done.connect(self._apply_report)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _apply_report(self, report: object) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        if not isinstance(report, HardwareReport):
            self.status_label.setText(tr("hw_failed", msg=report))
            return
        self._report = report
        self._loaded = True
        self._render()
        if report.errors:
            self.status_label.setText(tr("hw_partial", count=len(report.errors)))
        else:
            self.status_label.setText(tr("hw_loaded"))

    def _on_failed(self, message: str) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        self.status_label.setText(tr("hw_failed", msg=message))

    # ---------- rendering ----------

    def _render(self) -> None:
        report = self._report
        if report is None:
            return
        self._render_system(report)
        self._render_cpu(report)
        self._render_memory(report)
        self._render_gpus(report)
        self._render_board(report)
        self._render_bios(report)
        self._render_modules(report)
        self._render_disks(report)

    def _render_system(self, report: HardwareReport) -> None:
        system = report.system
        os_text = system.os_name
        if system.os_version:
            os_text = f"{os_text} ({system.os_version})" if os_text else system.os_version
        self.system_card.set_values([
            (tr("hw_manufacturer"), _val(system.manufacturer)),
            (tr("hw_model"), _val(system.model)),
            (tr("hw_os"), _val(os_text)),
            (tr("hw_arch"), _val(system.architecture)),
            (tr("hw_hostname"), _val(system.hostname)),
        ])

    def _render_cpu(self, report: HardwareReport) -> None:
        cpu = report.cpu
        if cpu is None:
            self.cpu_card.set_values([])
            return
        cache = f"L2 {cpu.l2_kb} KB · L3 {cpu.l3_kb} KB" if (cpu.l2_kb or cpu.l3_kb) else _MISSING
        self.cpu_card.set_values([
            (tr("hw_model"), _val(cpu.name)),
            (tr("hw_vendor"), _val(cpu.manufacturer)),
            (tr("hw_cores"), str(cpu.physical_cores) if cpu.physical_cores else _MISSING),
            (tr("hw_threads"), str(cpu.logical_cores) if cpu.logical_cores else _MISSING),
            (tr("hw_max_clock"), _mhz(cpu.max_clock_mhz)),
            (tr("hw_current_clock"), _mhz(cpu.current_clock_mhz)),
            (tr("hw_socket"), _val(cpu.socket)),
            (tr("hw_cache"), cache),
        ])

    def _render_memory(self, report: HardwareReport) -> None:
        memory = report.memory
        slots = (
            f"{memory.slots_used} / {memory.slots_total}" if memory.slots_total else str(memory.slots_used)
        )
        self.memory_card.set_values([
            (tr("hw_total_memory"), fmt_size(memory.total_bytes) if memory.total_bytes else _MISSING),
            (tr("hw_slots"), slots),
            (tr("hw_speed"), _mhz(memory.speed_mhz)),
        ])

    def _render_gpus(self, report: HardwareReport) -> None:
        items: list[tuple[str, str]] = []
        seen: dict[str, int] = {}
        for gpu in report.gpus:
            name = _val(gpu.name)
            seen[name] = seen.get(name, 0) + 1
            key = name if seen[name] == 1 else f"{name} #{seen[name]}"
            parts = [fmt_size(gpu.vram_bytes) if gpu.vram_bytes else _MISSING]
            if gpu.driver_version:
                parts.append(f"{tr('hw_driver')}: {gpu.driver_version}")
            if gpu.vendor:
                parts.append(gpu.vendor)
            items.append((key, " · ".join(parts)))
        self.gpu_card.set_values(items)

    def _render_board(self, report: HardwareReport) -> None:
        board = report.board
        self.board_card.set_values([
            (tr("hw_manufacturer"), _val(board.manufacturer)),
            (tr("hw_board_product"), _val(board.product)),
            (tr("hw_version"), _val(board.version)),
            (tr("hw_serial"), _val(board.serial)),
        ])

    def _render_bios(self, report: HardwareReport) -> None:
        bios = report.bios
        self.bios_card.set_values([
            (tr("hw_vendor"), _val(bios.vendor)),
            (tr("hw_version"), _val(bios.version)),
            (tr("hw_bios_date"), _val(bios.date)),
        ])

    def _render_modules(self, report: HardwareReport) -> None:
        modules = report.memory.modules
        self.modules_table.setRowCount(len(modules))
        for row, module in enumerate(modules):
            values = (
                module.slot,
                fmt_size(module.capacity_bytes) if module.capacity_bytes else _MISSING,
                _mhz(module.speed_mhz),
                _val(module.memory_type),
                _val(module.manufacturer),
                _val(module.part_number),
            )
            for col, text in enumerate(values):
                self.modules_table.setItem(row, col, QTableWidgetItem(str(text)))

    def _render_disks(self, report: HardwareReport) -> None:
        disks = report.disks
        self.disks_table.setRowCount(len(disks))
        for row, disk in enumerate(disks):
            values = (
                _val(disk.model),
                fmt_size(disk.size_bytes) if disk.size_bytes else _MISSING,
                _val(disk.interface),
                _val(disk.media),
                _val(disk.serial),
            )
            for col, text in enumerate(values):
                self.disks_table.setItem(row, col, QTableWidgetItem(str(text)))

    # ---------- i18n ----------

    def retranslate(self) -> None:
        self._title.setText(tr("hw_title"))
        self._desc.setText(tr("hw_desc"))
        self.refresh_button.setText(tr("hw_refresh"))
        self.system_card.set_title(tr("hw_system"))
        self.cpu_card.set_title(tr("hw_cpu"))
        self.memory_card.set_title(tr("hw_memory"))
        self.gpu_card.set_title(tr("hw_gpu"))
        self.board_card.set_title(tr("hw_board"))
        self.bios_card.set_title(tr("hw_bios"))
        self.modules_title.setText(tr("hw_modules").upper())
        self.disks_title.setText(tr("hw_disks").upper())
        self.modules_table.setHorizontalHeaderLabels([tr(k) for k in MEM_COLUMN_KEYS])
        self.disks_table.setHorizontalHeaderLabels([tr(k) for k in DISK_COLUMN_KEYS])
        if self._report is not None:
            self._render()
