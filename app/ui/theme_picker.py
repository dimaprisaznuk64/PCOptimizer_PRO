"""Theme preview delegate for the theme picker combo box.

Paints a small colour chip (background / accent / text / warning) next to
every theme name, so the list can be scanned visually instead of reading
29 names one by one.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QStyle, QStyledItemDelegate

from . import theme

SWATCH_WIDTH = 44
SWATCH_MARGIN = 10


class ThemeSwatchDelegate(QStyledItemDelegate):
    """Renders a theme preview chip in front of the theme name."""

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        return QSize(size.width() + SWATCH_WIDTH + SWATCH_MARGIN, max(size.height(), 30))

    def paint(self, painter: QPainter, option, index) -> None:
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if selected:
            painter.fillRect(option.rect, QColor(theme.ACCENT_TINT))
        elif hovered:
            painter.fillRect(option.rect, QColor(theme.HOVER))

        key = index.data(Qt.ItemDataRole.UserRole)
        palette = theme.PALETTES.get(str(key)) if key else None
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")

        chip_left = option.rect.left() + 4
        if palette:
            chip = QRect(chip_left, option.rect.top() + 3, SWATCH_WIDTH, option.rect.height() - 6)
            path = QPainterPath()
            path.addRoundedRect(chip, 6, 6)
            painter.fillPath(path, QColor(palette.get("BG", "#101216")))
            pen = painter.pen()
            painter.setPen(QColor(palette.get("BORDER_HI", "#3A4150")))
            painter.drawPath(path)
            painter.setPen(pen)

            dot = chip.adjusted(6, 6, -6, -6)
            step = dot.width() / 3
            for position, token in enumerate(("ACCENT", "TEXT", "WARN")):
                color = QColor(palette.get(token, "#888888"))
                cx = dot.left() + step * position + step / 2
                cy = dot.center().y() + 1
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(int(cx - 4), int(cy - 4), 8, 8)

        text_rect = option.rect.adjusted(chip_left + SWATCH_WIDTH + SWATCH_MARGIN, 0, -8, 0)
        painter.setPen(QColor(theme.TEXT))
        painter.drawText(
            text_rect,
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
        painter.restore()
