"""Compact combo boxes shared by the pages.

The native Qt popup grows to the full item list and follows the width of the
field, which looks like a full-screen dropdown when the field is wide.
`CompactCombo` keeps the popup a small, scrollable list anchored under the
field.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QSizePolicy,
)

COMBO_HEIGHT = 36
COMBO_WIDTH = 260
COMBO_WIDTH_WIDE = 300
MAX_VISIBLE_ROWS = 10


class CompactCombo(QComboBox):
    """Combo box whose popup stays a compact, scrollable list."""

    def showPopup(self) -> None:  # noqa: N802 - Qt naming
        super().showPopup()
        self._fit_popup()

    def _fit_popup(self) -> None:
        view = self.view()
        row = view.sizeHintForRow(0) or COMBO_HEIGHT
        target = row * max(self.maxVisibleItems(), 1) + 8
        view.setMaximumHeight(target)
        popup = view.window()
        if popup is None:
            return
        width = max(self.width(), self.view().sizeHintForColumn(0) + 40)
        popup.resize(width, target + 10)
        view.setGeometry(1, 5, max(popup.width() - 2, 1), target)

        screen = self.screen() or QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        height = popup.height()
        anchor = self.mapToGlobal(self.rect().bottomLeft())
        x = min(anchor.x(), available.right() - popup.width())
        below = anchor.y() + 2
        if below + height <= available.bottom():
            y = below
        else:
            y = max(available.top(), self.mapToGlobal(self.rect().topLeft()).y() - height - 2)
        popup.move(max(available.left(), x), y)


def tune_combo(combo: QComboBox, width: int = COMBO_WIDTH, expand: bool = False) -> QComboBox:
    """Keep a combo box compact and its popup readable."""
    combo.setFixedHeight(COMBO_HEIGHT)
    if expand:
        combo.setMinimumWidth(width)
        combo.setMaximumWidth(16777215)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    else:
        combo.setMinimumWidth(width)
        combo.setMaximumWidth(width)
        combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    combo.setMaxVisibleItems(MAX_VISIBLE_ROWS)
    view = combo.view()
    view.setMinimumWidth(width)
    if expand:
        view.setMaximumWidth(16777215)
    else:
        view.setMaximumWidth(width)
    view.setUniformItemSizes(True)
    view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    return combo
