from __future__ import annotations

import getpass
import time
from collections.abc import Sequence

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.history import PerformanceHistory, downsample
from app.i18n import tr
from app.network import NetworkService
from app.processes import ProcessService
from app.sensors import Snapshot
from app.sensors.temperature_names import temperature_kind
from app.temperature import localized_temperature_notes, target_temperatures

from .activity import ActivityLog
from .components import CardPanel, CardTitleLabel, MetricCard, PerfChart, RingCard
from .dashboard_custom import DASH_WIDGET_KEYS, DASH_WIDGET_SECTION, parse_dashboard_hidden
from .format import gb as _gb
from .format import rate as _rate
from .format import zone_label
from .icons import glyph
from .tasks import Task
from .theme import (
    ACCENT,
    BORDER,
    BORDER_HI,
    BRAND_A,
    BRAND_B,
    C1,
    C2,
    C3,
    C4,
    CARD_PADDING,
    DANGER,
    FONT_MONO,
    HERO_TOP,
    OK,
    PANEL,
    PANEL_ALT,
    RADIUS_LG,
    RADIUS_MD,
    RADIUS_SM,
    RADIUS_XL,
    SPACING_LG,
    SPACING_MD,
    SPACING_SM,
    SPACING_XS,
    T_BODY,
    T_CAPTION,
    T_H1,
    T_H2,
    T_SMALL,
    T_TITLE,
    TEXT,
    TEXT_DIM,
    WARN,
    hud_brackets,
    set_mono,
)


def _greeting() -> str:
    hour = QDateTime.currentDateTime().time().hour()
    if hour < 5:
        return tr("dash_greet_night")
    if hour < 12:
        return tr("dash_greet_morning")
    if hour < 18:
        return tr("dash_greet_day")
    return tr("dash_greet_evening")


def _user_name() -> str:
    try:
        name = getpass.getuser()
    except Exception:
        name = ""
    return name.replace(".", " ").replace("_", " ").title() or tr("dash_user_fallback")


def _level_color(value: float) -> str:
    if value >= 95:
        return DANGER
    if value >= 85:
        return WARN
    return OK


def _activity_style(level: str) -> tuple[str, str]:
    """(color, glyph) for an activity-log entry level: ok / warn / error.

    Colours are read live from the theme module so a palette switch is honoured.
    """
    from . import theme

    if level == "ok":
        return theme.OK, "check"
    if level == "error":
        return theme.DANGER, "error"
    return theme.WARN, "warning"


class ResourceHistoryWidget(QWidget):
    """Last 60 minutes of recorded CPU/RAM/GPU samples (persistent history)."""

    def __init__(self, history: PerformanceHistory | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.history = history or PerformanceHistory()
        self._last_refresh = 0.0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING_XS)
        self.chart = PerfChart(title=tr("dash_hist_title"), points=120)
        layout.addWidget(self.chart, 1)
        self.info = QLabel("")
        self.info.setObjectName("cardSub")
        self.info.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        layout.addWidget(self.info)
        self.refresh()

    def refresh(self) -> None:
        self._last_refresh = time.monotonic()
        samples = self.history.query(60.0)
        self.chart.clear()
        if not samples:
            self.info.setText(tr("dash_hist_empty"))
            return
        for sample in downsample(samples, 120):
            self.chart.push(sample.ts, cpu=sample.cpu, ram=sample.ram, gpu=sample.gpu)
        self.info.setText(tr("hist_samples", count=len(samples)))

    def maybe_refresh(self) -> None:
        if time.monotonic() - self._last_refresh >= 30.0:
            self.refresh()

    def retranslate(self) -> None:
        self.chart.retranslate()
        self.chart.set_title(tr("dash_hist_title"))
        self.refresh()


class RecommendationsWidget(QFrame):
    """Actionable hints derived from the current snapshot."""

    action_triggered = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        self.title = CardTitleLabel(tr("dash_rec_title"), C1)
        layout.addWidget(self.title)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(SPACING_SM)
        layout.addLayout(self._rows)
        layout.addStretch(1)
        self._specs: list[tuple[str, dict[str, object], str | None]] = []
        self._render()

    def set_items(self, specs: list[tuple[str, dict[str, object], str | None]]) -> None:
        self._specs = list(specs)
        self._render()

    def _render(self) -> None:
        _clear_layout(self._rows)
        if not self._specs:
            hint = QLabel(tr("dash_rec_ok"))
            hint.setWordWrap(True)
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            hint.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT_DIM};")
            self._rows.addWidget(hint)
            return
        for key, fmt, target in self._specs:
            row = QHBoxLayout()
            row.setSpacing(SPACING_SM)
            dot = QLabel("●")
            dot.setStyleSheet(f"font-size: {T_CAPTION}px; color: {WARN if target else OK};")
            row.addWidget(dot)
            text = QLabel(tr(key, **fmt))
            text.setWordWrap(True)
            text.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT};")
            row.addWidget(text, 1)
            if target:
                button = QPushButton(tr("dash_rec_open"))
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.setProperty("secondary", True)
                button.setProperty("compact", True)
                button.style().unpolish(button)
                button.style().polish(button)
                button.clicked.connect(lambda _=False, t=target: self.action_triggered.emit(t))
                row.addWidget(button)
            self._rows.addLayout(row)

    def retranslate(self) -> None:
        self.title.setText(tr("dash_rec_title").upper())
        self._render()


