from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from app.i18n import tr

from .icons import nav_icon
from .theme import BORDER, BRAND_A, BRAND_B, C1, NAV_WIDTH, OK, PANEL, TEXT, TEXT_DIM, fs

NAV_KEYS: tuple[tuple[str, str], ...] = (
    ("dashboard", "nav_dashboard"),
    ("monitor", "nav_monitor"),
    ("cleaner", "nav_cleaner"),
    ("processes", "nav_processes"),
    ("startup", "nav_startup"),
    ("gaming", "nav_gaming"),
    ("network", "nav_network"),
    ("optimizer", "nav_optimizer"),
    ("disk", "nav_disk"),
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
        self.setFixedWidth(238)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 12, 0, 14)
        layout.setSpacing(2)

        brand_box = QWidget()
        brand_box.setObjectName("brandBox")
        brand_row = QHBoxLayout(brand_box)
        brand_row.setContentsMargins(18, 12, 18, 20)
        brand_row.setSpacing(12)

        mark = _LogoMark()
        brand_row.addWidget(mark)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        brand = QLabel("PCOptimizer")
        brand.setObjectName("brand")
        brand.setStyleSheet(f"font-size: {fs(15)}px; font-weight: 800; color: {TEXT};")
        title_row.addWidget(brand)
        pro_badge = QLabel("PRO")
        pro_badge.setStyleSheet(
            f"background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B}); "
            f"color: #FFFFFF; font-size: {fs(11)}px; font-weight: 800; border-radius: 4px; padding: 2px 5px;"
        )
        title_row.addWidget(pro_badge)
        title_row.addStretch(1)
        titles.addLayout(title_row)

        self.brand_subtitle = QLabel(tr("app_subtitle"))
        self.brand_subtitle.setObjectName("brandSub")
        self.brand_subtitle.setWordWrap(True)
        self.brand_subtitle.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        titles.addWidget(self.brand_subtitle)
        brand_row.addLayout(titles, 1)
        layout.addWidget(brand_box)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._nav_tr = dict(NAV_KEYS)
        self._buttons: dict[str, QPushButton] = {}
        for key, _tr_key in NAV_KEYS:
            button = QPushButton(f"  {tr(_tr_key)}")
            button.setProperty("nav", True)
            button.setIcon(nav_icon(key))
            button.setIconSize(QSize(18, 18))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.installEventFilter(self)  # own hover state (Qt's :hover can get stuck)
            button.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            layout.addWidget(button)
            self._group.addButton(button)
            self._buttons[key] = button

        layout.addStretch(1)

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
        self.u_title.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 700; color: {TEXT};")
        self.u_sub = QLabel(tr("sidebar_user_sub"))
        self.u_sub.setWordWrap(True)
        self.u_sub.setStyleSheet(f"font-size: {fs(11)}px; color: {TEXT_DIM};")
        user_text.addWidget(self.u_title)
        user_text.addWidget(self.u_sub)
        user_row.addLayout(user_text, 1)
        layout.addWidget(user_card)

        # Status pill
        self.status = QLabel(f"● {tr('status_healthy')}")
        self.status.setObjectName("sysStatus")
        self.status.setProperty("level", "ok")
        self.status.setStyleSheet(f"font-size: {fs(12)}px; font-weight: 600; color: {OK}; padding: 4px 18px;")
        layout.addWidget(self.status)

        self.select("dashboard")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Not enough height for the full menu + info card: hide the card, keep the menu intact.
        self.user_card.setVisible(self.height() >= 760)

    def retranslate(self) -> None:
        """Refresh static texts after a language change (nav + brand + user card)."""
        for key, tr_key in self._nav_tr.items():
            self._buttons[key].setText(f"  {tr(tr_key)}")
        self.brand_subtitle.setText(tr("app_subtitle"))
        self.u_title.setText(tr("sidebar_user_title"))
        self.u_sub.setText(tr("sidebar_user_sub"))

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(self._buttons)

    def set_health(self, text: str, level: str) -> None:
        self.status.setText(f"● {text}")
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
