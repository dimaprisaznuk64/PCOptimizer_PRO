from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QPoint, Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu, QTableWidget

ContextLabel = str | Callable[[], str]
ContextCallback = Callable[[int], None]
ContextEnabled = Callable[[int], bool]
ContextEntry = tuple[ContextLabel, ContextCallback, ContextEnabled | None] | None


class TableContextMenu(QObject):
    def __init__(self, table: QTableWidget, parent: QObject | None = None) -> None:
        super().__init__(parent or table)
        self.table = table
        self._entries: list[ContextEntry] = []
        table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        table.customContextMenuRequested.connect(self.show)

    def add(
        self,
        label: ContextLabel,
        callback: ContextCallback,
        *,
        enabled: ContextEnabled | None = None,
    ) -> QAction:
        text = label() if callable(label) else label
        action = QAction(text, self.table)
        self._entries.append((label, callback, enabled))
        return action

    def separator(self) -> None:
        self._entries.append(None)

    def build_menu(self, row: int) -> QMenu:
        menu = QMenu(self.table)
        for entry in self._entries:
            if entry is None:
                menu.addSeparator()
                continue
            label, callback, enabled = entry
            action = menu.addAction(label() if callable(label) else label)
            action.setEnabled(row >= 0 and (enabled(row) if enabled else True))
            action.triggered.connect(lambda _checked=False, cb=callback, r=row: cb(r))
        return menu

    def show(self, pos: QPoint) -> None:
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        menu = self.build_menu(row)
        menu.exec(self.table.viewport().mapToGlobal(pos))


def copy_text(text: str) -> None:
    clipboard = QGuiApplication.clipboard()
    if clipboard is not None:
        clipboard.setText(text)
