from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .theme import NAV_WIDTH

NAV_ITEMS: tuple[tuple[str, str], ...] = (
    ("dashboard", "Dashboard"),
    ("monitor", "System Monitor"),
    ("gpu", "GPU Monitor"),
    ("processes", "Processes"),
    ("cleaner", "Cleaner"),
    ("startup", "Startup Apps"),
    ("optimizer", "Optimizer"),
    ("gaming", "Gaming Mode"),
    ("network", "Network"),
    ("disk", "Disk & Storage"),
    ("health", "System Health"),
    ("settings", "Settings"),
)

_NAV_ICONS = {
    "dashboard": "▦",
    "monitor": "◉",
    "gpu": "▧",
    "processes": "≋",
    "cleaner": "✧",
    "startup": "↗",
    "optimizer": "⌁",
    "gaming": "◇",
    "network": "⇄",
    "disk": "▤",
    "health": "♡",
    "settings": "⚙",
}


class Sidebar(QWidget):
    navigated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(NAV_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        brand_block = QWidget()
        brand_block.setObjectName("brandBlock")
        brand_layout = QHBoxLayout(brand_block)
        brand_layout.setContentsMargins(18, 22, 14, 16)
        brand_layout.setSpacing(11)
        mark = QLabel("P")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand_layout.addWidget(mark, 0, Qt.AlignmentFlag.AlignTop)
        brand_text = QVBoxLayout()
        brand_text.setContentsMargins(0, 1, 0, 0)
        brand_text.setSpacing(2)
        brand = QLabel("PCOptimizer")
        brand.setObjectName("brand")
        accent = QLabel("PRO  /  DESKTOP")
        accent.setObjectName("brandAccent")
        brand_text.addWidget(brand)
        brand_text.addWidget(accent)
        brand_layout.addLayout(brand_text, 1)
        layout.addWidget(brand_block)

        subtitle = QLabel("Your PC. Under control.")
        subtitle.setObjectName("brandSub")
        subtitle.setContentsMargins(20, 0, 16, 14)
        layout.addWidget(subtitle)

        section_monitor = QLabel("OVERVIEW")
        section_monitor.setObjectName("navSection")
        layout.addWidget(section_monitor)

        self._buttons: dict[str, QPushButton] = {}
        for index, (key, label) in enumerate(NAV_ITEMS):
            if key == "cleaner":
                section = QLabel("TOOLS & PERFORMANCE")
                section.setObjectName("navSection")
                layout.addWidget(section)
            elif key == "network":
                section = QLabel("DIAGNOSTICS")
                section.setObjectName("navSection")
                layout.addWidget(section)
            elif key == "settings":
                section = QLabel("PREFERENCES")
                section.setObjectName("navSection")
                layout.addWidget(section)

            icon = _NAV_ICONS.get(key, "•")
            button = QPushButton(f"{icon}     {label}")
            button.setProperty("nav", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(39)
            button.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            layout.addWidget(button)
            self._buttons[key] = button

        layout.addStretch(1)

        footer = QWidget()
        footer.setObjectName("sidebarFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(0, 0, 0, 0)
        footer_layout.setSpacing(0)
        status = QLabel("●  APP READY")
        status.setObjectName("footerStatus")
        footer_layout.addWidget(status)
        version = QLabel("PCOptimizer PRO  ·  v1.0")
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
        for item in self._buttons.values():
            item.setChecked(item is button)
        self.navigated.emit(key)
