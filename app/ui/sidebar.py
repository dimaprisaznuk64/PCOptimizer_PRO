from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .icons import nav_icon
from .theme import (
    BORDER,
    BRAND_A,
    BRAND_B,
    C1,
    OK,
    PANEL,
    T_BRAND,
    T_CAPTION,
    T_MICRO,
    T_SMALL,
    TEXT,
    TEXT_DIM,
)

# Sidebar widths: the full rail shows labels, the compact rail is icons only.
SIDEBAR_WIDTH = 238
SIDEBAR_COMPACT_WIDTH = 64

NAV_KEYS: tuple[tuple[str, str], ...] = (
    ("dashboard", "nav_dashboard"),
    ("monitor", "nav_monitor"),
    ("hardware", "nav_hardware"),
    ("cleaner", "nav_cleaner"),
    ("processes", "nav_processes"),
    ("startup", "nav_startup"),
    ("gaming", "nav_gaming"),
    ("launcher", "nav_launcher"),
    ("benchmarks", "nav_benchmarks"),
    ("history", "nav_history"),
    ("network", "nav_network"),
    ("optimizer", "nav_optimizer"),
    ("disk", "nav_disk"),
    ("diagnostics", "nav_diagnostics"),
    ("settings", "nav_settings"),
    ("gpu", "nav_gpu"),
    ("health", "nav_health"),
)

NAV_ITEMS: tuple[tuple[str, str], ...] = tuple((k, tr(kk)) for k, kk in NAV_KEYS)

NAV_SECTIONS: dict[str, str] = {}


class _LogoMark(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, 36, 36)
        grad.setColorAt(0.0, QColor(BRAND_A))
        grad.setColorAt(1.0, QColor(BRAND_B))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        path.addRoundedRect(2, 2, 32, 32, 9, 9)
        p.drawPath(path)
        p.setPen(QColor("#FFFFFF"))
        font = p.font()
        font.setBold(True)
        font.setPointSize(11)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "PC")