class HealthWidget(QFrame):
    """PC Health card with cybernetic illustration and full check button."""

    full_check_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        # Graphic box
        graphic = QLabel()
        graphic.setPixmap(glyph("shield", C1).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        graphic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graphic.setFixedHeight(48)
        layout.addWidget(graphic)

        title = QLabel(tr("dash_health_title"))
        title.setStyleSheet(f"font-size: {T_BODY}px; font-weight: 700; color: {TEXT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.health_title = title

        score_row = QHBoxLayout()
        score_row.setSpacing(SPACING_SM)
        score_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.score_label = QLabel("—")
        self.score_label.setStyleSheet(f"font-family: {FONT_MONO}; font-size: {T_TITLE}px; font-weight: 800; color: {OK};")
        score_row.addWidget(self.score_label)

        sub_denom = QLabel("/100")
        sub_denom.setStyleSheet(f"font-size: {T_BODY}px; font-weight: 600; color: {TEXT_DIM};")
        score_row.addWidget(sub_denom)
        layout.addLayout(score_row)

        self.badge = QLabel("")
        self.badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.badge)

        layout.addStretch(1)

        self.button = QPushButton(tr("dash_health_btn"))
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B}); "
            f"color: #FFFFFF; font-weight: 700; font-size: {T_BODY}px; border: none; border-radius: {RADIUS_MD}px; padding: 7px 12px;"
        )
        self.button.clicked.connect(self.full_check_clicked.emit)
        layout.addWidget(self.button)
        ActivityLog.instance().changed.connect(self._refresh_state)
        self._refresh_state()

    def _refresh_state(self) -> None:
        info = ActivityLog.instance().health
        if info is None:
            self.score_label.setText("—")
            color, text = TEXT_DIM, tr("dash_health_unknown")
        else:
            score, grade = info
            self.score_label.setText(str(score))
            color = OK if score >= 80 else WARN if score >= 60 else DANGER
            from .health import grade_text

            text = f"● {grade_text(grade)}"
        self.score_label.setStyleSheet(f"font-family: {FONT_MONO}; font-size: {T_TITLE}px; font-weight: 800; color: {color};")
        self.badge.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {color};")
        self.badge.setText(text)

    def retranslate(self) -> None:
        self.health_title.setText(tr("dash_health_title"))
        self._refresh_state()
        self.button.setText(tr("dash_health_btn"))


class QuickActionsWidget(QFrame):
    """Quick action vertical buttons list."""

    action_triggered = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel(tr("dash_qa_title"))
        title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.qa_title = title

        actions = (
            ("cleaner", "dash_qa_clean", "cleaner"),
            ("bolt", "dash_qa_optimize", "optimizer"),
            ("gaming", "dash_qa_gaming", "gaming"),
            ("cleaner", "dash_qa_cache", "cleaner"),
            ("processes", "dash_qa_tasks", "processes"),
        )
        self.buttons: list[QPushButton] = []
        for icon_key, text_key, target in actions:
            btn = QPushButton(f"  {tr(text_key)}")
            btn.setIcon(glyph(icon_key, C1))
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background: {PANEL_ALT}; border: 1px solid {BORDER}; "
                f"border-radius: {RADIUS_SM}px; color: {TEXT}; font-size: {T_SMALL}px; font-weight: 600; text-align: left; padding: 6px 10px; }} "
                f"QPushButton:hover {{ background: rgba(30, 107, 255, 0.2); border-color: {ACCENT}; color: {TEXT}; }}"
            )
            btn.clicked.connect(lambda _=False, t=target: self.action_triggered.emit(t))
            layout.addWidget(btn)
            self.buttons.append(btn)

    def retranslate(self) -> None:
        self.qa_title.setText(tr("dash_qa_title"))
        keys = ("dash_qa_clean", "dash_qa_optimize", "dash_qa_gaming", "dash_qa_cache", "dash_qa_tasks")
        for btn, key in zip(self.buttons, keys, strict=False):
            btn.setText(f"  {tr(key)}")


def _clear_layout(lay) -> None:
    while lay.count():
        item = lay.takeAt(0)
        child = item.layout()
        if child is not None:
            _clear_layout(child)
        elif item.widget() is not None:
            item.widget().deleteLater()


class GamingBannerWidget(QFrame):
    """Banner for Game Mode with glowing accents."""

    configure_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {PANEL}, stop:1 {HERO_TOP}); "
            f"border: 1px solid rgba(30, 107, 255, 0.4); border-radius: {RADIUS_XL}px; }}"
        )
        hud_brackets(self)
        row = QHBoxLayout(self)
        row.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        row.setSpacing(SPACING_LG)

        icon_label = QLabel()
        icon_label.setPixmap(glyph("gaming", C1).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        row.addWidget(icon_label)

        info_box = QVBoxLayout()
        info_box.setSpacing(SPACING_XS)
        h_row = QHBoxLayout()
        h_row.setSpacing(SPACING_SM)
        title = QLabel(tr("dash_gaming_banner"))
        title.setStyleSheet(f"font-size: {T_H2}px; font-weight: 800; color: {TEXT};")
        h_row.addWidget(title)
        self.banner_title = title
        self.status_badge = QLabel("")
        self.status_badge.setStyleSheet(
            f"background: rgba(0, 229, 153, 0.15); color: {OK}; font-size: {T_CAPTION}px; font-weight: 700; "
            f"border: 1px solid rgba(0, 229, 153, 0.3); border-radius: {RADIUS_SM}px; padding: 2px 7px;"
        )
        self.status_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        h_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        h_row.addStretch(1)
        info_box.addLayout(h_row)

        self.banner_desc = QLabel(tr("dash_gaming_desc"))
        self.banner_desc.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT_DIM};")
        info_box.addWidget(self.banner_desc)
        row.addLayout(info_box, 1)

        self.configure_button = QPushButton(tr("dash_gaming_btn"))
        self.configure_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.configure_button.setStyleSheet(
            f"QPushButton {{ background: rgba(30, 107, 255, 0.2); border: 1px solid {ACCENT}; "
            f"color: {TEXT}; font-size: {T_BODY}px; font-weight: 700; border-radius: {RADIUS_MD}px; padding: 6px 14px; }} "
            f"QPushButton:hover {{ background: {ACCENT}; }}"
        )
        self.configure_button.clicked.connect(self.configure_clicked.emit)
        row.addWidget(self.configure_button)
        ActivityLog.instance().changed.connect(self._refresh_state)
        self._refresh_state()

    def _refresh_state(self) -> None:
        on = ActivityLog.instance().gaming_active
        self.status_badge.setText(tr("dash_gaming_active") if on else tr("dash_gaming_off"))
        color, bg = (OK, "rgba(0, 229, 153, 0.15)") if on else (TEXT_DIM, "rgba(130, 146, 170, 0.15)")
        self.status_badge.setStyleSheet(
            f"background: {bg}; color: {color}; font-size: {T_CAPTION}px; font-weight: 700; "
            f"border-radius: {RADIUS_SM}px; padding: 2px 7px;"
        )

    def retranslate(self) -> None:
        self.banner_title.setText(tr("dash_gaming_banner"))
        self._refresh_state()
        self.banner_desc.setText(tr("dash_gaming_desc"))
        self.configure_button.setText(tr("dash_gaming_btn"))


