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
MAX_VISIBLE_ROWS = 12
MIN_ROW_HEIGHT = 30
MAX_POPUP_WIDTH = 450


class CompactCombo(QComboBox):
    """Combo box whose popup stays a compact, scrollable list."""

    def showPopup(self) -> None:  # noqa: N802 - Qt naming
        super().showPopup()
        self._fit_popup()

    def _fit_popup(self) -> None:
        view = self.view()
        # Ensure the row height is calculated correctly for the delegate
        row = view.sizeHintForRow(0) or COMBO_HEIGHT
        if row < MIN_ROW_HEIGHT:  # swatch delegates need a taller row
            row = MIN_ROW_HEIGHT
        row = max(row, view.fontMetrics().height() + 12)

        target = row * max(self.maxVisibleItems(), 1) + 10
        view.setMaximumHeight(target)

        popup = view.window()
        if popup is None:
            return

        # Keep the popup compact: never wider than the field and never wider
        # than MAX_POPUP_WIDTH, even on very wide windows.
        field_w = self.width()
        if field_w <= 0:
            field_w = self.sizeHint().width() or COMBO_WIDTH
        content_width = self.view().sizeHintForColumn(0) + 48
        width = min(field_w, content_width)
        width = min(width, MAX_POPUP_WIDTH)
        width = max(1, width)

        # Never let the popup grow wider than the available screen width.
        screen = self.screen() or QApplication.primaryScreen()
        if screen is not None:
            available = screen.availableGeometry()
            width = min(width, available.width() - 16)
            width = min(width, available.width() - 8)

        popup.setMinimumWidth(width)
        popup.setMaximumWidth(min(field_w, MAX_POPUP_WIDTH))
        popup.resize(width, target + 12)
        popup.setFixedWidth(min(field_w, MAX_POPUP_WIDTH))
        view.setGeometry(1, 6, max(popup.width() - 2, 1), target)
        view.setMaximumWidth(popup.width() - 2)
        view.setMinimumWidth(popup.width() - 2)

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
