from __future__ import annotations

from collections import deque

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .icons import glyph
from .theme import (
    ACCENT,
    BORDER,
    BORDER_HI,
    C1,
    C3,
    DANGER,
    OK,
    PANEL,
    PANEL_ALT,
    TEXT,
    TEXT_DIM,
    WARN,
    fs,
)


def level_color(percent: float, base: str = ACCENT) -> str:
    if percent >= 90:
        return DANGER
    if percent >= 75:
        return WARN
    return base


class ScoreRing(QWidget):
    """Circular 0-100 gauge; child label sits in the middle."""

    def __init__(self, label: QLabel, size: int = 132, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._value: float | None = None
        self._shown = 0.0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(600)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)

    def _on_anim(self, value) -> None:
        self._shown = float(value)
        self.update()

    def set_value(self, value: float | None) -> None:
        self._value = None if value is None else max(0.0, min(100.0, float(value)))
        self._anim.stop()
        target = self._value or 0.0
        if self.isVisible() and abs(target - self._shown) > 0.5:
            self._anim.setStartValue(self._shown)
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self._shown = target
            self.update()

    @staticmethod
    def color_for(value: float) -> str:
        if value >= 80:
            return OK
        if value >= 50:
            return WARN
        return DANGER

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        thickness = 10.0
        rect = QRectF(self.rect()).adjusted(thickness, thickness, -thickness, -thickness)
        track = QPen(QColor(PANEL_ALT), thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)
        if self._value and self._shown > 0:
            arc = QPen(QColor(self.color_for(self._value)), thickness)
            arc.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(arc)
            painter.drawArc(rect, 90 * 16, int(-360 * 16 * self._shown / 100.0))


def glyph_tile(icon: str, color: str = ACCENT, size: int = 38) -> QLabel:
    tile = QLabel()
    tile.setObjectName("iconTile")
    tile.setFixedSize(size, size)
    tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
    tile.setPixmap(
        glyph(icon, color).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    )
    return tile


class _Ring(QWidget):
    """Circular gauge with smooth neon glow; text lives in child labels."""

    def __init__(self, color: str, size: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._color = color
        self._percent = 0.0
        self._shown = 0.0
        self._has_value = False
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(380)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim)

    def _on_anim(self, value) -> None:
        self._shown = float(value)
        self.update()

    def set_percent(self, percent: float | None) -> None:
        self._has_value = percent is not None
        self._percent = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        self._anim.stop()
        if self.isVisible() and abs(self._percent - self._shown) > 0.5:
            self._anim.setStartValue(self._shown)
            self._anim.setEndValue(self._percent)
            self._anim.start()
        else:
            self._shown = self._percent
            self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        thickness = 8.5
        rect = QRectF(self.rect()).adjusted(thickness + 2, thickness + 2, -thickness - 2, -thickness - 2)
        
        # Background circular track
        track = QPen(QColor(PANEL_ALT), thickness)
        track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track)
        painter.drawArc(rect, 0, 360 * 16)
        
        if not self._has_value or self._shown <= 0:
            return
            
        span = int(-360 * 16 * self._shown / 100.0)
        color = QColor(level_color(self._percent, self._color))
        
        # Soft outer glow
        glow = QColor(color)
        glow.setAlpha(40)
        wide = QPen(glow, thickness + 8)
        wide.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(wide)
        painter.drawArc(rect, 90 * 16, span)
        
        # Sharp foreground arc
        arc = QPen(color, thickness)
        arc.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(arc)
        painter.drawArc(rect, 90 * 16, span)


