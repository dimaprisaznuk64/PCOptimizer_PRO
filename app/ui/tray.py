from __future__ import annotations

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMenu,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

TOAST_TIMEOUT_MS = 9000


def build_icon(color: str = "") -> QIcon:
    from .icons import app_icon

    return app_icon(color)


class _Toast(QWidget):
    """Silent in-app notification card (no Windows tray sound)."""

    clicked = Signal()

    def __init__(self) -> None:
        super().__init__(
            None,
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._card = QFrame(self)
        self._card.setObjectName("toastCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._card)

        inner = QVBoxLayout(self._card)
        inner.setContentsMargins(16, 12, 16, 12)
        inner.setSpacing(4)
        self._title = QLabel(self._card)
        self._title.setObjectName("toastTitle")
        self._body = QLabel(self._card)
        self._body.setObjectName("toastBody")
        self._body.setWordWrap(True)
        self._body.setMaximumWidth(340)
        inner.addWidget(self._title)
        inner.addWidget(self._body)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self.hide)

    def _apply_style(self) -> None:
        from . import theme

        self._card.setStyleSheet(
            f"""
            QFrame#toastCard {{
                background: {theme.PANEL_ALT};
                border: 1px solid {theme.ACCENT};
                border-radius: {theme.RADIUS_SM}px;
            }}
            QLabel#toastTitle {{
                color: {theme.TEXT};
                font-family: {theme.FONT_UI};
                font-size: {theme.T_SMALL}px;
                font-weight: 600;
            }}
            QLabel#toastBody {{
                color: {theme.TEXT_DIM};
                font-family: {theme.FONT_UI};
                font-size: {theme.T_CAPTION}px;
            }}
            """
        )

    def show_message(self, title: str, body: str) -> None:
        self._apply_style()
        self._title.setText(title)
        current = self._body.text()
        if self.isVisible() and current:
            self._body.setText(f"{current}\n{body}")
        else:
            self._body.setText(body)
        self.adjustSize()
        self._place()
        self.show()
        self.raise_()
        self._timer.start(TOAST_TIMEOUT_MS)

    def _place(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        self.move(
            area.right() - self.width() - 24,
            area.bottom() - self.height() - 24,
        )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt naming
        self.clicked.emit()
        self.hide()


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
        self._toast: _Toast | None = None

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
        """Show a notification card without playing the Windows alert sound."""
        if self._toast is None:
            self._toast = _Toast()
            self._toast.clicked.connect(self.open_requested.emit)
        self._toast.show_message(title, message)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        triggers = (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        )
        if reason in triggers:
            self.open_requested.emit()
