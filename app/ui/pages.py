from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PlaceholderPage(QWidget):
    def __init__(self, title: str, description: str, milestone: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 44, 48, 44)
        layout.setSpacing(10)

        badge = QLabel(milestone)
        badge.setObjectName("pageBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(badge, 0, Qt.AlignmentFlag.AlignLeft)

        heading = QLabel(title)
        heading.setObjectName("pageTitle")
        layout.addWidget(heading)

        desc = QLabel(description)
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        desc.setMaximumWidth(560)
        layout.addWidget(desc)

        layout.addStretch(1)


def build_pages(settings=None, on_theme_applied=None) -> list[tuple[str, QWidget]]:
    from app.settings import SettingsService

    from .benchmarks import BenchmarksPage
    from .cleaner import CleanerPage
    from .dashboard import DashboardPage
    from .disk import DiskPage
    from .gaming import GamingPage
    from .gpu import GpuPage
    from .hardware import HardwarePage
    from .health import HealthPage
    from .launcher import LauncherPage
    from .monitor import MonitorPage
    from .network import NetworkPage
    from .optimizer import OptimizerPage
    from .processes import ProcessPage
    from .settings import SettingsPage
    from .startup import StartupPage

    if settings is None:
        settings = SettingsService()

    return [
        ("dashboard", DashboardPage()),
        ("monitor", MonitorPage()),
        ("gpu", GpuPage()),
        ("hardware", HardwarePage()),
        ("processes", ProcessPage()),
        ("cleaner", CleanerPage()),
        ("startup", StartupPage()),
        ("optimizer", OptimizerPage()),
        ("gaming", GamingPage()),
        ("launcher", LauncherPage()),
        ("benchmarks", BenchmarksPage()),
        ("network", NetworkPage()),
        ("disk", DiskPage()),
        ("health", HealthPage()),
        ("settings", SettingsPage(settings, on_theme_applied=on_theme_applied)),
    ]
