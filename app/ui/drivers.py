from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
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

from app.drivers import DriverInfo, DriverService
from app.i18n import tr

from .components import attach_empty_hint
from .tasks import Task
from .theme import CARD_PADDING, PAGE_MARGINS

COLUMN_KEYS = (
    "drv_col_device",
    "drv_col_class",
    "drv_col_vendor",
    "drv_col_version",
    "drv_col_date",
    "drv_col_provider",
    "drv_col_status",
)


class DriversPage(QWidget):
    def __init__(self, service: DriverService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or DriverService()
        self._task: Task | None = None
        self._drivers: tuple[DriverInfo, ...] = ()
        self._errors: tuple[str, ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(10)

        title = QLabel(tr("drv_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("drv_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_button = QPushButton(tr("drv_refresh"))
        self.refresh_button.setProperty("primary", True)
        self.refresh_button.clicked.connect(self.start_load)
        toolbar.addWidget(self.refresh_button)
        self.status_label = QLabel(tr("drv_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        card = QFrame()
        card.setObjectName("card")
        body = QVBoxLayout(card)
        body.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        body.setSpacing(8)
        self.table = QTableWidget(0, len(COLUMN_KEYS))
        attach_empty_hint(self.table, "drv_empty")
        self.table.setHorizontalHeaderLabels([tr(key) for key in COLUMN_KEYS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        for col in range(len(COLUMN_KEYS) - 1):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(COLUMN_KEYS) - 1, QHeaderView.ResizeMode.Stretch)
        body.addWidget(self.table, 1)
        layout.addWidget(card, 1)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._drivers and self._task is None:
            self.start_load()

    def start_load(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("drv_loading"))
        self.refresh_button.setEnabled(False)
        self._task = Task(self._service.list_drivers, parent=self)
        self._task.done.connect(self._apply_drivers)
        self._task.failed.connect(self._on_failed)
        self._task.start()

    def _apply_drivers(self, result: object) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        if not isinstance(result, tuple) or len(result) != 2:
            self.status_label.setText(tr("drv_failed", msg=result))
            return
        drivers, errors = result
        if not isinstance(drivers, tuple) or not isinstance(errors, tuple):
            self.status_label.setText(tr("drv_failed", msg=result))
            return
        self._drivers = drivers
        self._errors = errors
        self._render()
        if errors:
            self.status_label.setText(f"{tr('drv_partial', count=len(errors))}: {errors[0]}")
        else:
            self.status_label.setText(tr("drv_loaded", count=len(drivers)))

    def _on_failed(self, message: str) -> None:
        self._task = None
        self.refresh_button.setEnabled(True)
        self.status_label.setText(tr("drv_failed", msg=message))

    def _render(self) -> None:
        self.table.setRowCount(len(self._drivers))
        for row, driver in enumerate(self._drivers):
            values = (
                driver.device,
                driver.device_class,
                driver.vendor,
                driver.driver_version,
                driver.driver_date,
                driver.provider,
                driver.status,
            )
            for col, text in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(text))

    def retranslate(self) -> None:
        self._title.setText(tr("drv_title"))
        self._desc.setText(tr("drv_desc"))
        self.refresh_button.setText(tr("drv_refresh"))
        self.table.setHorizontalHeaderLabels([tr(key) for key in COLUMN_KEYS])
        if self._drivers:
            self._render()
