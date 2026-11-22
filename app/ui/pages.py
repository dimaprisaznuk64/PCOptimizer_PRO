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
        desc.setSizePolicy(desc.sizePolicy().horizontalPolicy(), desc.sizePolicy().verticalPolicy())
        layout.addWidget(desc)

        layout.addStretch(1)


def build_pages(
    settings=None,
    on_theme_applied=None,
    history=None,
    on_scale_applied=None,
    on_wizard_requested=None,
    on_dashboard_hidden_applied=None,
    on_monitor_profile_applied=None,
    monitor_profile: str = "BALANCED",
) -> list[tuple[str, QWidget]]:
    from app.monitor.profiles import profile_for
    from app.settings import SettingsService

    from .benchmarks import BenchmarksPage
    from .cleaner import CleanerPage
    from .dashboard import DashboardPage
    from .diagnostics import DiagnosticsPage
    from .disk import DiskPage
    from .drivers import DriversPage
    from .export_center import ExportCenterPage
    from .gaming import GamingPage
    from .gpu import GpuPage
    from .hardware import HardwarePage
    from .hardware_benchmark import HardwareBenchmarkPage
    from .health import HealthPage
    from .history import HistoryPage
    from .launcher import LauncherPage
    from .monitor import MonitorPage
    from .network import NetworkPage
    from .operations import OperationsPage
    from .optimizer import OptimizerPage
    from .processes import ProcessPage
    from .settings import SettingsPage
    from .startup import StartupPage
    from .system_report import SystemReportPage
    from .temperature import TemperaturePage

    if settings is None:
        settings = SettingsService()

    return [
        (
            "dashboard",
            DashboardPage(
                history=history,
                dashboard_hidden=str(settings.get("dashboard_hidden")),
            ),
        ),
        (
            "monitor",
            MonitorPage(process_refresh_ms=profile_for(monitor_profile).process_refresh_ms),
        ),
        ("temperature", TemperaturePage()),
        ("gpu", GpuPage()),
        ("hardware", HardwarePage()),
        ("processes", ProcessPage()),
        ("cleaner", CleanerPage()),
        ("startup", StartupPage()),
        ("optimizer", OptimizerPage()),
        ("gaming", GamingPage()),
        ("launcher", LauncherPage()),
        ("benchmarks", BenchmarksPage()),
        ("hardware_benchmark", HardwareBenchmarkPage()),
        ("history", HistoryPage(history)),
        ("network", NetworkPage()),
        ("disk", DiskPage()),
        ("diagnostics", DiagnosticsPage()),
        ("drivers", DriversPage()),
        ("system_report", SystemReportPage()),
        ("export_center", ExportCenterPage()),
        ("health", HealthPage()),
        ("operations", OperationsPage()),
        (
            "settings",
            SettingsPage(
                settings,
                on_theme_applied=on_theme_applied,
                on_scale_applied=on_scale_applied,
                on_wizard_requested=on_wizard_requested,
                on_dashboard_hidden_applied=on_dashboard_hidden_applied,
                on_monitor_profile_applied=on_monitor_profile_applied,
            ),
        ),
    ]
