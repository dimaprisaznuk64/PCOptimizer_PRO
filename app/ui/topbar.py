from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QVariantAnimation, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .icons import glyph
from .theme import ACCENT, TEXT, TEXT_DIM, fs


class TopBar(QWidget):
    """Frame header: HUD page index, greeting, system status, clock, quick actions."""

    settings_requested = Signal()
    notifications_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("topBar")
        self.setFixedHeight(68)
        self._last_title: str = tr("nav_dashboard")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)
        layout.setSpacing(14)

        # Avatar / badge (accent follows the active theme)
        avatar = QLabel()
        avatar.setPixmap(glyph("shield", ACCENT).scaled(24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        avatar.setFixedSize(36, 36)
        ac = QColor(ACCENT)
        avatar.setStyleSheet(
            f"background: rgba({ac.red()}, {ac.green()}, {ac.blue()}, 0.15);"
            f" border: 1px solid rgba({ac.red()}, {ac.green()}, {ac.blue()}, 0.4); border-radius: 10px;"
        )
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(avatar)

        # HUD index + page title / subtitle
        info_col = QVBoxLayout()
        info_col.setSpacing(2)
        info_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.index = QLabel("01")
        self.index.setObjectName("hudIndex")
        title_row.addWidget(self.index)
        self.title = QLabel(tr("topbar_greeting"))
        self.title.setObjectName("topBarTitle")
        self.title.setStyleSheet(f"font-size: {fs(14)}px; font-weight: 700; color: {TEXT};")
        title_row.addWidget(self.title)
        info_col.addLayout(title_row)

        self.subtitle = QLabel(tr("topbar_subtitle_ok"))
        self.subtitle.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
        info_col.addWidget(self.subtitle)
        layout.addLayout(info_col)

        layout.addStretch(1)

        # Status badge (kept for API compatibility) with a slow HUD "breath"
        self.status = QLabel(f"● {tr('status_healthy')}")
        self.status.setObjectName("topBarStatus")
        self.status.setFixedHeight(28)
        self._status_fx = QGraphicsOpacityEffect(self.status)
        self._status_fx.setOpacity(1.0)
        self.status.setGraphicsEffect(self._status_fx)
        self._pulse = QVariantAnimation(self)
        self._pulse.setDuration(1600)
        self._pulse.setLoopCount(-1)
        self._pulse.setKeyValues([(0.0, 1.0), (0.5, 0.62), (1.0, 1.0)])
        self._pulse.valueChanged.connect(self._status_fx.setOpacity)
        self._pulse.start()
        layout.addWidget(self.status, 0, Qt.AlignmentFlag.AlignVCenter)

        # Clock & Date
        from PySide6.QtCore import QTimer
        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        clock_box.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet(f"font-size: {fs(13)}px; font-weight: 700; color: {TEXT};")
        self.clock_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.date_label = QLabel()
        self.date_label.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock_label)
        clock_box.addWidget(self.date_label)
        layout.addLayout(clock_box)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_clock)
        self._timer.start(1000)
        self._update_clock()

        # Notification button
        self.notify_button = QPushButton()
        self.notify_button.setObjectName("topBarIcon")
        self.notify_button.setIcon(glyph("bell", TEXT_DIM))
        self.notify_button.setIconSize(QSize(18, 18))
        self.notify_button.setToolTip(tr("topbar_notify_tip"))
        self.notify_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.notify_button.setMenu(self._build_notify_menu())
        layout.addWidget(self.notify_button)

        # Settings button
        self.settings_button = QPushButton()
        self.settings_button.setObjectName("topBarIcon")
        self.settings_button.setIcon(glyph("settings", TEXT_DIM))
        self.settings_button.setIconSize(QSize(18, 18))
        self.settings_button.setToolTip(tr("topbar_settings_tip"))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.clicked.connect(self.settings_requested.emit)
        layout.addWidget(self.settings_button)

    def _update_clock(self) -> None:
        from PySide6.QtCore import QDateTime, QLocale

        now = QDateTime.currentDateTime()
        self.clock_label.setText(now.toString("HH:mm"))
        self.date_label.setText(QLocale().toString(now, "ddd d MMM"))

    def _build_notify_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.aboutToShow.connect(lambda m=menu: self._fill_notify_menu(m))
        self._fill_notify_menu(menu)
        return menu

    @staticmethod
    def _fill_notify_menu(menu: QMenu) -> None:
        """Latest notifications and activity events."""
        from .activity import ActivityLog

        menu.clear()
        entries = ActivityLog.instance().entries(limit=10)
        if not entries:
            action = menu.addAction(tr("topbar_notify_empty"))
            action.setEnabled(False)
            return

        for e in entries:
            mark = {"ok": "✓", "warn": "⚠", "error": "✕"}.get(e.level, "⚠")
            text = f"{mark}  {e.title}" + (f" — {e.detail}" if e.detail else "") + f"   {e.time_text}"
            menu.addAction(text)

        menu.addSeparator()
        clear_action = menu.addAction(tr("topbar_notify_clear"))
        clear_action.triggered.connect(ActivityLog.instance().clear)

    def retranslate(self) -> None:
        self.notify_button.setToolTip(tr("topbar_notify_tip"))
        self.settings_button.setToolTip(tr("topbar_settings_tip"))
        self.notify_button.setMenu(self._build_notify_menu())
        self.set_title(self._last_title or tr("nav_dashboard"))

    def set_title(self, text: str) -> None:
        self._last_title = text
        self.title.setText(text)
        self.subtitle.setText(tr("topbar_subtitle_page"))
        self.title.setToolTip(text)

    def set_page_index(self, number: int, total: int = 99) -> None:
        """HUD slot number of the current page (e.g. 03)."""
        self.index.setText(f"{number:02d}/{total:02d}" if total <= 20 else f"{number:02d}")

    def set_status(self, text: str, level: str = "ok") -> None:
        self.status.setText(f"● {text}")
        if self.status.property("level") != level:
            self.status.setProperty("level", level)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)