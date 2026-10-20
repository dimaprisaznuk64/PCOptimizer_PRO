from __future__ import annotations

import math
from collections import deque

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QPointF,
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import (
    QColor,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
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
    CARD_PADDING,
    DANGER,
    OK,
    PANEL,
    PANEL_ALT,
    TEXT,
    TEXT_DIM,
    WARN,
    _mix,
    card_shadow,
    fs,
    hud_brackets,
    set_mono,
)

# Chart series palette. Colours are deliberately distinct and match the
# dashboard ring cards / legend: CPU - blue (C2), GPU - purple (C3),
# RAM - amber (WARN), network download - blue (C2), upload - amber (WARN).
# Each entry is (label key, theme colour token, pen style). ``label_key`` is
# passed through ``tr`` so network rows reuse the existing i18n strings while
# acronyms (CPU/GPU/RAM) fall back to themselves.
CHART_SERIES: dict[str, tuple[str, str, Qt.PenStyle]] = {
    "cpu": ("CPU", "C2", Qt.PenStyle.SolidLine),
    "gpu": ("GPU", "C3", Qt.PenStyle.SolidLine),
    "ram": ("RAM", "WARN", Qt.PenStyle.SolidLine),
    "net_down": ("dash_net_download", "C2", Qt.PenStyle.SolidLine),
    "net_up": ("dash_net_upload", "WARN", Qt.PenStyle.SolidLine),
}

# Series shown in the "All" tab and which series the "Network" tab plots.
ALL_SERIES = ("ram", "gpu", "cpu")
NET_DOWN_KEY = "net_down"
NET_UP_KEY = "net_up"


def chart_series_color(token: str) -> str:
    from . import theme

    return getattr(theme, token, ACCENT)


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


def card_heading(text: str, accent: str = ACCENT) -> QWidget:
    """Card caption: a short accent bar + the uppercase mono title."""
    row = QWidget()
    row.setObjectName("cardHeading")
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 0, 0, 0)
    hl.setSpacing(8)
    bar = QFrame()
    bar.setObjectName("cardHeadingBar")
    bar.setFixedSize(3, 14)
    bar.setStyleSheet(f"background: {accent}; border: none; border-radius: 1px;")
    hl.addWidget(bar)
    label = QLabel(text.upper())
    label.setObjectName("cardTitle")
    set_mono(label, spacing_pct=14.0)
    hl.addWidget(label)
    hl.addStretch(1)
    row._label = label  # type: ignore[attr-defined]
    return row


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
            self._paint_threshold(painter, rect, thickness)
            return
            
        span = int(-360 * 16 * self._shown / 100.0)
        # The value arc keeps its series colour at any level; red is reserved
        # for the threshold marker (see _paint_threshold).
        color = QColor(self._color)

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

        self._paint_threshold(painter, rect, thickness)

    @staticmethod
    def _paint_threshold(painter: QPainter, rect: QRectF, thickness: float) -> None:
        """Red tick at the 90% mark — the only red on the ring."""
        angle = math.radians(90 - 360 * 0.9)
        ux, uy = math.cos(angle), -math.sin(angle)
        cx, cy = rect.center().x(), rect.center().y()
        r = rect.width() / 2
        half = thickness / 2 + 1
        pen = QPen(QColor(DANGER), 2.0)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(cx + (r - half) * ux, cy + (r - half) * uy),
            QPointF(cx + (r + half) * ux, cy + (r + half) * uy),
        )


