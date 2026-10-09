from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .theme import ACCENT, BORDER, DANGER, PANEL_ALT, WARN


def with_alpha(color: str, alpha: int) -> QColor:
    result = QColor(color)
    result.setAlpha(max(0, min(255, int(alpha))))
    return result


def level_color(percent: float | None, base: str = ACCENT) -> str:
    if percent is None:
        return base
    if percent >= 90:
        return DANGER
    if percent >= 75:
        return WARN
    return base


class Sparkline(QWidget):
    def __init__(
        self,
        color: str = ACCENT,
        points: int = 90,
        height: int = 40,
        parent: QWidget | None = None,
        *,
        value_range: tuple[float, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._color = color
        self._range = value_range
        self._values: deque[float] = deque(maxlen=points)

    def add(self, value: float) -> None:
        self._values.append(float(value))
        self.update()

    def reset(self) -> None:
        self._values.clear()
        self.update()

    def paintEvent(self, event) -> None:
        if len(self._values) < 2:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(5, 6, -5, -6)

        if self._range is not None:
            lo, hi = self._range
        else:
            lo = min(self._values)
            hi = max(self._values)
        if hi - lo < 1e-9:
            hi = lo + 1.0

        grid = with_alpha(BORDER, 150)
        painter.setPen(QPen(grid, 1, Qt.PenStyle.DotLine))
        for frac in (0.25, 0.5, 0.75):
            y = rect.bottom() - frac * rect.height()
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))

        width = max(rect.width(), 1)
        step = width / (len(self._values) - 1)

        def point(i: int, value: float) -> QPointF:
            ratio = max(0.0, min(1.0, (value - lo) / (hi - lo)))
            return QPointF(rect.left() + i * step, rect.bottom() - ratio * rect.height())

        path = QPainterPath()
        start = point(0, self._values[0])
        path.moveTo(start)
        for i, value in enumerate(self._values):
            path.lineTo(point(i, value))

        fill = QPainterPath(path)
        fill.lineTo(rect.right(), rect.bottom())
        fill.lineTo(rect.left(), rect.bottom())
        fill.closeSubpath()
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0.0, with_alpha(self._color, 90))
        gradient.setColorAt(1.0, with_alpha(self._color, 0))
        painter.fillPath(fill, gradient)

        pen = QPen(QColor(self._color), 2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)

        painter.setBrush(QColor(self._color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(point(len(self._values) - 1, self._values[-1]), 3.0, 3.0)


class Bar(QWidget):
    def __init__(self, color: str = ACCENT, height: int = 8, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(height)
        self._color = color
        self._percent = 0.0

    def set_percent(self, percent: float | None) -> None:
        self._percent = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect())
        radius = rect.height() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PANEL_ALT))
        painter.drawRoundedRect(rect, radius, radius)
        if self._percent > 0:
            width = max(rect.width() * self._percent / 100.0, radius * 2)
            fill = QRectF(rect.left(), rect.top(), min(width, rect.width()), rect.height())
            painter.setBrush(QColor(self._color))
            painter.drawRoundedRect(fill, radius, radius)


class MetricCard(QFrame):
    def __init__(
        self,
        title: str,
        parent: QWidget | None = None,
        *,
        sparkline: bool = True,
        bar: bool = True,
        color: str = ACCENT,
        spark_range: tuple[float, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        title_label = QLabel(title.upper())
        title_label.setObjectName("cardTitle")
        layout.addWidget(title_label)

        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        layout.addWidget(self.value)

        self.sub = QLabel("")
        self.sub.setObjectName("cardSub")
        self.sub.setWordWrap(True)
        layout.addWidget(self.sub)

        self.spark = Sparkline(color, value_range=spark_range) if sparkline else None
        if self.spark:
            self.spark.setMinimumHeight(40)
            self.spark.setMaximumHeight(16777215)
            self.spark.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            layout.addSpacing(6)
            layout.addWidget(self.spark, 1)
        else:
            layout.addStretch(1)

        self.bar = Bar(color) if bar else None
        if self.bar:
            layout.addSpacing(6)
            layout.addWidget(self.bar)

    def update_metric(self, value: str, sub: str = "", percent: float | None = None, spark: float | None = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        if self.bar:
            self.bar.set_percent(percent)
            self.bar.set_color(level_color(percent, self._color) if percent is not None else PANEL_ALT)
        if self.spark:
            if spark is not None:
                self.spark.add(spark)
            else:
                self.spark.reset()


class CardPanel(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(8)
        label = QLabel(title.upper())
        label.setObjectName("cardTitle")
        self._layout.addWidget(label)
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self._layout.addLayout(self.body)
        self._layout.addStretch(1)
        self._rows: dict[str, tuple[QLabel, Bar, QLabel]] = {}

    def set_rows(self, items: list[tuple[str, float | None, str]]) -> None:
        wanted = [key for key, _p, _t in items]
        for key in list(self._rows):
            if key not in wanted:
                label, bar, text = self._rows.pop(key)
                label.deleteLater()
                bar.deleteLater()
                text.deleteLater()
        for key, percent, text in items:
            if key not in self._rows:
                label = QLabel(key)
                label.setObjectName("cardRow")
                label.setMinimumWidth(64)
                bar = Bar(ACCENT)
                text_label = QLabel("")
                text_label.setObjectName("cardSub")
                text_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.body.addWidget(label)
                self.body.addWidget(bar)
                self.body.addWidget(text_label)
                self._rows[key] = (label, bar, text_label)
            label, bar, text_label = self._rows[key]
            bar.set_percent(percent)
            bar.set_color(level_color(percent, ACCENT))
            text_label.setText(text)


class ValueListCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(6)
        label = QLabel(title.upper())
        label.setObjectName("cardTitle")
        self._layout.addWidget(label)
        self._empty = QLabel("—")
        self._empty.setObjectName("cardSub")
        self._layout.addWidget(self._empty)
        self._layout.addStretch(1)
        self._rows: dict[str, QLabel] = {}

    def set_values(self, items: list[tuple[str, str]]) -> None:
        wanted = [key for key, _ in items]
        for key in list(self._rows):
            if key not in wanted:
                widget = self._rows.pop(key)
                self._layout.removeWidget(widget)
                widget.deleteLater()
        self._empty.setVisible(not items)
        for key, text in items:
            if key not in self._rows:
                row = QLabel()
                row.setObjectName("cardRow")
                self._rows[key] = row
                self._layout.insertWidget(len(self._rows), row)
            self._rows[key].setText(f"{key}   {text}")


__all__ = ["Bar", "CardPanel", "MetricCard", "Sparkline", "ValueListCard", "level_color", "with_alpha"]
