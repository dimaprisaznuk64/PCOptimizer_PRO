from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from .theme import ACCENT, PANEL
from app.i18n import tr


def build_icon(color: str = "") -> QIcon:
    from .icons import app_icon

    return app_icon(color)


class AppTray(QObject):
    open_requested = Signal()
    gaming_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(icon or build_icon(), self)
        self.menu = QMenu()

        self.open_action: QAction = self.menu.addAction(tr("tray_open"))
        self.open_action.triggered.connect(self.open_requested.emit)

        self.gaming_action: QAction = self.menu.addAction(tr("tray_gaming"))
        self.gaming_action.triggered.connect(self.gaming_requested.emit)

        self.menu.addSeparator()
        self.quit_action: QAction = self.menu.addAction(tr("tray_quit"))
        self.quit_action.triggered.connect(self.quit_requested.emit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.setToolTip("PCOptimizer PRO")

    def retranslate(self) -> None:
        """Refresh context-menu texts after a language change."""
        self.open_action.setText(tr("tray_open"))
        self.gaming_action.setText(tr("tray_gaming"))
        self.quit_action.setText(tr("tray_quit"))

    @property
    def visible(self) -> bool:
        return self.tray.isVisible()

    def show(self) -> None:
        self.tray.show()

    def hide(self) -> None:
        self.tray.hide()

    def set_tooltip(self, text: str) -> None:
        self.tray.setToolTip(text)

    def show_message(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        triggers = (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        )
        if reason in triggers:
            self.open_requested.emit()