class RingCard(QFrame):
    """Vertical card: header with icon/model, glowing ring with percent, bottom stats."""

    clicked = Signal()

    def __init__(self, title: str, color: str = ACCENT, icon_name: str = "cpu", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self._shadow = card_shadow(self)
        hud_brackets(self)
        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius", self)
        self._shadow_anim.setDuration(180)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # Hover is driven by explicit enter/leave events (property "hot"):
        # the CSS :hover state could get stuck after repaints and left a
        # "random" accent border on the card.
        self.setProperty("hot", False)
        self.setStyleSheet(
            f"QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {_mix(PANEL, TEXT, 0.035)}, stop:1 {PANEL}); "
            f"border: 1px solid {BORDER}; border-radius: 12px; }} "
            f"QFrame#card[hot=\"true\"] {{ border-color: {ACCENT}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
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
        extra_color: str = OK,
    ) -> None:
        self.value.setText(value)
        self.sub.setText(sub)
        self.extra.setText(extra)
        self.extra.setStyleSheet(f"font-size: {fs(11)}px; font-weight: 600; color: {extra_color};")
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

    def _set_hot(self, hot: bool) -> None:
        if self.property("hot") == hot:
            return
        self.setProperty("hot", hot)
        self.style().unpolish(self)
        self.style().polish(self)
        # Hover glow: the drop shadow swells instead of scaling the card —
        # animating geometry would fight the layout manager.
        self._shadow_anim.stop()
        self._shadow_anim.setStartValue(float(self._shadow.blurRadius()))
        self._shadow_anim.setEndValue(46.0 if hot else 24.0)
        self._shadow_anim.start()
        self.update()

    def enterEvent(self, event) -> None:
        self._set_hot(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._set_hot(False)
        super().leaveEvent(event)

    def hideEvent(self, event) -> None:
        # Hiding while hovered (page switch) must not keep the accent border.
        self._set_hot(False)
        super().hideEvent(event)


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
        card_shadow(self)
        hud_brackets(self)
        self.setStyleSheet(
            f"QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, "
            f"stop:0 {_mix(PANEL, TEXT, 0.035)}, stop:1 {PANEL}); "
            f"border: 1px solid {BORDER}; border-radius: 12px; }} "
            f"QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        layout.setSpacing(6)

        head = QHBoxLayout()
        label = QLabel(title or tr("dash_chart_title"))
        label.setStyleSheet(f"font-size: {fs(13)}px; font-weight: 700; color: {TEXT};")
        head.addWidget(label)
        head.addStretch(1)
        self._title_label = label

        # Legend pills (rebuilt for every selected tab)
        legend = QHBoxLayout()
        legend.setSpacing(10)
        self._legend_layout = legend
        self._legend: dict[str, QLabel] = {}
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
        self._hidden: set[str] = set()
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
        self._rebuild_legend(self._canvas.key)

    @property
    def current(self) -> str:
        return self._canvas.key

    @staticmethod
    def _legend_keys(key: str) -> tuple[str, ...]:
        if key == "all":
            return ("cpu", "gpu", "ram")
        if key == "net":
            return (NET_DOWN_KEY, NET_UP_KEY)
        return (key,)

    def _rebuild_legend(self, key: str) -> None:
        while self._legend_layout.count():
            item = self._legend_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._legend = {}
        for series_key in self._legend_keys(key):
            label_key, token, _style = CHART_SERIES.get(series_key, (series_key, "ACCENT", Qt.PenStyle.SolidLine))
            color = chart_series_color(token)
            pill = QPushButton(f"● {tr(label_key)}")
            pill.setCheckable(True)
            pill.setChecked(series_key not in self._hidden)
            pill.setCursor(Qt.CursorShape.PointingHandCursor)
            pill.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; font-size: {fs(11)}px; "
                f"font-weight: 600; color: {color if series_key not in self._hidden else TEXT_DIM}; padding: 0px; }}"
                f"QPushButton:hover {{ color: {TEXT}; }}"
            )
            pill.clicked.connect(lambda _=False, k=series_key: self._toggle_series(k))
            self._legend_layout.addWidget(pill)
            self._legend[series_key] = pill

    def _toggle_series(self, key: str) -> None:
        """Legend pills toggle series visibility (never hide the last one)."""
        currently_hidden = key in self._hidden
        if currently_hidden:
            self._hidden.discard(key)
        else:
            visible = [k for k in self._legend if k not in self._hidden and k != key]
            if not visible:
                # Keep at least one series on screen: restore this one instead.
                self._hidden.discard(key)
            else:
                self._hidden.add(key)
        pill = self._legend.get(key)
        if pill is not None:
            on = key not in self._hidden
            pill.setChecked(on)
            label_key, token, _style = CHART_SERIES.get(key, (key, "ACCENT", Qt.PenStyle.SolidLine))
            pill.setStyleSheet(
                f"QPushButton {{ background: transparent; border: none; font-size: {fs(11)}px; "
                f"font-weight: 600; color: {chart_series_color(token) if on else TEXT_DIM}; padding: 0px; }}"
                f"QPushButton:hover {{ color: {TEXT}; }}"
            )
        self._canvas.set_hidden(self._hidden)

    def select(self, key: str) -> None:
        percent = {k: pct for k, _t, pct in self.SERIES}.get(key, True)
        if key in self._buttons:
            self._buttons[key].setChecked(True)
        self._rebuild_legend(key)
        self._canvas.set_key(key, percent)

    def push(self, ts: float, **values: float | None) -> None:
        self._canvas.push(ts, values)


def _fmt_rate(value: float) -> str:
    from .format import rate

    return rate(value)


_TIME_STEPS = (5, 10, 15, 30, 60, 120, 300, 600, 1800)


def time_step_for(span: float) -> int:
    """Fixed tick step (seconds) so axis labels land on round values."""
    for step in _TIME_STEPS:
        if span / step <= 6:
            return step
    return _TIME_STEPS[-1]


def chart_line_spec(key: str, multi: bool) -> tuple[bool, float]:
    """(draw fill, pen width): lines are uniform; only CPU keeps the fill in
    multi-series mode so the curves do not cover each other with gradients."""
    primary = (not multi) or key == "cpu"
    return primary, 2.5


class _ChartCanvas(QWidget):
    def __init__(self, points: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(130)
        self.setMouseTracking(True)
        self.key = "all"
        self._percent = True
        self._hidden: set[str] = set()
        self._history: dict[str, deque[float]] = {}
        self._times: deque[float] = deque(maxlen=points)
        self._points = points
        self._hover_x: float | None = None

    def set_key(self, key: str, percent: bool) -> None:
        self.key = key
        self._percent = percent
        self.update()

    def set_hidden(self, keys: set[str]) -> None:
        self._hidden = set(keys)
        self.update()

    def push(self, ts: float, values: dict[str, float | None]) -> None:
        self._times.append(ts)
        for key, value in values.items():
            hist = self._history.setdefault(key, deque(maxlen=self._points))
            if value is None:
                value = hist[-1] if hist else 0.0  # a missed reading must not look like a drop to 0
            hist.append(float(value))
        self.update()

    @staticmethod
    def _span_text(seconds: float) -> str:
        # One format for every tick (-m:ss) so units never mix on the axis.
        total = max(0, int(round(seconds)))
        return f"-{total // 60}:{total % 60:02d}"

    def _time_ticks(self, span: float, width: float) -> list[tuple[float, str]]:
        """(x, label) pairs aligned to fixed second steps (right edge = now)."""
        if span <= 1 or width <= 0:
            return []
        step = time_step_for(span)
        ticks: list[tuple[float, str]] = []
        k = 1
        while k * step < span * 0.97:
            x = width - (k * step) / span * width
            if x <= width - 70 and (not ticks or ticks[-1][0] - x >= 44) and x >= 34:
                label = (
                    tr("chart_ago_s", n=int(k * step))
                    if span <= 60
                    else self._span_text(k * step)
                )
                ticks.append((x, label))
            k += 1
        return ticks

    def _series_to_draw(self) -> list[tuple[str, QColor, Qt.PenStyle]]:
        """Return ``(history key, colour, pen style)`` for the active tab."""
        if self.key == "all":
            keys = list(ALL_SERIES)
        elif self.key == "net":
            keys = [k for k in (NET_DOWN_KEY, NET_UP_KEY) if self._history.get(k)]
            if not keys and self._history.get("net"):
                keys = ["net"]  # legacy single-line payload
        else:
            keys = [self.key]
        keys = [k for k in keys if k not in self._hidden]
        series: list[tuple[str, QColor, Qt.PenStyle]] = []
        for key in keys:
            _label, token, style = CHART_SERIES.get(key, (key, "ACCENT", Qt.PenStyle.SolidLine))
            series.append((key, QColor(chart_series_color(token)), style))
        return series

    @staticmethod
    def _smooth(values: list[float], window: int = 3) -> list[float]:
        """Centered moving average so sensor noise does not look like spikes."""
        if window < 2 or len(values) < window:
            return list(values)
        half = window // 2
        out: list[float] = []
        for i in range(len(values)):
            lo = max(0, i - half)
            hi = min(len(values), i + half + 1)
            segment = values[lo:hi]
            out.append(sum(segment) / len(segment))
        return out

    def _axis_hi(self, series: list[tuple[str, QColor, Qt.PenStyle]]) -> float:
        if self._percent:
            return 100.0
        peak = 0.0
        for key, _color, _style in series:
            vals = self._history.get(key)
            if vals:
                peak = max(peak, max(vals))
        # Floor keeps tiny idle traffic a flat line instead of a spike.
        return max(peak * 1.25, 100 * 1024.0)

    def _axis_label(self, hi: float, frac: float) -> str:
        if self._percent:
            return f"{hi * frac:.0f}%"
        from .format import rate

        return rate(hi * frac)

    def _plot_metrics(self) -> tuple[float, float]:
        """(left margin, bottom margin) matching what paintEvent reserves."""
        font = self.font()
        font.setPixelSize(fs(11))
        metrics = QFontMetrics(font)
        hi = 100.0 if self._percent else self._axis_hi(self._series_to_draw())
        tick_labels = [self._axis_label(hi, frac) for frac in (1.0, 0.5, 0.0)]
        left = max(metrics.horizontalAdvance(lbl) for lbl in tick_labels) + 12
        return left, 20.0

    def _plot_rect(self) -> QRectF:
        left, bottom = self._plot_metrics()
        return QRectF(left, 6, max(10.0, self.width() - left - 10), self.height() - bottom - 10)

    def mouseMoveEvent(self, event) -> None:
        self._hover_x = event.position().x()
        self.update()

    def leaveEvent(self, event) -> None:
        self._hover_x = None
        self.update()

    def _paint_hover(self, painter: QPainter, plot: QRectF, series: list) -> None:
        """Accent crosshair, per-series dots and a drawn value box under the cursor."""
        from datetime import datetime

        count = max((len(self._history.get(k, ())) for k, _c, _s in series), default=0)
        if self._hover_x is None or count < 2 or not plot.left() <= self._hover_x <= plot.right():
            return
        idx = round((self._hover_x - plot.left()) / plot.width() * (count - 1))
        x = plot.left() + idx / (count - 1) * plot.width()
        cross = QColor(ACCENT)
        cross.setAlpha(170)
        painter.setPen(QPen(cross, 1, Qt.PenStyle.DotLine))
        painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
        rows: list[tuple[str, QColor]] = []
        time_text = (
            datetime.fromtimestamp(self._times[idx]).strftime("%H:%M:%S")
            if len(self._times) == count and 0 <= idx < len(self._times)
            else ""
        )
        if time_text:
            rows.append((time_text, QColor(TEXT_DIM)))
        hi = 100.0 if self._percent else self._axis_hi(series)
        for key, color, _style in series:
            vals = self._history.get(key)
            if not vals or idx >= len(vals):
                continue
            label_key = CHART_SERIES.get(key, (key, "ACCENT", Qt.PenStyle.SolidLine))[0]
            value = vals[idx]
            # Dot at the hovered sample.
            ratio = max(0.0, min(1.0, value / hi))
            dot = QPointF(x, plot.bottom() - ratio * plot.height())
            painter.setPen(QPen(QColor(PANEL), 1.5))
            painter.setBrush(color)
            painter.drawEllipse(dot, 3.5, 3.5)
            shown = f"{value:.0f}%" if self._percent else f"{_fmt_rate(value)}/s"
            rows.append((f"{tr(label_key)}: {shown}", color))
        if not rows:
            return
        metrics = painter.fontMetrics()
        width = max(metrics.horizontalAdvance(t) for t, _c in rows) + 16
        height = len(rows) * (metrics.height() + 2) + 8
        bx = x + 10 if x + 10 + width <= plot.right() else x - 10 - width
        box = QRectF(bx, plot.top() + 2, width, height)
        painter.setPen(QPen(QColor(BORDER_HI), 1))
        painter.setBrush(QColor(PANEL))
        painter.drawRoundedRect(box, 6, 6)
        y = box.top() + 4
        for text_, color in rows:
            painter.setPen(color)
            painter.drawText(
                QRectF(box.left() + 8, y, width - 12, metrics.height()),
                Qt.AlignmentFlag.AlignVCenter,
                text_,
            )
            y += metrics.height() + 2

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        series = self._series_to_draw()
        hi = self._axis_hi(series)

        font = painter.font()
        font.setPixelSize(fs(11))
        painter.setFont(font)

        # Reserve room for the widest Y label so nothing is clipped at the edge.
        plot = self._plot_rect()
        left = plot.left()

        grid = QColor(BORDER)
        text = QColor(TEXT_DIM)

        # Horizontal grid + Y labels
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - frac * plot.height()
            painter.setPen(QPen(grid, 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            if frac in (0.0, 0.5, 1.0):
                painter.setPen(text)
                painter.drawText(
                    QRectF(0, y - 8, left - 8, 16),
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                    self._axis_label(hi, frac),
                )

        # Stretch the time axis to what we actually have, so the curve fills the
        # plot honestly right after startup instead of hugging the right edge.
        # Ticks sit on fixed second steps (-10s / -20s ... or -m:ss for long spans).
        count = len(self._times)
        if count > 1:
            dt = (self._times[-1] - self._times[0]) / (count - 1)
            span = dt * (count - 1)
        else:
            span = 0.0
        painter.setPen(text)
        for x, label in self._time_ticks(span, plot.width()):
            painter.drawText(
                QRectF(plot.left() + x - 30, plot.bottom() + 4, 60, 14),
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
        painter.drawText(
            QRectF(plot.right() - 60, plot.bottom() + 4, 60, 14),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            tr("dash_chart_now"),
        )

        multi = len(series) > 1
        for key, color, style in series:
            raw = self._history.get(key)
            if not raw or len(raw) < 2:
                continue
            values = self._smooth(list(raw))
            step = plot.width() / max(1, len(values) - 1)
            x0 = plot.right() - (len(values) - 1) * step

            path = QPainterPath()
            prev = None
            for i, v in enumerate(values):
                ratio = max(0.0, min(1.0, v / hi))
                pt = QPointF(x0 + i * step, plot.bottom() - ratio * plot.height())
                if prev is None:
                    path.moveTo(pt)
                else:
                    # Smooth cubic segment through the midpoint -> no jagged spikes.
                    mid = (prev.x() + pt.x()) / 2
                    path.cubicTo(QPointF(mid, prev.y()), QPointF(mid, pt.y()), pt)
                prev = pt
            last_x = x0 + (len(values) - 1) * step

            # Single-series tabs (and CPU in "All") get a gradient fill and a
            # 2px line; the other series stay thin 1px lines so they do not
            # fight the emphasized curve.
            with_fill, pen_width = chart_line_spec(key, multi)
            if with_fill:
                fill = QPainterPath(path)
                fill.lineTo(QPointF(last_x, plot.bottom()))
                fill.lineTo(QPointF(x0, plot.bottom()))
                fill.closeSubpath()
                top = QColor(color)
                top.setAlpha(38)
                fade = QColor(color)
                fade.setAlpha(0)
                gradient = QLinearGradient(0, plot.top(), 0, plot.bottom())
                gradient.setColorAt(0.0, top)
                gradient.setColorAt(1.0, fade)
                painter.fillPath(fill, gradient)

            pen = QPen(color, pen_width)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            if style == Qt.PenStyle.DashLine:
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setDashPattern([5.0, 4.0])
            painter.setPen(pen)
            painter.drawPath(path)

        self._paint_hover(painter, plot, series)


class _EmptyHint(QLabel):
    """Centered hint shown over a table viewport while the table has no rows."""

    def __init__(self, table, key: str) -> None:
        super().__init__(table.viewport())
        self._table = table
        self._key = key
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"color: {TEXT_DIM}; font-size: {fs(13)}px; background: transparent; padding: 24px;"
        )
        # Subtle HUD glyph above the copy so an empty table still looks designed.
        self.setPixmap(
            glyph("search", _mix(TEXT_DIM, PANEL, 0.35)).scaled(
                30, 30, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
        )
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
        card_shadow(self)
        hud_brackets(self)
        row = QHBoxLayout(self)
        row.setContentsMargins(CARD_PADDING, CARD_PADDING, 12, 12)
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
        card_shadow(self)
        hud_brackets(self)
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
        self._marker: float | None = None

    def set_percent(self, percent: float | None) -> None:
        self._percent = 0.0 if percent is None else max(0.0, min(100.0, float(percent)))
        self.update()

    def set_color(self, color: str) -> None:
        self._color = color
        self.update()

    def set_marker(self, marker: float | None) -> None:
        """Vertical threshold tick (e.g. 85 C) drawn over the fill."""
        self._marker = None if marker is None else max(0.0, min(100.0, float(marker)))
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
        if self._marker is not None and 0 < self._marker < 100:
            x = rect.left() + rect.width() * self._marker / 100.0
            x = min(max(x, rect.left() + 1), rect.right() - 1)
            tick = QColor(TEXT)
            tick.setAlpha(170)
            painter.setPen(QPen(tick, 2))
            painter.drawLine(QPointF(x, rect.top() + 1), QPointF(x, rect.bottom() - 1))


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
        card_shadow(self)
        hud_brackets(self)
        self._color = color

        layout = QVBoxLayout(self)
        layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        layout.setSpacing(4)

        heading = card_heading(title, color)
        layout.addWidget(heading)
        title_label = heading._label  # type: ignore[attr-defined]
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
        card_shadow(self)
        hud_brackets(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        self._layout.setSpacing(8)
        heading = card_heading(title)
        self._layout.addWidget(heading)
        self.title_label = heading._label  # type: ignore[attr-defined]
        self.body = QVBoxLayout()
        self.body.setSpacing(6)
        self._layout.addLayout(self.body)
        self._layout.addStretch(1)
        self._rows: dict[str, tuple[QLabel, Bar, QLabel]] = {}
        self._marker: float | None = None

    def set_title(self, text: str) -> None:
        self.title_label.setText(text.upper())

    def set_rows(self, items: list[tuple[str, float | None, str]], marker: float | None = None) -> None:
        self._marker = marker
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
            bar.set_marker(marker)
            text_label.setText(text)


class ValueListCard(QFrame):
    def __init__(self, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        card_shadow(self)
        hud_brackets(self)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        self._layout.setSpacing(6)
        heading = card_heading(title)
        self._layout.addWidget(heading)
        self.title_label = heading._label  # type: ignore[attr-defined]
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
