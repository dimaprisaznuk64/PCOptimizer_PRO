from __future__ import annotations

import getpass

from PySide6.QtCore import QDateTime, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
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

from app.i18n import tr
from app.network import NetworkService
from app.processes import ProcessService
from app.sensors import Snapshot

from .activity import ActivityLog
from .components import CardPanel, MetricCard, PerfChart, QuickButton, RingCard
from .format import gb as _gb
from .format import zone_label
from .format import rate as _rate
from .icons import glyph
from .tasks import Task
from .theme import ACCENT, BORDER, BORDER_HI, BRAND_A, BRAND_B, C1, C2, C3, C4, DANGER, HERO_TOP, OK, PANEL, PANEL_ALT, TEXT, TEXT_DIM, WARN, fs


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


class HealthWidget(QFrame):
    """PC Health card with cybernetic illustration and full check button."""

    full_check_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Graphic box
        graphic = QLabel()
        graphic.setPixmap(glyph("shield", C1).scaled(40, 40, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        graphic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        graphic.setFixedHeight(48)
        layout.addWidget(graphic)

        title = QLabel(tr("dash_health_title"))
        title.setStyleSheet(f"font-size: {fs(13)}px; font-weight: 700; color: {TEXT};")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        self.health_title = title

        score_row = QHBoxLayout()
        score_row.setSpacing(6)
        score_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.score_label = QLabel("—")
        self.score_label.setStyleSheet(f"font-size: {fs(26)}px; font-weight: 800; color: {OK};")
        score_row.addWidget(self.score_label)

        sub_denom = QLabel("/100")
        sub_denom.setStyleSheet(f"font-size: {fs(13)}px; font-weight: 600; color: {TEXT_DIM};")
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
            f"color: #FFFFFF; font-weight: 700; font-size: {fs(12)}px; border: none; border-radius: 8px; padding: 7px 12px;"
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
        self.score_label.setStyleSheet(f"font-size: {fs(26)}px; font-weight: 800; color: {color};")
        self.badge.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 600; color: {color};")
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
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        title = QLabel(tr("dash_qa_title"))
        title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
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
                f"border-radius: 7px; color: {TEXT}; font-size: {fs(12)}px; font-weight: 600; text-align: left; padding: 6px 10px; }} "
                f"QPushButton:hover {{ background: rgba(30, 107, 255, 0.2); border-color: {ACCENT}; color: {TEXT}; }}"
            )
            btn.clicked.connect(lambda _=False, t=target: self.action_triggered.emit(t))
            layout.addWidget(btn)
            self.buttons.append(btn)

    def retranslate(self) -> None:
        self.qa_title.setText(tr("dash_qa_title"))
        keys = ("dash_qa_clean", "dash_qa_optimize", "dash_qa_gaming", "dash_qa_cache", "dash_qa_tasks")
        for btn, key in zip(self.buttons, keys):
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
            "border: 1px solid rgba(30, 107, 255, 0.4); border-radius: 14px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(18, 14, 18, 14)
        row.setSpacing(14)

        icon_label = QLabel()
        icon_label.setPixmap(glyph("gaming", C1).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        row.addWidget(icon_label)

        info_box = QVBoxLayout()
        info_box.setSpacing(3)
        h_row = QHBoxLayout()
        h_row.setSpacing(8)
        title = QLabel(tr("dash_gaming_banner"))
        title.setStyleSheet(f"font-size: {fs(14)}px; font-weight: 800; color: {TEXT};")
        h_row.addWidget(title)
        self.banner_title = title
        self.status_badge = QLabel("")
        self.status_badge.setStyleSheet(
            f"background: rgba(0, 229, 153, 0.15); color: {OK}; font-size: {fs(11)}px; font-weight: 700; "
            "border: 1px solid rgba(0, 229, 153, 0.3); border-radius: 6px; padding: 2px 7px;"
        )
        self.status_badge.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        h_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignVCenter)
        h_row.addStretch(1)
        info_box.addLayout(h_row)

        self.banner_desc = QLabel(tr("dash_gaming_desc"))
        self.banner_desc.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
        info_box.addWidget(self.banner_desc)
        row.addLayout(info_box, 1)

        self.configure_button = QPushButton(tr("dash_gaming_btn"))
        self.configure_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.configure_button.setStyleSheet(
            f"QPushButton {{ background: rgba(30, 107, 255, 0.2); border: 1px solid {ACCENT}; "
            f"color: {TEXT}; font-size: {fs(12)}px; font-weight: 700; border-radius: 8px; padding: 6px 14px; }} "
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
            f"background: {bg}; color: {color}; font-size: {fs(11)}px; font-weight: 700; "
            "border-radius: 6px; padding: 2px 7px;"
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
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel(tr("dash_recent_title"))
        title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.recent_title = title

        self._rows = QVBoxLayout()
        self._rows.setSpacing(8)
        layout.addLayout(self._rows)
        layout.addStretch(1)
        self._log = ActivityLog.instance()
        self._log.changed.connect(self._render)
        self._render()

    def _render(self) -> None:
        _clear_layout(self._rows)
        entries = self._log.entries(limit=4)
        if not entries:
            empty = QLabel(tr("act_empty"))
            empty.setWordWrap(True)
            empty.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
            self._rows.addWidget(empty)
            return
        for e in entries:
            color = OK if e.level == "ok" else WARN
            r = QHBoxLayout()
            r.setSpacing(8)
            chk = QLabel()
            chk.setPixmap(glyph("check" if e.level == "ok" else "warning", color).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            r.addWidget(chk)
            t_lbl = QLabel(e.title)
            t_lbl.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT};")
            r.addWidget(t_lbl, 1)
            val_col = QVBoxLayout()
            val_col.setSpacing(1)
            v_lbl = QLabel(e.detail)
            v_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            v_lbl.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {color};")
            tm_lbl = QLabel(e.time_text)
            tm_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            tm_lbl.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
            val_col.addWidget(v_lbl)
            val_col.addWidget(tm_lbl)
            r.addLayout(val_col)
            self._rows.addLayout(r)

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
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        head = QHBoxLayout()
        title = QLabel(tr("dash_proc_title"))
        title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        head.addWidget(title)
        self.proc_title = title
        head.addStretch(1)

        more_btn = QPushButton(tr("dash_proc_more"))
        more_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        more_btn.setStyleSheet(f"background: transparent; border: none; color: {ACCENT}; font-size: {fs(12)}px; font-weight: 700;")
        more_btn.clicked.connect(self.view_all_clicked.emit)
        head.addWidget(more_btn)
        self.more_button = more_btn
        layout.addLayout(head)

        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(8)
        layout.addLayout(self._rows_box)
        layout.addStretch(1)
        self.set_rows([])

    def set_rows(self, procs: list[tuple[str, float, int]]) -> None:
        """Show the top processes: (name, cpu %, memory in MB)."""
        while self._rows_box.count():
            item = self._rows_box.takeAt(0)
            lay = item.layout()
            if lay is not None:
                while lay.count():
                    w = lay.takeAt(0).widget()
                    if w is not None:
                        w.deleteLater()
            elif item.widget() is not None:
                item.widget().deleteLater()
        if not procs:
            empty = QLabel("…")
            empty.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
            self._rows_box.addWidget(empty)
            return
        for name, cpu, mem_mb in procs:
            row = QHBoxLayout()
            row.setSpacing(8)
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {ACCENT}; font-size: {fs(11)}px;")
            row.addWidget(dot)

            n_lbl = QLabel(name)
            n_lbl.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 600; color: {TEXT};")
            row.addWidget(n_lbl, 1)

            c_lbl = QLabel(f"{cpu:.1f}%")
            c_lbl.setMinimumWidth(48)
            c_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            c_lbl.setStyleSheet(
                f"font-size: {fs(12)}px; font-weight: 700; color: {DANGER};" if cpu > 10
                else f"font-size: {fs(12)}px; font-weight: 600; color: {TEXT_DIM};"
            )
            row.addWidget(c_lbl)

            mem = f"{mem_mb / 1024:.1f} GB" if mem_mb >= 1024 else f"{mem_mb:.0f} MB"
            m_lbl = QLabel(mem)
            m_lbl.setMinimumWidth(62)
            m_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            m_lbl.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 600; color: {TEXT_DIM};")
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
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)

        title = QLabel(tr("dash_net_title"))
        title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.net_title = title

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        net_icon = QLabel()
        net_icon.setPixmap(glyph("network", C1).scaled(18, 18, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        top_row.addWidget(net_icon)

        conn_info = QVBoxLayout()
        conn_info.setSpacing(1)
        self.name_label = QLabel("Ethernet")
        self.name_label.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        self.ping_label = QLabel(tr("dash_ping_none"))
        self.ping_label.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        conn_info.addWidget(self.name_label)
        conn_info.addWidget(self.ping_label)
        top_row.addLayout(conn_info, 1)

        speed_box = QHBoxLayout()
        speed_box.setSpacing(12)
        
        down_col = QVBoxLayout()
        down_col.setSpacing(1)
        d_lbl = QLabel(tr("dash_net_download"))
        d_lbl.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        self.down_val = QLabel("—")
        self.down_val.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {C1};")
        down_col.addWidget(d_lbl)
        down_col.addWidget(self.down_val)
        speed_box.addLayout(down_col)
        self.down_caption = d_lbl

        up_col = QVBoxLayout()
        up_col.setSpacing(1)
        u_lbl = QLabel(tr("dash_net_upload"))
        u_lbl.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        self.up_val = QLabel("—")
        self.up_val.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {C2};")
        up_col.addWidget(u_lbl)
        up_col.addWidget(self.up_val)
        speed_box.addLayout(up_col)
        self.up_caption = u_lbl

        top_row.addLayout(speed_box)
        layout.addLayout(top_row)

        # Diagnostics pills
        diag_row = QHBoxLayout()
        diag_row.setSpacing(8)
        self.diag_pills: list[QLabel] = []
        for item_key in ("dash_net_internet", "dash_net_dns", "dash_net_gateway", "dash_net_loss", "dash_net_latency"):
            p = QLabel(f"✓ {tr(item_key, pct=0)}")
            p.setStyleSheet(f"font-size: {fs(11)}px; font-weight: 600; color: {OK}; background: rgba(0, 229, 153, 0.1); border-radius: 4px; padding: 2px 5px;")
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
        for pill, key in zip(self.diag_pills, keys):
            pill.setText(f"✓ {tr(key, pct=0)}")


class NotificationsWidget(QFrame):
    """Recent notification highlights list."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            f"border-radius: 14px; }} QFrame#card:hover {{ border-color: {BORDER_HI}; }}"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QLabel(tr("dash_notif_title"))
        title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        layout.addWidget(title)
        self.notif_title = title

        self._rows = QVBoxLayout()
        self._rows.setSpacing(8)
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
        for e in self._log.entries(level="warn", limit=3):
            items.append(("warning", WARN, e.title, e.detail, e.time_text))
        if not items:
            empty = QLabel(tr("notif_empty"))
            empty.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
            self._rows.addWidget(empty)
            return
        for ic, col, head_txt, sub_txt, time_str in items[:4]:
            r = QHBoxLayout()
            r.setSpacing(8)
            i_lbl = QLabel()
            i_lbl.setPixmap(glyph(ic, col).scaled(14, 14, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            r.addWidget(i_lbl)
            col_box = QVBoxLayout()
            col_box.setSpacing(1)
            h = QLabel(head_txt)
            h.setWordWrap(True)
            h.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 600; color: {TEXT};")
            col_box.addWidget(h)
            if sub_txt:
                sl = QLabel(sub_txt)
                sl.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
                col_box.addWidget(sl)
            r.addLayout(col_box, 1)
            if time_str:
                t = QLabel(time_str)
                t.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
                r.addWidget(t)
            self._rows.addLayout(r)

    def retranslate(self) -> None:
        self.notif_title.setText(tr("dash_notif_title"))
        self._render()


class DashboardPage(QWidget):
    navigate = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        outer.addWidget(scroll)

        inner = QWidget()
        inner.setAutoFillBackground(False)
        scroll.setWidget(inner)

        layout = QVBoxLayout(inner)
        layout.setContentsMargins(40, 20, 40, 24)
        layout.setSpacing(14)

        # Header titles (greeting + status + clock)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self._user_display = _user_name()
        self.greeting = QLabel(f"{_greeting()}, {self._user_display}!")
        self.greeting.setObjectName("welcome")
        self.greeting.setStyleSheet(f"font-size: {fs(18)}px; font-weight: 800; color: {TEXT};")
        titles.addWidget(self.greeting)
        self._verdict_key = "dash_verdict_ok"
        self.verdict = QLabel(tr(self._verdict_key))
        self.verdict.setObjectName("pageDesc")
        self.verdict.setStyleSheet(f"font-size: {fs(12)}px; color: {TEXT_DIM};")
        titles.addWidget(self.verdict)
        head.addLayout(titles)
        head.addStretch(1)

        clock_box = QVBoxLayout()
        clock_box.setSpacing(0)
        self.clock = QLabel("")
        self.clock.setObjectName("clock")
        self.clock.setStyleSheet(f"font-size: {fs(14)}px; font-weight: 700; color: {TEXT};")
        self.clock.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.clock)
        self.date = QLabel("")
        self.date.setObjectName("cardSub")
        self.date.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        self.date.setAlignment(Qt.AlignmentFlag.AlignRight)
        clock_box.addWidget(self.date)
        head.addLayout(clock_box)
        self.clock.hide()  # the clock already lives in the top bar
        self.date.hide()
        layout.addLayout(head)

        # ROW 1: 4 RingCards + PC Health + Quick Actions
        row1 = QGridLayout()
        row1.setSpacing(12)

        self.cpu = RingCard(tr("dash_cpu"), C1, icon_name="cpu")
        self.cpu.set_center_sub(tr("dash_ring_load"))
        self.ram = RingCard(tr("dash_mem"), C2, icon_name="ram")
        self.ram.set_center_sub(tr("dash_ring_used"))
        self.gpu = RingCard(tr("dash_gpu"), C3, icon_name="gpu")
        self.gpu.set_center_sub(tr("dash_ring_load"))
        self.disk = RingCard(tr("dash_ring_disks"), C4, icon_name="disk")
        self.disk.set_center_sub(tr("dash_ring_full"))


        self.health_card = HealthWidget()
        self.health_card.full_check_clicked.connect(lambda: self.navigate.emit("health"))

        self.quick_actions = QuickActionsWidget()
        self.quick_actions.action_triggered.connect(self.navigate.emit)

        layout.addLayout(row1)

        # ROW 2: System Load Chart + Temperatures + Fans
        self._grids: dict[str, QGridLayout] = {}
        row2 = QGridLayout()
        row2.setSpacing(12)

        self.chart = PerfChart()
        self.thermal = CardPanel(tr("dash_thermals_title"))
        self.fans = CardPanel(tr("dash_fans_title"))
        # Default fans items
        self.fans.hide()  # no fan sensor data is collected
        self.thermal.set_rows([])
        layout.addLayout(row2)

        # ROW 3: Storage + Recent Actions + Process Load
        row3 = QGridLayout()
        row3.setSpacing(12)

        self.disks = CardPanel(tr("dash_disks_title"))
        self.disks.set_rows([])
        self.recent_actions = RecentActionsWidget()
        self.proc_load = ProcessLoadWidget()
        self.proc_load.view_all_clicked.connect(lambda: self.navigate.emit("processes"))
        layout.addLayout(row3)

        # ROW 4: Gaming Banner + Network + Notifications
        row4 = QGridLayout()
        row4.setSpacing(12)

        self.gaming_banner = GamingBannerWidget()
        self.gaming_banner.configure_clicked.connect(lambda: self.navigate.emit("gaming"))
        self.net_widget = NetworkWidget()
        self.notif_widget = NotificationsWidget()
        layout.addLayout(row4)

        # Responsive layout: (widget, row, col, colspan) per mode on a 12-column grid.
        r1 = [self.cpu, self.ram, self.gpu, self.disk, self.health_card, self.quick_actions]
        self._grid_rows = {"row1": (row1, r1), "row2": (row2, [self.chart, self.thermal]),
                           "row3": (row3, [self.disks, self.recent_actions, self.proc_load]),
                           "row4": (row4, [self.gaming_banner, self.net_widget, self.notif_widget])}
        self._mode = ""
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

    def _refresh_ping(self) -> None:
        if self._ping_task is not None or not self.isVisible():
            return
        self._ping_task = Task(lambda: self._net_service.ping(count=1), parent=self)
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
        if self._proc_task is not None or not self.isVisible():
            return
        self._proc_task = Task(self._proc_service.list, parent=self)
        self._proc_task.done.connect(self._apply_processes)
        self._proc_task.failed.connect(lambda _msg: setattr(self, "_proc_task", None))
        self._proc_task.start()

    def _apply_processes(self, infos: object) -> None:
        self._proc_task = None
        try:
            top = [p for p in infos if p.name.lower() not in ("system idle process", "system")][:5]  # type: ignore[union-attr]
            self.proc_load.set_rows([(p.name, p.cpu_percent, p.memory_bytes / (1024 * 1024)) for p in top])
        except RuntimeError:
            pass

    def _relayout(self, width: int) -> None:
        """Responsive grid (12 columns): wide / mid / compact, so nothing is cut off."""
        mode = "wide" if width >= 1500 else ("mid" if width >= 960 else "compact")
        if mode == self._mode:
            return
        self._mode = mode
        spec = {
            "wide": {
                "row1": [(0, 0, 2), (0, 2, 2), (0, 4, 2), (0, 6, 2), (0, 8, 2), (0, 10, 2)],
                "row2": [(0, 0, 8), (0, 8, 4)],
                "row3": [(0, 0, 4), (0, 4, 4), (0, 8, 4)],
                "row4": [(0, 0, 5), (0, 5, 4), (0, 9, 3)],
            },
            "mid": {
                "row1": [(0, 0, 4), (0, 4, 4), (0, 8, 4), (1, 0, 4), (1, 4, 4), (1, 8, 4)],
                "row2": [(0, 0, 12), (1, 0, 12)],
                "row3": [(0, 0, 4), (0, 4, 4), (0, 8, 4)],
                "row4": [(0, 0, 12), (1, 0, 7), (1, 7, 5)],
            },
            "compact": {
                "row1": [(0, 0, 6), (0, 6, 6), (1, 0, 6), (1, 6, 6), (2, 0, 6), (2, 6, 6)],
                "row2": [(0, 0, 12), (1, 0, 12)],
                "row3": [(0, 0, 12), (1, 0, 6), (1, 6, 6)],
                "row4": [(0, 0, 12), (1, 0, 7), (1, 7, 5)],
            },
        }[mode]
        for key, (grid, widgets) in self._grid_rows.items():
            for w in widgets:
                grid.removeWidget(w)
            for w, (r, c, span) in zip(widgets, spec[key]):
                grid.addWidget(w, r, c, 1, span)
            for c in range(12):
                grid.setColumnStretch(c, 1)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._relayout(event.size().width())

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self.greeting.setText(f"{_greeting()}, {self._user_display}!")
        self.verdict.setText(tr(self._verdict_key))
        self.cpu.set_center_sub(tr("dash_ring_load"))
        self.ram.set_center_sub(tr("dash_ring_used"))
        self.gpu.set_center_sub(tr("dash_ring_load"))
        self.disk.set_center_sub(tr("dash_ring_full"))
        self.thermal.set_title(tr("dash_thermals_title"))
        self.fans.set_title(tr("dash_fans_title"))
        self.disks.set_title(tr("dash_disks_title"))
        self.chart.retranslate()
        for widget in (
            self.health_card,
            self.quick_actions,
            self.gaming_banner,
            self.recent_actions,
            self.proc_load,
            self.net_widget,
            self.notif_widget,
        ):
            widget.retranslate()

    def apply_snapshot(self, s: Snapshot) -> None:
        now = QDateTime.currentDateTime()
        self.clock.setText(now.toString("HH:mm"))
        self.date.setText(now.toString("ddd, d MMM"))

        temps = list(s.thermal.temperatures) if s.thermal else []
        cpu_temp = next((v for n, v in temps if "cpu" in n.lower() or "core" in n.lower() or "package" in n.lower()), None)
        if cpu_temp is None and temps:
            cpu_temp = temps[0][1]

        cpu_pct = ram_pct = gpu_pct = None
        if s.cpu:
            c = s.cpu
            cpu_pct = c.percent
            self.cpu.set_header(f"{c.physical_cores}C / {c.logical_cores}T" if c.freq_mhz is None else f"{c.freq_mhz / 1000:.1f} GHz")
            self.cpu.update_metric(
                f"{c.percent:.0f}%",
                tr("dash_freq_sub", freq=c.freq_mhz / 1000) if c.freq_mhz else tr("dash_threads_sub", logical=c.logical_cores),
                percent=c.percent,
                spark=c.percent,
                extra=f"{cpu_temp:.0f}°C" if cpu_temp is not None else "",
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
            )
        else:
            self.gpu.set_header("GPU")
            self.gpu.update_metric("—", tr("dash_no_gpu"))

        if s.disks:
            main = next((d for d in s.disks if d.mountpoint.upper().startswith("C")), s.disks[0])
            self.disk.set_header(f"{main.mountpoint.rstrip(chr(92) + '/') or main.device}")
            self.disk.update_metric(
                f"{main.percent:.0f}%",
                f"{_gb(main.used)} / {_gb(main.total)}",
                percent=main.percent,
                spark=main.percent,
                extra=tr("dash_free", size=_gb(main.free)),
            )
            rows = [
                (d.mountpoint.rstrip("\\/") or d.device, d.percent, f"{_gb(d.used)} / {_gb(d.total)}")
                for d in s.disks
            ]
            self.disks.set_rows(rows)
            full = next((d for d in s.disks if d.percent >= 85), None)
            self.notif_widget.set_live_warning(
                tr("notif_disk_full", mount=full.mountpoint.rstrip("\\/") or full.device, pct=int(full.percent)) if full else ""
            )

        net_rate = None
        if s.net:
            n = s.net
            net_rate = n.recv_rate
            self.net.update_metric(
                f"{_rate(n.recv_rate)}/s",
                f"up {_rate(n.send_rate)}/s · total ↓{_gb(n.bytes_recv)} ↑{_gb(n.bytes_sent)}",
                percent=None,
                spark=n.recv_rate,
            )
            self.net_widget.down_val.setText(f"{_rate(n.recv_rate)}/s")
            self.net_widget.up_val.setText(f"{_rate(n.send_rate)}/s")

        self.chart.push(s.ts, cpu=cpu_pct, ram=ram_pct, gpu=gpu_pct, net=net_rate)

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

        if temps:
            self.thermal.set_rows([(zone_label(name), min(value, 100.0), f"{value:.0f}°C") for name, value in temps])

        if s.errors:
            self.errors.setText(tr("dash_sensors_err", msg=" · ".join(f"{k}: {v}" for k, v in s.errors.items())))
            self.errors.setVisible(True)
        else:
            self.errors.setVisible(False)
            self.errors.setText("")
