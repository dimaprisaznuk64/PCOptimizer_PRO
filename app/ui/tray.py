from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon


def build_icon(color: str = "#4f8cff") -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(color))
    painter.drawEllipse(4, 4, 56, 56)
    painter.setBrush(QColor("#0f1115"))
    painter.drawEllipse(22, 22, 20, 20)
    painter.end()
    return QIcon(pixmap)


class AppTray(QObject):
    open_requested = Signal()
    gaming_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.tray = QSystemTrayIcon(icon or build_icon(), self)
        self.menu = QMenu()

        self.open_action: QAction = self.menu.addAction("Open PCOptimizer")
        self.open_action.triggered.connect(self.open_requested.emit)

        self.gaming_action: QAction = self.menu.addAction("Gaming Mode")
        self.gaming_action.triggered.connect(self.gaming_requested.emit)

        self.menu.addSeparator()
        self.quit_action: QAction = self.menu.addAction("Quit")
        self.quit_action.triggered.connect(self.quit_requested.emit)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.setToolTip("PCOptimizer PRO")

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
