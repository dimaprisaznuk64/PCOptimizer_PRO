from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from PySide6.QtCore import QEvent, QPoint, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .icons import nav_icon
from .sidebar import NAV_GROUPS, NAV_KEYS
from .theme import ICON_SIZE, ls


@dataclass(frozen=True)
class SearchEntry:
    key: str
    label: str
    group: str
    detail: str


def build_entries(recent: Sequence[str] = ()) -> list[SearchEntry]:
    labels = {key: tr(tr_key) for key, tr_key in NAV_KEYS}
    groups = {group: tr(tr_key) for group, tr_key, _ in NAV_GROUPS}
    group_of = {key: group for group, _, keys in NAV_GROUPS for key in keys}

    def make(key: str, group: str) -> SearchEntry:
        return SearchEntry(
            key=key,
            label=labels[key],
            group=group,
            detail=tr(f"tip_nav_{key}"),
        )

    entries = [make(key, groups[group_of[key]]) for key, _tr_key in NAV_KEYS]
    if recent:
        recent_label = tr("palette_recent")
        seen: set[str] = set()
        pinned: list[SearchEntry] = []
        for key in recent:
            if key in labels and key not in seen:
                seen.add(key)
                pinned.append(make(key, recent_label))
        entries = pinned + [entry for entry in entries if entry.key not in seen]
    return entries


def search_entries(entries: Sequence[SearchEntry], query: str) -> list[SearchEntry]:
    text = query.strip().casefold()
    if not text:
        return list(entries)
    terms = text.split()
    scored: list[tuple[int, int, SearchEntry]] = []
    for index, entry in enumerate(entries):
        label = entry.label.casefold()
        haystack = " ".join((label, entry.group.casefold(), entry.detail.casefold(), entry.key))
        if not all(term in haystack for term in terms):
            continue
        score = sum(2 for term in terms if term in label)
        if label.startswith(text):
            score += 3
        scored.append((score, index, entry))
    scored.sort(key=lambda row: (-row[0], row[1]))
    return [entry for _score, _index, entry in scored]


class CommandPalette(QFrame):
    selected = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("commandPalette")
        self.setWindowFlag(Qt.WindowType.Popup, True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedWidth(ls(460))

        self._entries: list[SearchEntry] = []
        self._recent: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ls(10), ls(10), ls(10), ls(8))
        layout.setSpacing(ls(8))

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(ls(8))
        self.search = QLineEdit()
        self.search.setObjectName("commandSearch")
        self.search.setPlaceholderText(tr("palette_placeholder"))
        self.search.setClearButtonEnabled(True)
        self.search.installEventFilter(self)
        search_row.addWidget(self.search)
        layout.addLayout(search_row)

        self.result_list = QListWidget()
        self.result_list.setObjectName("commandResults")
        self.result_list.setAlternatingRowColors(False)
        self.result_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.result_list.itemActivated.connect(self._accept_current)
        layout.addWidget(self.result_list)

        self.hint = QLabel(tr("palette_hint"))
        self.hint.setObjectName("commandHint")
        layout.addWidget(self.hint)

        self.search.textChanged.connect(self._populate)

    def open(self, recent: Sequence[str] = ()) -> None:
        self._recent = list(recent)
        self._entries = build_entries(self._recent)
        self.search.clear()
        self._populate("")
        self.show()
        self.raise_()
        self.activateWindow()
        parent = self.parentWidget()
        if parent is not None:
            self.move(
                parent.mapToGlobal(QPoint(0, 0))
                + QPoint((parent.width() - self.width()) // 2, ls(70))
            )
        self.search.setFocus()

    def retranslate(self) -> None:
        self.search.setPlaceholderText(tr("palette_placeholder"))
        self.hint.setText(tr("palette_hint"))
        self._entries = build_entries(self._recent)
        self._populate(self.search.text())

    def _populate(self, query: str) -> None:
        matches = search_entries(self._entries, query)
        self.result_list.clear()
        for entry in matches:
            item = QListWidgetItem(f"{entry.label}   ·   {entry.group}")
            item.setIcon(nav_icon(entry.key))
            item.setSizeHint(QSize(item.sizeHint().width(), ICON_SIZE + ls(14)))
            item.setData(Qt.ItemDataRole.UserRole, entry.key)
            item.setToolTip(entry.detail)
            self.result_list.addItem(item)
        if matches:
            self.result_list.setCurrentRow(0)
        else:
            empty = QListWidgetItem(tr("palette_empty"))
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            self.result_list.addItem(empty)

    def _accept_current(self, _item: QListWidgetItem | None = None) -> None:
        item = self.result_list.currentItem()
        if item is None:
            return
        key = item.data(Qt.ItemDataRole.UserRole)
        if not isinstance(key, str) or not key:
            return
        self.selected.emit(key)
        self.hide()

    def eventFilter(self, watched: QWidget, event: QEvent) -> bool:
        if watched is self.search and isinstance(event, QKeyEvent):
            key = event.key()
            if key in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                row = self.result_list.currentRow()
                step = -1 if key == Qt.Key.Key_Up else 1
                self.result_list.setCurrentRow(max(0, min(self.result_list.count() - 1, row + step)))
                return True
            if key in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
                self._accept_current()
                return True
            if key == Qt.Key.Key_Escape:
                self.hide()
                return True
        return super().eventFilter(watched, event)