class RingCard(QFrame):
    """Vertical card: header with icon/model, glowing ring with percent, bottom stats."""

    clicked = Signal()

    def __init__(self, title: str, color: str = ACCENT, icon_name: str = "cpu", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {ACCENT}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header: Icon + Title + Arrow
        header = QHBoxLayout()
        header.setSpacing(6)
        self.header_icon = QLabel()
        self.header_icon.setPixmap(glyph(icon_name, color).scaled(16, 16, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(self.header_icon)

        self.header_title = QLabel(title)
        self.header_title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT_DIM};")
        header.addWidget(self.header_title)
        header.addStretch(1)

        self.header_arrow = QLabel("›")
        self.header_arrow.setStyleSheet(f"font-size: {fs(14)}px; font-weight: 700; color: {TEXT_DIM};")
        header.addWidget(self.header_arrow)
        layout.addLayout(header)

        # Center ring
        self.ring = _Ring(color, size=124)
        ring_layout = QVBoxLayout(self.ring)
        ring_layout.setContentsMargins(0, 0, 0, 0)
        ring_layout.setSpacing(1)
        ring_layout.addStretch(1)

        self.value = QLabel("—")
        self.value.setObjectName("ringValue")
        self.value.setStyleSheet(f"font-size: {fs(24)}px; font-weight: 800; color: {TEXT};")
        self.value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_layout.addWidget(self.value)

        self.center_sub = QLabel("Завантаження")
        self.center_sub.setStyleSheet(f"font-size: {fs(10)}px; font-weight: 500; color: {TEXT_DIM};")
        self.center_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ring_layout.addWidget(self.center_sub)
        ring_layout.addStretch(1)

        layout.addWidget(self.ring, 0, Qt.AlignmentFlag.AlignHCenter)

        # Bottom details (two rows / metrics)
        details_box = QHBoxLayout()
        details_box.setSpacing(4)
        
        self.sub = QLabel("")
        self.sub.setObjectName("ringSub")
        self.sub.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        self.sub.setAlignment(Qt.AlignmentFlag.AlignLeft)
        details_box.addWidget(self.sub)

        details_box.addStretch(1)

        self.extra = QLabel("")
        self.extra.setObjectName("cardSub")
        self.extra.setStyleSheet(f"font-size: {fs(11)}px; font-weight: 600; color: {OK};")
        self.extra.setAlignment(Qt.AlignmentFlag.AlignRight)
        details_box.addWidget(self.extra)
        
        layout.addLayout(details_box)

        self.spark = Sparkline(color, points=120, height=10, value_range=(0, 100), parent=self)
        self.spark.hide()

        for child in self.findChildren(QWidget):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_header(self, text: str) -> None:
        self.header_title.setText(text)

    def set_center_sub(self, text: str) -> None:
        self.center_sub.setText(text)

    def update_metric(
        self,
        value: str,
        sub: str = "",
        percent: float | None = None,
        spark: float | None = None,
        extra: str = "",
    ) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.extra.setText(extra)
        self.extra.setVisible(bool(extra))
        self.ring.set_percent(percent)
        if spark is not None:
            self.spark.add(spark)
        else:
            self.spark.reset()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class PerfChart(QFrame):
    """Tabbed history chart (CPU / RAM / GPU / Network) with axes and multi-series curves."""

    SERIES = (
        ("all", "dash_legend_all", True),
        ("cpu", "CPU", True),
        ("ram", "RAM", True),
        ("gpu", "GPU", True),
        ("net", "dash_legend_net", False),
    )

    def __init__(self, title: str | None = None, points: int = 120, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(6)

        head = QHBoxLayout()
        label = QLabel(title or tr("dash_chart_title"))
        label.setStyleSheet(f"font-size: {fs(13)}px; font-weight: 700; color: {TEXT};")
        head.addWidget(label)
        head.addStretch(1)
        self._title_label = label

        # Legend pills
        legend = QHBoxLayout()
        legend.setSpacing(10)
        self._legend: dict[str, QLabel] = {}
        for name, col in (("CPU", C1), ("GPU", C3), ("RAM", OK)):
            leg_lbl = QLabel(f"● {name}")
            leg_lbl.setStyleSheet(f"font-size: {fs(11)}px; font-weight: 600; color: {col};")
            legend.addWidget(leg_lbl)
            self._legend[name] = leg_lbl
        head.addLayout(legend)
        head.addSpacing(14)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons: dict[str, QPushButton] = {}
        for key, text_key, _pct in self.SERIES:
            button = QPushButton(tr(text_key))
            button.setProperty("seg", True)
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, k=key: self.select(k))
            self._group.addButton(button)
            head.addWidget(button)
            self._buttons[key] = button
        layout.addLayout(head)

        self._canvas = _ChartCanvas(points)
        layout.addWidget(self._canvas, 1)
        self.select("all")

    def set_title(self, text: str) -> None:
        self._title_label.setText(text)

    def retranslate(self) -> None:
        """Refresh dynamic labels after a language change."""
        self.set_title(tr("dash_chart_title"))
        for key, button in self._buttons.items():
            text_key = next(t for k, t, _p in self.SERIES if k == key)
            button.setText(tr(text_key))

    @property
    def current(self) -> str:
        return self._canvas.key

    def select(self, key: str) -> None:
        percent = {k: pct for k, _t, pct in self.SERIES}.get(key, True)
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        self._canvas.set_key(key, percent)

    def push(self, ts: float, **values: float | None) -> None:
        self._canvas.push(ts, values)


class _ChartCanvas(QWidget):
    def __init__(self, points: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.key = "all"
        self._percent = True
        self._history: dict[str, deque[float]] = {}
        self._times: deque[float] = deque(maxlen=points)
        self._points = points

    def set_key(self, key: str, percent: bool) -> None:
        self.key = key
        self._percent = percent
        self.update()

    def push(self, ts: float, values: dict[str, float | None]) -> None:
        self._times.append(ts)
        for key, value in values.items():
            self._history.setdefault(key, deque(maxlen=self._points)).append(0.0 if value is None else float(value))
        self.update()

    @staticmethod
    def _span_text(seconds: float) -> str:
        # Single formatter for every tick: >= 60 s -> minutes, else seconds.
        if seconds >= 60:
            return tr("dash_time_min", min=f"{round(seconds / 60):.0f}")
        return tr("dash_time_sec", sec=f"{round(seconds):.0f}")

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        left, bottom = 38, 20
        plot = QRectF(left, 6, self.width() - left - 10, self.height() - bottom - 10)
        
        values = self._history.get(self.key if self.key != "all" else "cpu")
        if self._percent:
            hi = 100.0
        else:
            hi = max(max(values) * 1.25 if values else 0.0, 100 * 1024.0)

        grid = QColor(BORDER)
        text = QColor(TEXT_DIM)
        font = painter.font()
        font.setPixelSize(fs(11))
        painter.setFont(font)
        
        # Horizontal grid
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - frac * plot.height()
            painter.setPen(QPen(grid, 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            if frac in (0.0, 0.5, 1.0):
                if self._percent:
                    label = f"{hi * frac:.0f}%"
                else:
                    from .format import rate
                    label = rate(hi * frac)
                painter.setPen(text)
                painter.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, label)

        # Stretch the axis to what we actually have, so the curve fills the plot
        # honestly right after startup instead of hugging the right edge.
        count = len(self._times)
        if count > 1:
            dt = (self._times[-1] - self._times[0]) / (count - 1)
            span = dt * (count - 1)
        else:
            span = 0.0
        painter.setPen(text)
        for i, frac in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
            x = plot.left() + frac * plot.width()
            label = tr("dash_chart_now") if frac == 1.0 else self._span_text(span * (1 - frac)) if span else ""
            align = Qt.AlignmentFlag.AlignLeft if i == 0 else Qt.AlignmentFlag.AlignRight if frac == 1.0 else Qt.AlignmentFlag.AlignHCenter
            box = QRectF(x - 30 if align == Qt.AlignmentFlag.AlignHCenter else x - (0 if i == 0 else 60), plot.bottom() + 4, 60, 14)
            if align == Qt.AlignmentFlag.AlignRight:
                box = QRectF(x - 60, plot.bottom() + 4, 60, 14)
            painter.drawText(box, align | Qt.AlignmentFlag.AlignVCenter, label)

        step = plot.width() / max(1, count - 1)

        def point(i: int, v: float, count: int) -> QPointF:
            x0 = plot.right() - (count - 1) * step
            ratio = max(0.0, min(1.0, v / hi))
            return QPointF(x0 + i * step, plot.bottom() - ratio * plot.height())

        if self.key == "all":
            series_cfg = [
                ("ram", QColor(OK)),
                ("gpu", QColor(C3)),
                ("cpu", QColor(C1)),
            ]
            for s_key, s_col in series_cfg:
                s_vals = self._history.get(s_key)
                if not s_vals or len(s_vals) < 2:
                    continue
                path = QPainterPath(point(0, s_vals[0], len(s_vals)))
                for i, v in enumerate(s_vals):
                    path.lineTo(point(i, v, len(s_vals)))
                fill = QPainterPath(path)
                fill.lineTo(plot.right(), plot.bottom())
                x0 = plot.right() - (len(s_vals) - 1) * step
                fill.lineTo(x0, plot.bottom())
                fill.closeSubpath()
                top = QColor(s_col)
                top.setAlpha(35)
                bottom_c = QColor(s_col)
                bottom_c.setAlpha(0)
                gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
                gradient.setColorAt(0.0, top)
                gradient.setColorAt(1.0, bottom_c)
                painter.fillPath(fill, gradient)
                pen = QPen(s_col, 2.0)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.drawPath(path)
        else:
            if not values or len(values) < 2:
                return
            path = QPainterPath(point(0, values[0], len(values)))
            for i, v in enumerate(values):
                path.lineTo(point(i, v, len(values)))
            fill = QPainterPath(path)
            fill.lineTo(plot.right(), plot.bottom())
            x0 = plot.right() - (len(values) - 1) * step
            fill.lineTo(x0, plot.bottom())
            fill.closeSubpath()
            color = QColor(ACCENT)
            top = QColor(color)
            top.setAlpha(80)
            bottom_c = QColor(color)
            bottom_c.setAlpha(0)
            gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
            gradient.setColorAt(0.0, top)
            gradient.setColorAt(1.0, bottom_c)
            painter.fillPath(fill, gradient)
            pen = QPen(color, 2.0)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            painter.drawPath(path)


class _EmptyHint(QLabel):
    """Centered hint shown over a table viewport while the table has no rows."""

    def __init__(self, table, key: str) -> None:
        super().__init__(table.viewport())
        self._table = table
        self._key = key
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(f"color: {TEXT_DIM}; font-size: {fs(13)}px; background: transparent; padding: 24px;")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        table.viewport().installEventFilter(self)
        model = table.model()
        for sig in (model.rowsInserted, model.rowsRemoved, model.modelReset, model.layoutChanged):
            sig.connect(self.refresh)
        self.refresh()

    def eventFilter(self, obj, event) -> bool:
        if event.type() in (QEvent.Type.Resize, QEvent.Type.Show):
            self.refresh()
        return False

    def refresh(self, *_args) -> None:
        from app.i18n import tr

        self.setText(tr(self._key))
        self.setGeometry(self._table.viewport().rect())
        row_count = getattr(self._table, "rowCount", None) or self._table.count
        self.setVisible(row_count() == 0)
        if self.isVisible():
            self.raise_()


def align_numeric_headers(table, columns: tuple[int, ...]) -> None:
    """Right-align header captions of numeric columns (call after setHorizontalHeaderLabels)."""
    for col in columns:
        item = table.horizontalHeaderItem(col)
        if item is not None:
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


def attach_empty_hint(table, key: str) -> _EmptyHint:
    """Show translated text `key` over `table` whenever it has no rows."""
    return _EmptyHint(table, key)


class QuickButton(QPushButton):
    def __init__(self, icon: str, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("quick", True)
        self.setIcon(QIcon(glyph(icon, ACCENT)))
        self.setIconSize(QSize(18, 18))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(38)


class ArcGauge(QWidget):
    """240-degree gauge drawn as radial ticks, value text in the middle."""

    TICKS = 40

    def __init__(self, caption: str = "Utilization", base: str = ACCENT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(150, 132)
        self._base = base
        self._percent = 0.0
        self._has_value = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 14)
        layout.setSpacing(0)
        layout.addStretch(1)
        self.value_label = QLabel("—")
        self.value_label.setObjectName("gaugeValue")
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.value_label)
        self.caption_label = QLabel(caption)
        self.caption_label.setObjectName("cardSub")
        self.caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.caption_label)
        layout.addStretch(1)

    def set_percent(self, percent: float | None) -> None:
        self._has_value = percent is not None
        self._percent = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        self.update()

    def set_caption(self, text: str) -> None:
        self.caption_label.setText(text)

    def paintEvent(self, event) -> None:
        import math

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2 + 2
        outer = min(self.width(), self.height()) / 2 - 4
        inner = outer - 11
        pen_off = QPen(QColor(BORDER_HI), 3.0)
        pen_off.setCapStyle(Qt.PenCapStyle.RoundCap)
        for i in range(self.TICKS):
            frac = i / (self.TICKS - 1)
            angle = math.radians(210 - 240 * frac)
            active = self._has_value and (i + 0.5) / self.TICKS * 100 <= self._percent
            if active:
                color = self._base if frac < 0.6 else WARN if frac < 0.8 else DANGER
                pen = QPen(QColor(color), 3.4)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                painter.setPen(pen)
            else:
                painter.setPen(pen_off)
            painter.drawLine(
                QPointF(cx + math.cos(angle) * inner, cy - math.sin(angle) * inner),
                QPointF(cx + math.cos(angle) * outer, cy - math.sin(angle) * outer),
            )


class GaugeCard(QFrame):
    more_clicked = Signal()

    def __init__(
        self,
        title: str,
        icon: str,
        caption: str = "Utilization",
        color: str = ACCENT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 16, 14, 14)
        row.setSpacing(8)

        left = QVBoxLayout()
        left.setSpacing(4)
        tile = QLabel()
        tile.setObjectName("iconTile")
        tile.setFixedSize(38, 38)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(glyph(icon, color).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        left.addWidget(tile)
        left.addSpacing(4)
        name = QLabel(title)
        name.setObjectName("gaugeTitle")
        left.addWidget(name)
        self.title_label = name
        self.sub = QLabel("")
        self.sub.setObjectName("cardSub")
        self.sub.setWordWrap(True)
        left.addWidget(self.sub)
        left.addStretch(1)
        self.spark = Sparkline(color, points=60, height=26, value_range=(0, 100))
        left.addWidget(self.spark)
        self.more = QPushButton("View more  ›")
        self.more.setObjectName("linkButton")
        self.more.setCursor(Qt.CursorShape.PointingHandCursor)
        self.more.clicked.connect(self.more_clicked)
        left.addWidget(self.more, 0, Qt.AlignmentFlag.AlignLeft)
        row.addLayout(left, 1)

        self.gauge = ArcGauge(caption, color)
        row.addWidget(self.gauge, 0, Qt.AlignmentFlag.AlignVCenter)
        self.value = self.gauge.value_label
        self.bar = self.gauge

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)

    def set_caption(self, text: str) -> None:
        self.gauge.set_caption(text)

    def update_metric(self, value: str, sub: str = "", percent: float | None = None, spark: float | None = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.gauge.set_percent(percent)
        if spark is not None:
            self.spark.add(spark)
        else:
            self.spark.reset()


class _VerticalMeter(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(26, 120)
        self._percent = 0.0

    def set_percent(self, percent: float) -> None:
        self._percent = max(0.0, min(100.0, percent))
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0, 0, 0, 0)
        radius = rect.width() / 2
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(PANEL_ALT))
        painter.drawRoundedRect(rect, radius, radius)
        fill_h = max(rect.height() * self._percent / 100.0, rect.width())
        fill = QRectF(rect.left(), rect.bottom() - fill_h, rect.width(), fill_h)
        gradient = QLinearGradient(0, rect.bottom(), 0, rect.top())
        gradient.setColorAt(0.0, QColor(OK))
        gradient.setColorAt(0.6, QColor(WARN))
        gradient.setColorAt(1.0, QColor(DANGER))
        painter.setBrush(gradient)
        painter.drawRoundedRect(fill, radius, radius)


class LoadCard(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)
        title = QLabel("LOAD")
        title.setObjectName("cardTitle")
        layout.addWidget(title)
        self.value = QLabel("—")
        self.value.setObjectName("cardValue")
        layout.addWidget(self.value)
        self.state = QLabel("")
        self.state.setObjectName("cardSub")
        layout.addWidget(self.state)
        self.meter = _VerticalMeter()
        layout.addWidget(self.meter, 1, Qt.AlignmentFlag.AlignHCenter)

    def update_load(self, percent: float | None) -> None:
        if percent is None:
            self.value.setText("—")
            self.state.setText("")
            self.meter.set_percent(0)
            return
        self.value.setText(f"{percent:.0f}%")
        self.state.setText("Light" if percent < 40 else "Normal" if percent < 75 else "Heavy" if percent < 90 else "Critical")
        self.meter.set_percent(percent)


class ActionTile(QPushButton):
    def __init__(self, icon: str, title: str, subtitle: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("tile", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(64)
        row = QHBoxLayout(self)
        row.setContentsMargins(14, 10, 14, 10)
        row.setSpacing(12)
        tile = QLabel()
        tile.setObjectName("iconTile")
        tile.setFixedSize(38, 38)
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile.setPixmap(glyph(icon, ACCENT).scaled(22, 22, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        row.addWidget(tile)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        head = QLabel(title)
        head.setObjectName("tileTitle")
        texts.addWidget(head)
        sub = QLabel(subtitle)
        sub.setObjectName("cardSub")
        texts.addWidget(sub)
        row.addLayout(texts, 1)
        arrow = QLabel("›")
        arrow.setObjectName("tileArrow")
        row.addWidget(arrow)
        for child in (tile, head, sub, arrow):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)


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
            lo = 0.0 if min(self._values) >= 0 else min(self._values)
            hi = max(max(self._values) * 1.15, lo + 1.0)
        if hi - lo < 1e-9:
            hi = lo + 1.0

        grid = QColor(BORDER)
        grid.setAlpha(150)
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
        top = QColor(self._color)
        top.setAlpha(90)
        bottom = QColor(self._color)
        bottom.setAlpha(0)
        gradient = QLinearGradient(0, rect.top(), 0, rect.bottom())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.fillPath(fill, gradient)

        pen = QPen(QColor(self._color), 2.0)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawPath(path)
        painter.setBrush(QColor(self._color))
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
        self.title_label = title_label

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

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def update_metric(self, value: str, sub: str = "", percent: float | None = None, spark: float | None = None) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.sub.setVisible(bool(sub))
        if self.bar:
            self.bar.set_percent(percent)
            if percent is not None:
                self.bar.set_color(level_color(percent, self._color))
            else:
                self.bar.set_color(PANEL_ALT)
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
        self.title_label = label
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self._layout.addLayout(self.body)
        self._layout.addStretch(1)
        self._rows: dict[str, tuple[QLabel, Bar, QLabel]] = {}

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def set_rows(self, items: list[tuple[str, float | None, str]]) -> None:
        if not hasattr(self, "_empty_label"):
            self._empty_label = QLabel(tr("no_data"))
            self._empty_label.setObjectName("cardSub")
            self.body.addWidget(self._empty_label)
        self._empty_label.setText(tr("no_data"))
        self._empty_label.setVisible(not items)
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
            bar.set_color(level_color(percent or 0, ACCENT))
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
        self.title_label = label
        self._empty = QLabel("—")
        self._empty.setObjectName("cardSub")
        self._layout.addWidget(self._empty)
        self._layout.addStretch(1)
        self._rows: dict[str, QLabel] = {}

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def set_values(self, items: list[tuple[str, str]]) -> None:
        wanted = [key for key, _ in items]
        for key in list(self._rows):
            if key not in wanted:
                row = self._rows.pop(key)
                self._layout.removeWidget(row)
                row.setParent(None)
                row.deleteLater()
        self._empty.setVisible(not items)
        for key, text in items:
            if key not in self._rows:
                row = QLabel()
                row.setObjectName("cardRow")
                self._rows[key] = row
                self._layout.insertWidget(len(self._rows), row)
            self._rows[key].setText(f"{key}   {text}")


__all__ = ["ActionTile", "ArcGauge", "Bar", "CardPanel", "GaugeCard", "LoadCard", "MetricCard", "PerfChart", "QuickButton", "RingCard", "ScoreRing", "Sparkline", "ValueListCard", "glyph_tile", "level_color"]
