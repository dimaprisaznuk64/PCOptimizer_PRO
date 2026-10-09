from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import NAV_WIDTH

NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("dashboard", "Dashboard"),
    ("monitor", "System Monitor"),
    ("gpu", "GPU Monitor"),
    ("processes", "Processes"),
    ("cleaner", "Cleaner"),
    ("startup", "Startup"),
    ("optimizer", "Optimizer"),
    ("gaming", "Gaming Mode"),
    ("network", "Network"),
    ("disk", "Disk"),
    ("health", "Health Score"),
    ("settings", "Settings"),
)


class Sidebar(QWidget):
    navigated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(NAV_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand = QLabel("PCOptimizer PRO")
        brand.setObjectName("brand")
        layout.addWidget(brand)

        subtitle = QLabel("Windows toolkit")
        subtitle.setObjectName("brandSub")
        layout.addWidget(subtitle)

        self._buttons: dict[str, QPushButton] = {}
        for key, label in NAV_ITEMS:
            button = QPushButton(label)
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            layout.addWidget(button)
            self._buttons[key] = button

        layout.addStretch(1)

        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        version = QLabel("v0.1.0 · M14")
        version.setObjectName("footerText")
        footer_layout.addWidget(version)
        layout.addWidget(footer)

        self.select("dashboard")

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._buttons)

    def select(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        button.setChecked(True)
        self.navigated.emit(key)
