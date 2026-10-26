"""Tests for the compact combo boxes and the theme swatch delegate."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtWidgets import QApplication, QStyleOptionViewItem  # noqa: E402

from app.ui.combos import (  # noqa: E402
    COMBO_HEIGHT,
    MAX_POPUP_WIDTH,
    MAX_VISIBLE_ROWS,
    MIN_ROW_HEIGHT,
    CompactCombo,
    tune_combo,
)
from app.ui.theme_picker import ThemeSwatchDelegate  # noqa: E402


@pytest.fixture()
def qapp():
    app = QApplication.instance() or QApplication([])
    # Keep metrics deterministic across test order / DPI emulation
    app.setFont(QFont("Segoe UI", 9))
    yield app
    app.processEvents()


def _make_combo(qapp, items: int = 29) -> CompactCombo:
    combo = CompactCombo()
    combo.setFont(QFont("Segoe UI", 9))
    for i in range(items):
        combo.addItem(f"Item {i}")
    tune_combo(combo, 280)
    combo.show()
    qapp.processEvents()
    qapp.processEvents()
    return combo


def test_combo_has_fixed_compact_size(qapp):
    combo = _make_combo(qapp)
    assert combo.height() == COMBO_HEIGHT
    assert combo.width() == 280
    assert combo.maxVisibleItems() == MAX_VISIBLE_ROWS


def test_combo_popup_is_bounded_and_anchored_under_the_field(qapp):
    combo = _make_combo(qapp)
    combo.setFont(QFont("Segoe UI", 9))
    combo.setFixedWidth(280)
    combo.show()
    qapp.processEvents()
    combo.showPopup()
    for _ in range(5):
        qapp.processEvents()

    popup = combo.view().window()
    view = combo.view()
    # The implementation floors the row height for swatch delegates, so the
    # bound must use the same floor (font size varies between test runs).
    row = max(view.sizeHintForRow(0), MIN_ROW_HEIGHT)
    row = max(row, view.fontMetrics().height() + 12)
    # The popup shows a few rows only - not the whole list.
    assert popup.height() <= row * MAX_VISIBLE_ROWS + 28
    assert abs(popup.width() - 280) <= 8

    # Anchored under the field, not at the top-left corner of the screen.
    anchor = combo.mapToGlobal(combo.rect().bottomLeft())
    popup_pos = popup.mapToGlobal(popup.rect().topLeft())
    assert abs(popup_pos.x() - anchor.x()) <= 6
    assert popup_pos.y() >= anchor.y() - 6
    combo.hidePopup()
    qapp.processEvents()


def test_combo_popup_does_not_stretch_to_a_wide_field(qapp):
    combo = _make_combo(qapp)
    combo.setFixedWidth(1200)
    combo.showPopup()
    qapp.processEvents()

    popup = combo.view().window()
    assert popup.width() <= MAX_POPUP_WIDTH + 8
    assert popup.width() <= combo.width()
    combo.hidePopup()


def test_combo_popup_scrolls_the_rest_of_the_list(qapp):
    combo = _make_combo(qapp, items=29)
    combo.showPopup()
    qapp.processEvents()
    view = combo.view()
    # More items than visible -> a scrollbar is offered.
    assert view.verticalScrollBar().maximum() > 0
    combo.hidePopup()


def test_swatch_delegate_reports_a_wider_item(qapp):
    combo = CompactCombo()
    combo.addItem("Graphite", "GRAPHITE")
    tune_combo(combo, 280)
    delegate = ThemeSwatchDelegate(combo)
    combo.setItemDelegate(delegate)
    combo.show()
    qapp.processEvents()

    index = combo.model().index(0, 0)
    option = QStyleOptionViewItem()
    option.initFrom(combo)
    option.fontMetrics = combo.fontMetrics()
    hint = delegate.sizeHint(option, index)
    plain = combo.fontMetrics().horizontalAdvance("Graphite")
    assert hint.width() > plain
    assert hint.height() >= 30


def test_swatch_delegate_uses_the_theme_palette(qapp):
    from app.ui import theme

    combo = CompactCombo()
    combo.addItem("Graphite", "GRAPHITE")
    tune_combo(combo, 280)
    delegate = ThemeSwatchDelegate(combo)
    combo.setItemDelegate(delegate)
    combo.show()
    qapp.processEvents()

    index = combo.model().index(0, 0)
    assert index.data(Qt.ItemDataRole.UserRole) == "GRAPHITE"
    assert "GRAPHITE" in theme.PALETTES


def _render_delegate_row(combo, delegate, row: int, width: int = 220, height: int = 30):
    from PySide6.QtCore import QRect
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtWidgets import QStyle


    index = combo.model().index(row, 0)
    option = QStyleOptionViewItem()
    option.initFrom(combo.view())
    option.rect = QRect(0, 0, width, height)
    option.font = combo.font()
    option.fontMetrics = combo.fontMetrics()
    option.state = QStyle.StateFlag.State_Enabled
    image = QImage(width, height, QImage.Format.Format_ARGB32)
    image.fill(0)
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()
    return image


def _accent_pixels_on_the_right(image) -> int:
    from PySide6.QtGui import QColor

    from app.ui import theme

    accent = QColor(theme.ACCENT)
    count = 0
    for x in range(image.width() - 26, image.width() - 4):
        for y in range(image.height()):
            color = image.pixelColor(x, y)
            if (
                abs(color.red() - accent.red()) <= 30
                and abs(color.green() - accent.green()) <= 30
                and abs(color.blue() - accent.blue()) <= 30
            ):
                count += 1
    return count


def test_swatch_delegate_marks_the_current_theme(qapp):
    combo = CompactCombo()
    for key in ("GRAPHITE", "TITANIUM"):
        combo.addItem(key.title(), key)
    tune_combo(combo, 280)
    delegate = ThemeSwatchDelegate(combo)
    combo.setItemDelegate(delegate)

    delegate.set_current("GRAPHITE")
    assert delegate.current_key == "GRAPHITE"
    assert _accent_pixels_on_the_right(_render_delegate_row(combo, delegate, 0)) > 10
    assert _accent_pixels_on_the_right(_render_delegate_row(combo, delegate, 1)) == 0