class RecentActionsWidget(QFrame):
    """Recent actions log widget with checkmark items."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(220)
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel(tr("dash_recent_title"))
        title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.recent_title = title

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        host = QWidget()
        host.setStyleSheet("background: transparent;")
        self._rows = QVBoxLayout(host)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(SPACING_SM)
        self._rows.addStretch(1)
        scroll.setWidget(host)
        layout.addWidget(scroll, 1)
        self._scroll = scroll
        self._log = ActivityLog.instance()
        self._log.changed.connect(self._render)
        self._render()

    def _render(self) -> None:
        _clear_layout(self._rows)
        entries = self._log.entries(limit=20)
        if not entries:
            self._rows.addStretch(1)
            empty = QLabel(tr("act_empty"))
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT_DIM};")
            self._rows.addWidget(empty)
            self._rows.addStretch(1)
            return
        for e in entries:
            color, icon = _activity_style(e.level)
            r = QHBoxLayout()
            r.setSpacing(SPACING_SM)
            chk = QLabel()
            chk.setPixmap(glyph(icon, color).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            r.addWidget(chk)
            t_lbl = QLabel(e.title)
            t_lbl.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT};")
            t_lbl.setWordWrap(True)
            r.addWidget(t_lbl, 1)
            val_col = QVBoxLayout()
            val_col.setSpacing(1)
            v_lbl = QLabel(e.detail)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            v_lbl.setWordWrap(True)
            v_lbl.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {color};")
            tm_lbl = QLabel(e.time_text)
            tm_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            tm_lbl.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
            val_col.addWidget(v_lbl)
            val_col.addWidget(tm_lbl)
            r.addLayout(val_col)
            self._rows.addLayout(r)
        self._rows.addStretch(1)

    def retranslate(self) -> None:
        self.recent_title.setText(tr("dash_recent_title"))
        self._render()


class ProcessLoadWidget(QFrame):
    """Top active processes list with resource utilization."""

    view_all_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        head = QHBoxLayout()
        title = QLabel(tr("dash_proc_title"))
        title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        head.addWidget(title)
        self.proc_title = title
        head.addStretch(1)

        more_btn = QPushButton(tr("dash_proc_more"))
        more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        more_btn.setStyleSheet(f"background: transparent; border: none; color: {ACCENT}; font-size: {T_SMALL}px; font-weight: 600;")
        more_btn.clicked.connect(self.view_all_clicked.emit)
        head.addWidget(more_btn)
        self.more_button = more_btn
        layout.addLayout(head)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(SPACING_SM)
        layout.addLayout(self._rows_box)
        layout.addStretch(1)
        self.set_rows([])

    def set_rows(self, procs: list[tuple[str, float, int]]) -> None:
        """Show the top processes: (name, cpu %, memory in MB)."""
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            if item is None:
                continue
            lay = item.layout()
            if lay is not None:
                while lay.count():
                    child = lay.takeAt(0)
                    if child is None:
                        continue
                    w = child.widget()
                    if w is not None:
                        w.deleteLater()
            else:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        if not procs:
            empty = QLabel("…")
            empty.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT_DIM};")
            self._rows_box.addWidget(empty)
            return
        for name, cpu, mem_mb in procs:
            row = QHBoxLayout()
            row.setSpacing(SPACING_SM)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT}; font-size: {T_CAPTION}px;")
            row.addWidget(dot)

            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {TEXT};")
            row.addWidget(n_lbl, 1)

            c_lbl = QLabel(f"{cpu:.1f}%")
            c_lbl.setMinimumWidth(36)
            c_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            c_lbl.setStyleSheet(
                f"font-size: {T_SMALL}px; font-weight: 700; color: {DANGER};" if cpu > 10
                else f"font-size: {T_SMALL}px; font-weight: 600; color: {TEXT_DIM};"
            )
            row.addWidget(c_lbl)

            mem = f"{mem_mb / 1024:.1f} GB" if mem_mb >= 1024 else f"{mem_mb:.0f} MB"
            m_lbl = QLabel(mem)
            m_lbl.setMinimumWidth(48)
            m_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            m_lbl.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {TEXT_DIM};")
            row.addWidget(m_lbl)
            self._rows_box.addLayout(row)

    def retranslate(self) -> None:
        self.proc_title.setText(tr("dash_proc_title"))
        self.more_button.setText(tr("dash_proc_more"))


class NetworkWidget(QFrame):
    """Network connection status, speeds and diagnostics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel(tr("dash_net_title"))
        title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.net_title = title

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACING_SM)
        net_icon = QLabel()
        net_icon.setPixmap(glyph("network", C1).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        top_row.addWidget(net_icon)

        conn_info = QVBoxLayout()
        conn_info.setSpacing(1)
        self.name_label = QLabel("Ethernet")
        self.name_label.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        self.ping_label = QLabel(tr("dash_ping_none"))
        self.ping_label.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        conn_info.addWidget(self.name_label)
        conn_info.addWidget(self.ping_label)
        top_row.addLayout(conn_info, 1)

        speed_box = QHBoxLayout()
        speed_box.setSpacing(SPACING_MD)
        
        down_col = QVBoxLayout()
        down_col.setSpacing(1)
        d_lbl = QLabel(tr("dash_net_download"))
        d_lbl.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        self.down_val = QLabel("—")
        self.down_val.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {C2};")
        down_col.addWidget(d_lbl)
        down_col.addWidget(self.down_val)
        speed_box.addLayout(down_col)
        self.down_caption = d_lbl

        up_col = QVBoxLayout()
        up_col.setSpacing(1)
        u_lbl = QLabel(tr("dash_net_upload"))
        u_lbl.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        self.up_val = QLabel("—")
        self.up_val.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {WARN};")
        up_col.addWidget(u_lbl)
        up_col.addWidget(self.up_val)
        speed_box.addLayout(up_col)
        self.up_caption = u_lbl

        top_row.addLayout(speed_box)
        layout.addLayout(top_row)

        # Diagnostics pills
        diag_row = QHBoxLayout()
        diag_row.setSpacing(SPACING_SM)
        self.diag_pills: list[QLabel] = []
        for item_key in ("dash_net_internet", "dash_net_dns", "dash_net_gateway", "dash_net_loss", "dash_net_latency"):
            p = QLabel(f"✓ {tr(item_key, pct=0)}")
            p.setStyleSheet(f"font-size: {T_CAPTION}px; font-weight: 600; color: {OK}; background: rgba(0, 229, 153, 0.1); border-radius: {RADIUS_SM}px; padding: 2px 5px;")
            diag_row.addWidget(p)
            p.hide()  # no live diagnostics on the dashboard (run them on the Network page)
            self.diag_pills.append(p)
        diag_row.addStretch(1)
        layout.addLayout(diag_row)

    def retranslate(self) -> None:
        self.net_title.setText(tr("dash_net_title"))
        self.down_caption.setText(tr("dash_net_download"))
        self.up_caption.setText(tr("dash_net_upload"))
        keys = ("dash_net_internet", "dash_net_dns", "dash_net_gateway", "dash_net_loss", "dash_net_latency")
        for pill, key in zip(self.diag_pills, keys, strict=False):
            pill.setText(f"✓ {tr(key, pct=0)}")


class NotificationsWidget(QFrame):
    """Recent notification highlights list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: {RADIUS_LG}px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        hud_brackets(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        title = QLabel(tr("dash_notif_title"))
        title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.notif_title = title

        self._rows = QVBoxLayout()
        self._rows.setSpacing(SPACING_SM)
        layout.addLayout(self._rows)
        layout.addStretch(1)
        self._live: str = ""
        self._log = ActivityLog.instance()
        self._log.changed.connect(self._render)
        self._render()

    def set_live_warning(self, text: str) -> None:
        if text != self._live:
            self._live = text
            self._render()

    def _render(self) -> None:
        _clear_layout(self._rows)
        items = []
        if self._live:
            items.append(("warning", WARN, self._live, "", ""))
        # Warnings AND errors — a failed operation must be visible here too.
        events = self._log.entries(level="warn", limit=3) + self._log.entries(level="error", limit=3)
        for e in sorted(events, key=lambda e: e.ts, reverse=True):
            color, icon = _activity_style(e.level)
            items.append((icon, color, e.title, e.detail, e.time_text))
        # An empty notifications card just wastes space — hide it instead.
        self.setVisible(bool(items))
        if not items:
            empty = QLabel(tr("notif_empty"))
            empty.setStyleSheet(f"font-size: {T_SMALL}px; color: {TEXT_DIM};")
            self._rows.addWidget(empty)
            return
        for ic, col, head_txt, sub_txt, time_str in items[:4]:
            r = QHBoxLayout()
            r.setSpacing(SPACING_SM)
            i_lbl = QLabel()
            i_lbl.setPixmap(glyph(ic, col).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            r.addWidget(i_lbl)
            col_box = QVBoxLayout()
            col_box.setSpacing(1)
            h = QLabel(head_txt)
            h.setWordWrap(True)
            h.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {TEXT};")
            col_box.addWidget(h)
            if sub_txt:
                sl = QLabel(sub_txt)
                sl.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
                col_box.addWidget(sl)
            r.addLayout(col_box, 1)
            if time_str:
                t = QLabel(time_str)
                t.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
                r.addWidget(t)
            self._rows.addLayout(r)

    def retranslate(self) -> None:
        self.notif_title.setText(tr("dash_notif_title"))
        self._render()


class DashboardPage(QWidget):
    navigate = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        history: PerformanceHistory | None = None,
        dashboard_hidden: str | set[str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._hidden_widgets = parse_dashboard_hidden(dashboard_hidden or "")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)

        inner = QWidget()
        inner.setAutoFillBackground(False)
        scroll.setWidget(inner)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        layout.setSpacing(SPACING_MD)

        # Header titles (greeting + status + clock)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self._user_display = _user_name()
        hud_row = QHBoxLayout()
        hud_row.setSpacing(SPACING_SM)
        hud_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        hud_tag = QLabel(tr("dash_hud_status"))
        hud_tag.setObjectName("hudTag")
        set_mono(hud_tag, size=T_CAPTION, weight=QFont.Weight.DemiBold, spacing_pct=18.0)
        hud_row.addWidget(hud_tag)
        self.greeting = QLabel(f"{_greeting()}, {self._user_display}!")
        self.greeting.setObjectName("welcome")
        self.greeting.setStyleSheet(f"font-size: {T_H1}px; font-weight: 800; color: {TEXT};")
        hud_row.addWidget(self.greeting)
        hud_row.addStretch(1)
        titles.addLayout(hud_row)
        self._verdict_key = "dash_verdict_ok"
        self.verdict = QLabel(tr(self._verdict_key))
        self.verdict.setObjectName("pageDesc")
        titles.addWidget(self.verdict)
        head.addLayout(titles)
        head.addStretch(1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock = QLabel("")
        self.clock.setObjectName("clock")
        self.clock.setStyleSheet(f"font-size: {T_H2}px; font-weight: 700; color: {TEXT};")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock)
        self.date = QLabel("")
        self.date.setObjectName("cardSub")
        self.date.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        self.date.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.date)
        head.addLayout(clock_box)
        self.clock.hide()  # the clock already lives in the top bar
        self.date.hide()
        layout.addLayout(head)

        def _section(key: str) -> CardTitleLabel:
            return CardTitleLabel(tr(key), C1)

        self._section_keys = (
            "dash_sec_overview",
            "dash_sec_monitoring",
            "dash_sec_system",
            "dash_sec_activity",
        )
        self.sections = [_section(key) for key in self._section_keys]

        # ZONE 1 — live overview: rings, hottest sensor and health score.
        layout.addWidget(self.sections[0])
        row1 = QGridLayout()
        row1.setSpacing(SPACING_SM)

        self.cpu = RingCard(tr("dash_cpu"), C2, icon_name="cpu")
        self.cpu.set_center_sub(tr("dash_ring_load"))
        self.ram = RingCard(tr("dash_mem"), WARN, icon_name="ram")
        self.ram.set_center_sub(tr("dash_ring_used"))
        self.gpu = RingCard(tr("dash_gpu"), C3, icon_name="gpu")
        self.gpu.set_center_sub(tr("dash_ring_load"))
        self.disk = RingCard(tr("dash_ring_disks"), C4, icon_name="disk")
        self.disk.set_center_sub(tr("dash_ring_full"))
        self.temp_tile = MetricCard(tr("dash_temp"), sparkline=False, bar=False, color=WARN)
        self.temp_tile.update_metric("—", tr("dash_temp_none"))

        # Clicking a card opens the page with the matching detail view.
        self.cpu.clicked.connect(lambda: self.navigate.emit("monitor"))
        self.ram.clicked.connect(lambda: self.navigate.emit("monitor"))
        self.gpu.clicked.connect(lambda: self.navigate.emit("gpu"))
        self.disk.clicked.connect(lambda: self.navigate.emit("disk"))

        self.health_card = HealthWidget()
        self.health_card.full_check_clicked.connect(lambda: self.navigate.emit("health"))
        self._device_name_cache: dict[str, str] | None = None
        layout.addLayout(row1)

        # ZONE 2 — live chart, persistent 60-minute history and temperatures.
        layout.addWidget(self.sections[1])
        row2 = QGridLayout()
        row2.setSpacing(SPACING_SM)
        self.chart = PerfChart(points=3600, enable_range=True)
        self.chart.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.history_widget = ResourceHistoryWidget(history)
        self.thermal = CardPanel(tr("dash_thermals_title"))
        self.fans = CardPanel(tr("dash_fans_title"))
        self.fans.hide()  # no fan sensor data is collected
        self.thermal.set_rows([])
        layout.addLayout(row2)

        # ZONE 3 — storage, top processes and shortcuts.
        layout.addWidget(self.sections[2])
        row3 = QGridLayout()
        row3.setSpacing(SPACING_SM)
        self.disks = CardPanel(tr("dash_disks_title"))
        self.disks.set_rows([])
        self.proc_load = ProcessLoadWidget()
        self.proc_load.view_all_clicked.connect(lambda: self.navigate.emit("processes"))
        self.quick_actions = QuickActionsWidget()
        self.quick_actions.action_triggered.connect(self.navigate.emit)
        layout.addLayout(row3)

        row4 = QGridLayout()
        row4.setSpacing(SPACING_SM)
        self.gaming_banner = GamingBannerWidget()
        self.gaming_banner.configure_clicked.connect(lambda: self.navigate.emit("gaming"))
        self.net_widget = NetworkWidget()
        self.notif_widget = NotificationsWidget()
        layout.addLayout(row4)

        # ZONE 4 — recent actions and actionable recommendations.
        layout.addWidget(self.sections[3])
        row5 = QGridLayout()
        row5.setSpacing(SPACING_SM)
        self.recent_actions = RecentActionsWidget()
        self.recommendations = RecommendationsWidget()
        self.recommendations.action_triggered.connect(self.navigate.emit)
        self.recommendations.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.recommendations.setMinimumHeight(220)
        row5.setRowStretch(0, 1)
        row5.setRowStretch(1, 1)
        layout.addLayout(row5, 1)

        # Responsive layout: (widget, row, col, colspan) per mode on a 12-column grid.
        r1 = [self.cpu, self.ram, self.gpu, self.disk, self.temp_tile, self.health_card]
        r2 = [self.chart, self.history_widget, self.thermal]
        r3 = [self.disks, self.proc_load, self.quick_actions]
        r4 = [self.gaming_banner, self.net_widget, self.notif_widget]
        r5 = [self.recent_actions, self.recommendations]
        self._grid_rows: dict[str, tuple[QGridLayout, Sequence[QWidget]]] = {
            "row1": (row1, r1),
            "row2": (row2, r2),
            "row3": (row3, r3),
            "row4": (row4, r4),
            "row5": (row5, r5),
        }
        self._row_widget_keys = {
            "row1": ("cpu", "ram", "gpu", "disk", "temp", "health"),
            "row2": ("chart", "history", "thermal"),
            "row3": ("disks", "processes", "quick"),
            "row4": ("gaming", "network", "notifications"),
            "row5": ("recent", "recommendations"),
        }
        self._widget_map = {
            "cpu": self.cpu,
            "ram": self.ram,
            "gpu": self.gpu,
            "disk": self.disk,
            "temp": self.temp_tile,
            "health": self.health_card,
            "chart": self.chart,
            "history": self.history_widget,
            "thermal": self.thermal,
            "disks": self.disks,
            "processes": self.proc_load,
            "quick": self.quick_actions,
            "gaming": self.gaming_banner,
            "network": self.net_widget,
            "notifications": self.notif_widget,
            "recent": self.recent_actions,
            "recommendations": self.recommendations,
        }
        self._mode = ""
        self._apply_hidden_visibility()
        self._relayout(1200)

        # Real top-process list (refreshed every 3 s on a worker thread).
        self._proc_service = ProcessService()
        self._proc_task: Task | None = None
        self._proc_timer = QTimer(self)
        self._proc_timer.timeout.connect(self._refresh_processes)
        self._proc_timer.start(3000)
        QTimer.singleShot(400, self._refresh_processes)

        self._net_service = NetworkService()
        self._ping_task: Task | None = None
        self._ping_timer = QTimer(self)
        self._ping_timer.timeout.connect(self._refresh_ping)
        self._ping_timer.start(20000)
        QTimer.singleShot(1500, self._refresh_ping)

        # Keep self.net MetricCard for full test compatibility (hidden or minimal)
        self.net = MetricCard("Network", sparkline=False, bar=False)
        self.net.hide()
        layout.addWidget(self.net)

        self.errors = QLabel("")
        self.errors.setObjectName("errorLine")
        self.errors.setVisible(False)
        layout.addWidget(self.errors)

    def closeEvent(self, event) -> None:
        self._proc_timer.stop()
        self._ping_timer.stop()
        if self._proc_task and self._proc_task.isRunning():
            self._proc_task.requestInterruption()
            self._proc_task.wait(3000)
        if self._ping_task and self._ping_task.isRunning():
            self._ping_task.requestInterruption()
            # ping(count=1) is bounded to ~5s in NetworkService; wait at least
            # that long so shutdown does not leave a live task registered.
            self._ping_task.wait(6000)
        super().closeEvent(event)

    def _apply_hidden_visibility(self) -> None:
        for key in DASH_WIDGET_KEYS:
            self._widget_map[key].setVisible(key not in self._hidden_widgets)
        for section in range(len(self.sections)):
            visible = any(
                DASH_WIDGET_SECTION[key] == section and key not in self._hidden_widgets
                for key in DASH_WIDGET_KEYS
            )
            self.sections[section].setVisible(visible)

    def set_hidden_widgets(self, hidden: object) -> None:
        self._hidden_widgets = parse_dashboard_hidden(hidden)
        self._apply_hidden_visibility()
        self._mode = ""
        self._relayout(self.width() or 1200)

    def _refresh_ping(self) -> None:
        if self._ping_task is not None or not self.isVisible() or "network" in self._hidden_widgets:
            return

        def ping_once() -> object:
            # Keep the dashboard probe short so window shutdown does not wait on
            # a long external ping command.
            probe = self._ping_task
            if probe is None or probe.isInterruptionRequested():
                return None
            try:
                result = self._net_service.ping(count=1)
            except Exception:
                return None
            return None if probe.isInterruptionRequested() else result

        self._ping_task = Task(ping_once, parent=self)
        self._ping_task.done.connect(self._apply_ping)
        self._ping_task.failed.connect(lambda _m: self._apply_ping(None))
        self._ping_task.start()

    def _apply_ping(self, result: object) -> None:
        self._ping_task = None
        avg = getattr(result, "avg_ms", None)
        try:
            self.net_widget.ping_label.setText(f"Ping {avg} ms" if avg is not None else tr("dash_ping_none"))
        except RuntimeError:
            pass

    def _refresh_processes(self) -> None:
        if self._proc_task is not None or not self.isVisible() or "processes" in self._hidden_widgets:
            return
        self._proc_task = Task(self._proc_service.list, parent=self)
        self._proc_task.done.connect(self._apply_processes)
        self._proc_task.failed.connect(lambda _msg: setattr(self, "_proc_task", None))
        self._proc_task.start()

    def _apply_processes(self, infos: object) -> None:
        self._proc_task = None
        if not isinstance(infos, list):
            return
        try:
            top = [p for p in infos if p.name.lower() not in ("system idle process", "system")][:5]
            self.proc_load.set_rows([(p.name, p.cpu_percent, p.memory_bytes / (1024 * 1024)) for p in top])
        except RuntimeError:
            pass

    def _relayout(self, width: int) -> None:
        """Responsive grid (12 columns): wide / mid / compact, so nothing is cut off."""
        mode = "wide" if width >= 1500 else ("mid" if width >= 960 else "compact")
        if mode == self._mode:
            return
        self._mode = mode
        spec: dict[str, list[tuple[int, int, int]]] = {
            "wide": {
                "row1": [(0, 0, 2), (0, 2, 2), (0, 4, 2), (0, 6, 2), (0, 8, 2), (0, 10, 2)],
                "row2": [(0, 0, 5), (0, 5, 4), (0, 9, 3)],
                "row3": [(0, 0, 4), (0, 4, 4), (0, 8, 4)],
                "row4": [(0, 0, 4), (0, 4, 4), (0, 8, 4)],
                "row5": [(0, 0, 6), (0, 6, 6)],
            },
            "mid": {
                "row1": [(0, 0, 4), (0, 4, 4), (0, 8, 4), (1, 0, 4), (1, 4, 4), (1, 8, 4)],
                "row2": [(0, 0, 12), (1, 0, 6), (1, 6, 6)],
                "row3": [(0, 0, 4), (0, 4, 4), (0, 8, 4)],
                "row4": [(0, 0, 12), (1, 0, 6), (1, 6, 6)],
                "row5": [(0, 0, 6), (0, 6, 6)],
            },
            "compact": {
                "row1": [(0, 0, 6), (0, 6, 6), (1, 0, 6), (1, 6, 6), (2, 0, 6), (2, 6, 6)],
                "row2": [(0, 0, 12), (1, 0, 12), (2, 0, 12)],
                "row3": [(0, 0, 12), (1, 0, 6), (1, 6, 6)],
                "row4": [(0, 0, 12), (1, 0, 6), (1, 6, 6)],
                "row5": [(0, 0, 12), (1, 0, 12)],
            },
        }[mode]
        for key, (grid, widgets) in self._grid_rows.items():
            for w in widgets:
                grid.removeWidget(w)
            for widget_key, (r, c, span) in zip(self._row_widget_keys[key], spec[key], strict=False):
                if widget_key in self._hidden_widgets:
                    continue
                grid.addWidget(self._widget_map[widget_key], r, c, 1, span)
            for col in range(12):
                grid.setColumnStretch(col, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout(event.size().width())

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self.greeting.setText(f"{_greeting()}, {self._user_display}!")
        self.verdict.setText(tr(self._verdict_key))
        for label, key in zip(self.sections, self._section_keys, strict=False):
            label.setText(tr(key).upper())
        self.cpu.set_center_sub(tr("dash_ring_load"))
        self.cpu.set_header(tr("dash_cpu") + getattr(self, "_cpu_head_suffix", ""))
        self.ram.set_center_sub(tr("dash_ring_used"))
        self.gpu.set_center_sub(tr("dash_ring_load"))
        self.disk.set_center_sub(tr("dash_ring_full"))
        self.temp_tile.set_title(tr("dash_temp"))
        self.thermal.set_title(tr("dash_thermals_title"))
        self.fans.set_title(tr("dash_fans_title"))
        self.disks.set_title(tr("dash_disks_title"))
        self.chart.retranslate()
        self.history_widget.retranslate()
        for widget in (
            self.health_card,
            self.quick_actions,
            self.gaming_banner,
            self.recent_actions,
            self.proc_load,
            self.net_widget,
            self.notif_widget,
            self.recommendations,
        ):
            widget.retranslate()

    def _device_names(self, s: Snapshot) -> dict[str, str]:
        if self._device_name_cache is not None:
            names = dict(self._device_name_cache)
            gpus = [g for g in (getattr(s, "gpus", ()) or ()) if not getattr(g, "stale", False)]
            if gpus:
                gpu_name = str(getattr(gpus[0], "name", "") or "").strip()
                if gpu_name:
                    names["gpu"] = gpu_name
            return names
        names = {"cpu": "", "board": "", "gpu": ""}
        cpu_name = str(getattr(getattr(s, "cpu", None), "name", "") or "").strip()
        if not cpu_name:
            try:
                from app.hardware.service import HardwareService

                cpu_name = str(getattr(HardwareService()._cpu([]), "name", "") or "").strip()
            except Exception:
                cpu_name = ""
        names["cpu"] = cpu_name
        gpus = [g for g in (getattr(s, "gpus", ()) or ()) if not getattr(g, "stale", False)]
        if gpus:
            names["gpu"] = str(getattr(gpus[0], "name", "") or "").strip()
        thermal = getattr(s, "thermal", None)
        for raw, _value in (getattr(thermal, "temperatures", ()) or ()):
            text = str(raw).strip()
            if temperature_kind(text) != "board":
                continue
            label = zone_label(text)
            if label and label.strip().casefold() not in {
                "board",
                "motherboard",
                "mainboard",
                "system board",
                "материнка",
                "материнська плата",
            }:
                names["board"] = label
                break
        if not names["board"]:
            try:
                from app.hardware.service import HardwareService

                info = HardwareService()._board([])
                parts = [p for p in (info.manufacturer, info.product) if p]
                names["board"] = " ".join(parts).strip()
            except Exception:
                pass
        self._device_name_cache = dict(names)
        return names

    def apply_snapshot(self, s: Snapshot) -> None:
        from PySide6.QtCore import QLocale

        now = QDateTime.currentDateTime()
        self.clock.setText(now.toString("HH:mm"))
        self.date.setText(QLocale().toString(now, "ddd d MMM"))

        temps = list(s.thermal.temperatures) if s.thermal else []
        targets = target_temperatures(s)
        cpu_temp = targets["cpu"][0]
        gpu_temp = targets["gpu"][0]
        all_temps = list(temps)
        if gpu_temp is not None:
            all_temps.append((tr("temp_target_gpu"), gpu_temp))
        hottest = max(all_temps, key=lambda item: item[1], default=None)
        if hottest is not None:
            self.temp_tile.update_metric(f"{hottest[1]:.0f}°C", tr("dash_temp_sub"))
        else:
            self.temp_tile.update_metric("—", tr("dash_temp_none"))

        cpu_pct = ram_pct = gpu_pct = None
        if s.cpu:
            c = s.cpu
            cpu_pct = c.percent
            freq_head = f"{c.physical_cores}C / {c.logical_cores}T" if c.freq_mhz is None else f"{c.freq_mhz / 1000:.1f} GHz"
            self._cpu_head_suffix = f" · {freq_head}"
            self.cpu.set_header(tr("dash_cpu") + self._cpu_head_suffix)
            self.cpu.update_metric(
                f"{c.percent:.0f}%",
                tr("dash_freq_sub", freq=c.freq_mhz / 1000) if c.freq_mhz else tr("dash_threads_sub", logical=c.logical_cores),
                percent=c.percent,
                spark=c.percent,
                extra=f"{cpu_temp:.0f}°C" if cpu_temp is not None else "",
                extra_color=_level_color(cpu_temp) if cpu_temp is not None else OK,
            )

        if s.memory:
            m = s.memory
            ram_pct = m.percent
            total_gb = m.total / (1024**3)
            self.ram.set_header(f"{total_gb:.0f} GB RAM")
            self.ram.update_metric(
                f"{m.percent:.0f}%",
                f"{_gb(m.used)} / {_gb(m.total)}",
                percent=m.percent,
                spark=m.percent,
                extra=tr("dash_free", size=_gb(m.available)),
            )

        g = s.gpu
        if g:
            gpu_pct = g.utilization
            vram = f"{_gb(g.memory_used)} / {_gb(g.memory_total)}"
            self.gpu.set_header(g.name or "NVIDIA GPU")
            self.gpu.update_metric(
                f"{g.utilization:.0f}%",
                vram,
                percent=g.utilization,
                spark=g.utilization,
                extra=f"{g.temperature:.0f}°C" if g.temperature is not None else "",
                extra_color=_level_color(g.temperature) if g.temperature is not None else OK,
            )
        else:
            self.gpu.set_header("GPU")
            self.gpu.update_metric("—", tr("dash_no_gpu"))

        full_disk = None
        if s.disks:
            main = next((d for d in s.disks if d.mountpoint.upper().startswith("C")), s.disks[0])
            self.disk.set_header(f"{main.mountpoint.rstrip(chr(92) + '/') or main.device}")
            self.disk.update_metric(
                f"{main.percent:.0f}%",
                f"{_gb(main.used)} / {_gb(main.total)}",
                percent=main.percent,
                spark=main.percent,
                extra=tr("dash_free", size=_gb(main.free)),
                extra_color=_level_color(main.percent),
            )
            rows: list[tuple[str, float | None, str]] = [
                (d.mountpoint.rstrip("\\/") or d.device, d.percent, f"{_gb(d.used)} / {_gb(d.total)}")
                for d in s.disks
            ]
            self.disks.set_rows(rows)
            full_disk = next((d for d in s.disks if d.percent >= 80), None)
            self.notif_widget.set_live_warning(
                tr("notif_disk_full", mount=full_disk.mountpoint.rstrip("\\/") or full_disk.device, pct=int(full_disk.percent))
                if full_disk else ""
            )

        net_down = None
        net_up = None
        if s.net:
            n = s.net
            net_down = n.recv_rate
            net_up = n.send_rate
            self.net.update_metric(
                f"{_rate(n.recv_rate)}/s",
                f"up {_rate(n.send_rate)}/s · total ↓{_gb(n.bytes_recv)} ↑{_gb(n.bytes_sent)}",
                percent=None,
                spark=n.recv_rate,
            )
            self.net_widget.down_val.setText(f"{_rate(n.recv_rate)}/s")
            self.net_widget.up_val.setText(f"{_rate(n.send_rate)}/s")

        self.chart.push(s.ts, cpu=cpu_pct, ram=ram_pct, gpu=gpu_pct, net_down=net_down, net_up=net_up)
        self.history_widget.maybe_refresh()

        loads = [v for v in (cpu_pct, ram_pct) if v is not None]
        peak = max(loads) if loads else None
        if peak is None:
            self._verdict_key = "dash_verdict_waiting"
        elif peak >= 90:
            self._verdict_key = "dash_verdict_high"
        elif peak >= 75:
            self._verdict_key = "dash_verdict_active"
        else:
            self._verdict_key = "dash_verdict_ok"
        self.verdict.setText(tr(self._verdict_key))

        device_names = self._device_names(s)
        thermal_rows: list[tuple[str, float | None, str]] = []
        for kind, key in (
            ("cpu", "temp_target_cpu"),
            ("board", "temp_target_board"),
            ("gpu", "temp_target_gpu"),
        ):
            value, _source = targets[kind]
            label = tr(key)
            device = device_names.get(kind, "")
            if device:
                label = f"{label} · {device}"
            thermal_rows.append(
                (
                    label,
                    None if value is None else min(value, 100.0),
                    "—" if value is None else f"{value:.0f}°C",
                )
            )
        for name, value in temps:
            if temperature_kind(name) in ("cpu", "board", "gpu"):
                continue
            thermal_rows.append((zone_label(name), min(value, 100.0), f"{value:.0f}°C"))
        self.thermal.set_rows(thermal_rows, marker=85.0)
        thermal_notes = " · ".join(localized_temperature_notes(s))
        self.thermal.setToolTip(thermal_notes)
        self.thermal.title_label.setToolTip(thermal_notes)

        recs: list[tuple[str, dict[str, object], str | None]] = []
        if cpu_pct is not None and cpu_pct >= 90:
            recs.append(("dash_rec_high_cpu", {"pct": int(cpu_pct)}, "processes"))
        if gpu_pct is not None and gpu_pct >= 90:
            recs.append(("dash_rec_high_gpu", {"pct": int(gpu_pct)}, "gpu"))
        if hottest is not None and hottest[1] >= 85:
            recs.append(("dash_rec_hot", {"temp": int(hottest[1])}, "temperature"))
        if full_disk is not None:
            recs.append((
                "dash_rec_disk",
                {"mount": full_disk.mountpoint.rstrip("\\/") or full_disk.device, "pct": int(full_disk.percent)},
                "cleaner",
            ))
        health = ActivityLog.instance().health
        if health is not None and health[0] < 70:
            recs.append(("dash_rec_health", {"score": health[0]}, "health"))
        self.recommendations.set_items(recs[:4])

        shown_errors = {k: v for k, v in s.errors.items() if k != "thermal"}
        if shown_errors:
            self.errors.setText(tr("dash_sensors_err", msg=" · ".join(f"{k}: {v}" for k, v in shown_errors.items())))
            self.errors.setVisible(True)
        else:
            self.errors.setVisible(False)
            self.errors.setText("")
