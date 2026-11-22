from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QFont, QKeyEvent
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .activity import ActivityLog, Entry
from .icons import glyph
from .theme import ICON_SIZE, PADDING_MD, ls

FILTER_ALL = "all"
FILTER_UNREAD = "unread"
FILTER_ALERTS = "alerts"
_FILTERS = (FILTER_ALL, FILTER_UNREAD, FILTER_ALERTS)


def filter_entries(
    entries: Sequence[Entry],
    mode: str,
    is_read: Callable[[float], bool],
) -> list[Entry]:
    """Pure filter used by the notification center list."""
    if mode == FILTER_UNREAD:
        return [entry for entry in entries if not is_read(entry.ts)]
    if mode == FILTER_ALERTS:
        return [entry for entry in entries if entry.level in ("warn", "error")]
    return list(entries)


class NotificationCenter(QFrame):
    """Popup with the full activity feed, read state and quick filters."""

    def __init__(self, parent: QWidget | None = None, log: ActivityLog | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("notificationCenter")
        self.setWindowFlag(Qt.WindowType.Popup, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(ls(440))

        self._log = log or ActivityLog.instance()
        self._log.changed.connect(self._on_changed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ls(10), ls(10), ls(10), ls(8))
        layout.setSpacing(ls(8))

        head = QHBoxLayout()
        head.setSpacing(ls(8))
        self.title = QLabel(tr("notif_center_title"))
        self.title.setObjectName("notifCenterTitle")
        head.addWidget(self.title)
        head.addStretch(1)
        self.count = QLabel()
        self.count.setObjectName("notifCenterCount")
        head.addWidget(self.count)
        layout.addLayout(head)

        controls = QHBoxLayout()
        controls.setSpacing(ls(8))
        self.filter_combo = QComboBox()
        self.filter_combo.setObjectName("notifCenterFilter")
        self.filter_combo.addItems(
            [
                tr("notif_center_filter_all"),
                tr("notif_center_filter_unread"),
                tr("notif_center_filter_alerts"),
            ]
        )
        self.filter_combo.currentIndexChanged.connect(self._populate)
        controls.addWidget(self.filter_combo, 1)
        self.mark_all_button = QPushButton(tr("notif_center_mark_all"))
        self.mark_all_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_all_button.clicked.connect(self._log.mark_all_read)
        controls.addWidget(self.mark_all_button)
        self.clear_button = QPushButton(tr("notif_center_clear"))
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.clicked.connect(self._log.clear)
        controls.addWidget(self.clear_button)
        layout.addLayout(controls)

        self.result_list = QListWidget()
        self.result_list.setObjectName("notifCenterList")
        self.result_list.setAlternatingRowColors(False)
        self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.result_list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.result_list)

        self.hint = QLabel(tr("notif_center_hint"))
        self.hint.setObjectName("notifCenterHint")
        layout.addWidget(self.hint)

        self._populate()

    def open(self, anchor: QWidget | None = None) -> None:
        """Show the popup under the bell button, clamped to the current screen."""
        self._populate()
        self.show()
        self.raise_()
        self.activateWindow()
        if anchor is not None:
            point = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + ls(6)))
            screen = self.screen()
            if screen is not None:
                area = screen.availableGeometry()
                point.setX(max(area.left(), min(point.x(), area.right() - self.width())))
                point.setY(max(area.top(), min(point.y(), area.bottom() - self.height())))
            self.move(point)
        self.result_list.setFocus()

    def retranslate(self) -> None:
        current = self.filter_combo.currentIndex()
        self.title.setText(tr("notif_center_title"))
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems(
            [
                tr("notif_center_filter_all"),
                tr("notif_center_filter_unread"),
                tr("notif_center_filter_alerts"),
            ]
        )
        self.filter_combo.setCurrentIndex(max(0, min(current, self.filter_combo.count() - 1)))
        self.filter_combo.blockSignals(False)
        self.mark_all_button.setText(tr("notif_center_mark_all"))
        self.clear_button.setText(tr("notif_center_clear"))
        self.hint.setText(tr("notif_center_hint"))
        self._populate()

    def _on_changed(self) -> None:
        self._populate()

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        ts = item.data(Qt.ItemDataRole.UserRole)
        if isinstance(ts, float):
            self._log.mark_read(ts)
            self._populate()

    def _populate(self, *_args) -> None:
        from . import theme as th

        all_entries = self._log.entries(limit=30)
        mode = _FILTERS[max(0, min(self.filter_combo.currentIndex(), len(_FILTERS) - 1))]
        entries = filter_entries(all_entries, mode, self._log.is_read)
        self.count.setText(tr("notif_center_unread", count=self._log.unread_count()))
        self.result_list.clear()

        colors = {"ok": th.OK, "warn": th.WARN, "error": th.DANGER}
        glyphs = {"ok": "check", "warn": "warning", "error": "error"}
        for entry in entries:
            read = self._log.is_read(entry.ts)
            text = f"{entry.title}   ·   {entry.time_text}"
            if entry.detail:
                text += f"\n{entry.detail}"
            item = QListWidgetItem(text)
            item.setIcon(glyph(glyphs.get(entry.level, "info"), colors.get(entry.level, th.TEXT_DIM)))
            item.setSizeHint(QSize(item.sizeHint().width() + PADDING_MD, ICON_SIZE + ls(22)))
            item.setData(Qt.ItemDataRole.UserRole, entry.ts)
            item.setToolTip(entry.detail or entry.title)
            if not read:
                font = QFont(item.font())
                font.setBold(True)
                item.setFont(font)
            self.result_list.addItem(item)

        if not entries:
            empty = QListWidgetItem(tr("notif_center_empty"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.result_list.addItem(empty)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            return
        super().keyPressEvent(event)