class Sidebar(QWidget):
    navigated = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)
        self._compact = False
        self._status_text = tr("status_healthy")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 14)
        layout.setSpacing(2)

        brand_box = QWidget()
        brand_box.setObjectName("brandBox")
        brand_row = QHBoxLayout(brand_box)
        brand_row.setContentsMargins(16, 10, 16, 10)
        brand_row.setSpacing(10)
        self._brand_row = brand_row

        mark = _LogoMark()
        brand_row.addWidget(mark)

        titles_box = QWidget()
        titles = QVBoxLayout(titles_box)
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(1)
        self._brand_titles = titles_box
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        brand = QLabel("PCOptimizer")
        brand.setObjectName("brand")
        brand.setMinimumWidth(0)
        brand.setStyleSheet(f"font-size: {T_BRAND}px; font-weight: 800; color: {TEXT};")
        title_row.addWidget(brand)
        pro_badge = QLabel("PRO")
        pro_badge.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B}); "
            f"color: #FFFFFF; font-size: {T_MICRO}px; font-weight: 800; border-radius: 4px; padding: 1px 5px;"
        )
        title_row.addWidget(pro_badge)
        title_row.addStretch(1)
        titles.addLayout(title_row)

        self.brand_subtitle = QLabel(tr("app_subtitle"))
        self.brand_subtitle.setObjectName("brandSub")
        self.brand_subtitle.setWordWrap(True)
        self.brand_subtitle.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        titles.addWidget(self.brand_subtitle)
        brand_row.addWidget(titles_box, 1)
        layout.addWidget(brand_box)

        # Scrollable nav list so every item stays reachable when the window is
        # short; the list scrolls instead of the bottom block getting squeezed.
        self._nav_host = QWidget()
        self._nav_host.setObjectName("navHost")
        nav_layout = QVBoxLayout(self._nav_host)
        nav_layout.setContentsMargins(0, 0, 0, 0)
        nav_layout.setSpacing(1)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._nav_tr = dict(NAV_KEYS)
        self._buttons: dict[str, QPushButton] = {}
        for key, _tr_key in NAV_KEYS:
            button = QPushButton(f"  {tr(_tr_key)}")
            button.setAccessibleName(tr(_tr_key))
            button.setProperty("nav", True)
            button.setIcon(nav_icon(key))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.installEventFilter(self)  # own hover state (Qt's :hover can get stuck)
            button.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            nav_layout.addWidget(button)
            self._group.addButton(button)
            self._buttons[key] = button

        nav_layout.addStretch(1)

        self.nav_scroll = QScrollArea()
        self.nav_scroll.setObjectName("navScroll")
        self.nav_scroll.setWidgetResizable(True)
        self.nav_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.nav_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.nav_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.nav_scroll.setMinimumHeight(96)
        self.nav_scroll.viewport().setAutoFillBackground(False)
        self._nav_host.setAutoFillBackground(False)
        self.nav_scroll.setWidget(self._nav_host)
        layout.addWidget(self.nav_scroll, 1)

        # Bottom card
        user_card = QFrame()
        self.user_card = user_card
        user_card.setObjectName("card")
        user_card.setStyleSheet(
            f"QFrame#card {{ background: {PANEL}; border: 1px solid {BORDER}; "
            "border-radius: 12px; margin: 0px 12px 10px 12px; padding: 6px; } "
            "QFrame#card QLabel { background: transparent; border: none; padding: 0; margin: 0; }"
        )
        user_row = QHBoxLayout(user_card)
        user_row.setContentsMargins(8, 8, 8, 8)
        user_row.setSpacing(10)
        from .icons import glyph
        shield_icon = QLabel()
        shield_icon.setPixmap(glyph("shield", C1).scaled(20, 20, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        shield_icon.setFixedSize(22, 22)
        user_row.addWidget(shield_icon)

        user_text = QVBoxLayout()
        user_text.setSpacing(2)
        self.u_title = QLabel(tr("sidebar_user_title"))
        self.u_title.setWordWrap(True)
        self.u_title.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 700; color: {TEXT};")
        self.u_sub = QLabel(tr("sidebar_user_sub"))
        self.u_sub.setWordWrap(True)
        self.u_sub.setStyleSheet(f"font-size: {T_CAPTION}px; color: {TEXT_DIM};")
        user_text.addWidget(self.u_title)
        user_text.addWidget(self.u_sub)
        user_row.addLayout(user_text, 1)

        bottom = QWidget()
        bottom.setObjectName("sideBottom")
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(2)
        bottom_layout.addWidget(user_card)

        # Status pill
        self.status = QLabel(f"● {self._status_text}")
        self.status.setObjectName("sysStatus")
        self.status.setProperty("level", "ok")
        self.status.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: 4px 18px;")
        bottom_layout.addWidget(self.status)
        self._bottom = bottom
        layout.addWidget(bottom)

        self.select("dashboard")

    def set_compact(self, compact: bool) -> None:
        """Switch between the full rail (labels) and the icon-only rail.

        The compact rail is used on narrow windows so the page keeps as much
        horizontal room as possible. Labels move into the tooltips.
        """
        if compact == self._compact:
            return
        self._compact = compact
        self.setFixedWidth(SIDEBAR_COMPACT_WIDTH if compact else SIDEBAR_WIDTH)

        self._brand_titles.setVisible(not compact)
        self._brand_row.setContentsMargins(
            (14 if compact else 16), 10, (14 if compact else 16), 10
        )

        for key, button in self._buttons.items():
            label = tr(self._nav_tr[key])
            button.setText("" if compact else f"  {label}")
            button.setToolTip(label if compact else "")
            button.setProperty("compact", compact)
            button.style().unpolish(button)
            button.style().polish(button)

        self.user_card.setVisible(not compact)
        self._apply_status()

    @property
    def compact(self) -> bool:
        return self._compact

    def _apply_status(self) -> None:
        if self._compact:
            self.status.setText("●")
            self.status.setToolTip(self._status_text)
            self.status.setStyleSheet(
                f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: 4px 0px;"
            )
        else:
            self.status.setText(f"● {self._status_text}")
            self.status.setToolTip("")
            self.status.setStyleSheet(
                f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: 4px 18px;"
            )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # The nav list scrolls on its own, so the info card only yields on very
        # short windows where even the status pill would be cramped.
        self.user_card.setVisible(not self._compact and self.height() >= 620)

    def retranslate(self) -> None:
        """Refresh static texts after a language change (nav + brand + user card)."""
        for key, tr_key in self._nav_tr.items():
            label = tr(tr_key)
            button = self._buttons[key]
            button.setText("" if self._compact else f"  {label}")
            button.setToolTip(label if self._compact else "")
            button.setAccessibleName(label)
        self.brand_subtitle.setText(tr("app_subtitle"))
        self.u_title.setText(tr("sidebar_user_title"))
        self.u_sub.setText(tr("sidebar_user_sub"))
        self._status_text = tr("status_healthy")
        self._apply_status()

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._buttons)

    def set_health(self, text: str, level: str) -> None:
        self._status_text = text
        self._apply_status()
        if self.status.property("level") != level:
            self.status.setProperty("level", level)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)

    def _set_hot(self, active: QPushButton | None) -> None:
        for b in self._buttons.values():
            hot = b is active
            if bool(b.property("hot")) != hot:
                b.setProperty("hot", hot)
                b.style().unpolish(b)
                b.style().polish(b)

    def eventFilter(self, obj, event) -> bool:
        kind = event.type()
        if kind == QEvent.Type.Enter and obj in self._buttons.values():
            self._set_hot(obj)
        elif kind in (QEvent.Type.Leave, QEvent.Type.Hide, QEvent.Type.WindowDeactivate):
            self._set_hot(None)
        return False

    def leaveEvent(self, event) -> None:
        self._set_hot(None)
        super().leaveEvent(event)

    def set_current(self, key: str) -> None:
        self._set_hot(None)
        button = self._buttons.get(key)
        if button is not None:
            button.setChecked(True)

    def select(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        button.setChecked(True)
        self.navigated.emit(key)
