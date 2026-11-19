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
    LOGO_SIZE,
    NAV_ICON_SIZE,
    OK,
    PADDING_LG,
    PADDING_SM,
    PANEL,
    RADIUS_LG,
    RADIUS_MD,
    SIDEBAR_COMPACT_WIDTH,
    SIDEBAR_WIDTH,
    SPACING_MD,
    T_BRAND,
    T_CAPTION,
    T_MICRO,
    T_SMALL,
    TEXT,
    TEXT_DIM,
    ls,
)

NAV_KEYS: tuple[tuple[str, str], ...] = (
    ("dashboard", "nav_dashboard"),
    ("monitor", "nav_monitor"),
    ("temperature", "nav_temperature"),
    ("gpu", "nav_gpu"),
    ("hardware", "nav_hardware"),
    ("processes", "nav_processes"),
    ("cleaner", "nav_cleaner"),
    ("startup", "nav_startup"),
    ("gaming", "nav_gaming"),
    ("launcher", "nav_launcher"),
    ("benchmarks", "nav_benchmarks"),
    ("hardware_benchmark", "nav_hardware_benchmark"),
    ("history", "nav_history"),
    ("network", "nav_network"),
    ("optimizer", "nav_optimizer"),
    ("disk", "nav_disk"),
    ("diagnostics", "nav_diagnostics"),
    ("drivers", "nav_drivers"),
    ("system_report", "nav_system_report"),
    ("export_center", "nav_export_center"),
    ("health", "nav_health"),
    ("settings", "nav_settings"),
)

NAV_ITEMS: tuple[tuple[str, str], ...] = tuple((k, tr(kk)) for k, kk in NAV_KEYS)

# One source of truth for the grouped rail. Every navigation key appears exactly
# once; NAV_KEYS stays unchanged so TopBar page numbers and tests keep working.
NAV_GROUPS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("overview", "nav_group_overview", ("dashboard", "health")),
    ("monitoring", "nav_group_monitoring", ("monitor", "temperature", "gpu", "history")),
    ("hardware", "nav_group_hardware", ("hardware", "processes", "drivers")),
    ("optimization", "nav_group_optimization", ("cleaner", "startup", "optimizer", "disk")),
    ("gaming", "nav_group_gaming", ("gaming", "launcher", "benchmarks", "hardware_benchmark")),
    ("tools", "nav_group_tools", ("network", "diagnostics", "system_report", "export_center")),
    ("settings", "nav_group_settings", ("settings",)),
)

_GROUP_OF_KEY: dict[str, str] = {
    key: group for group, _tr_key, keys in NAV_GROUPS for key in keys
}


class _LogoMark(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(LOGO_SIZE, LOGO_SIZE)

    def paintEvent(self, event) -> None:
        from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        grad = QLinearGradient(0, 0, LOGO_SIZE, LOGO_SIZE)
        grad.setColorAt(0.0, QColor(BRAND_A))
        grad.setColorAt(1.0, QColor(BRAND_B))
        p.setBrush(grad)
        p.setPen(Qt.PenStyle.NoPen)
        path = QPainterPath()
        inset = ls(2)
        path.addRoundedRect(
            inset, inset, LOGO_SIZE - inset * 2, LOGO_SIZE - inset * 2, RADIUS_MD, RADIUS_MD
        )
        p.drawPath(path)
        p.setPen(QColor("#FFFFFF"))
        font = p.font()
        font.setBold(True)
        font.setPointSize(max(8, T_CAPTION - 1))
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
            button.setToolTip(tr(f"tip_nav_{key}"))
            button.setProperty("nav", True)
            button.setIcon(nav_icon(key))
            button.setIconSize(QSize(NAV_ICON_SIZE, NAV_ICON_SIZE))
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.installEventFilter(self)  # own hover state (Qt's :hover can get stuck)
            button.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            self._group.addButton(button)
            self._buttons[key] = button

        self._group_buttons: dict[str, QPushButton] = {}
        self._group_tr = {group: tr_key for group, tr_key, _ in NAV_GROUPS}
        self._group_keys = {group: keys for group, _, keys in NAV_GROUPS}
        self._collapsed: set[str] = set()
        for group, _tr_key, keys in NAV_GROUPS:
            header = QPushButton()
            header.setObjectName("navGroup")
            header.setProperty("navGroup", True)
            header.setCheckable(True)
            header.setChecked(True)
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.clicked.connect(lambda _=False, g=group: self.toggle_group(g))
            nav_layout.addWidget(header)
            self._group_buttons[group] = header
            for key in keys:
                nav_layout.addWidget(self._buttons[key])

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
            f"border-radius: {RADIUS_LG}px; margin: 0px {ls(12)}px {ls(10)}px {ls(12)}px; "
            f"padding: {ls(6)}px; }} "
            "QFrame#card QLabel { background: transparent; border: none; padding: 0; margin: 0; }"
        )
        user_row = QHBoxLayout(user_card)
        user_row.setContentsMargins(PADDING_SM, PADDING_SM, PADDING_SM, PADDING_SM)
        user_row.setSpacing(SPACING_MD)
        from .icons import glyph
        shield_icon = QLabel()
        shield_icon.setPixmap(glyph("shield", C1).scaled(ls(20), ls(20), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        shield_icon.setFixedSize(ls(22), ls(22))
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
        self.status.setStyleSheet(f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: {ls(4)}px {PADDING_LG}px;")
        bottom_layout.addWidget(self.status)
        self._bottom = bottom
        layout.addWidget(bottom)

        for group in self._group_buttons:
            self._apply_group(group)
        self.select("dashboard")

    def _nav_tooltip(self, key: str) -> str:
        label = tr(self._nav_tr[key])
        description = tr(f"tip_nav_{key}")
        return f"{label}\n{description}" if self._compact else description

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
            button.setToolTip(self._nav_tooltip(key))
            button.setProperty("compact", compact)
            button.style().unpolish(button)
            button.style().polish(button)
        for group in self._group_buttons:
            self._apply_group(group)

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
                f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: {ls(4)}px 0px;"
            )
        else:
            self.status.setText(f"● {self._status_text}")
            self.status.setToolTip("")
            self.status.setStyleSheet(
                f"font-size: {T_SMALL}px; font-weight: 600; color: {OK}; padding: {ls(4)}px {PADDING_LG}px;"
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
            button.setToolTip(self._nav_tooltip(key))
            button.setAccessibleName(label)
        for group in self._group_buttons:
            self._apply_group(group)
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

    def _apply_group(self, group: str) -> None:
        """Sync a group header (label, arrow, tooltip) and its children's visibility."""
        header = self._group_buttons[group]
        label = tr(self._group_tr[group])
        collapsed = group in self._collapsed
        count = len(self._group_keys[group])
        summary = tr("nav_group_count", group=label, count=count)
        header.setChecked(not collapsed)
        header.setText(
            "─" if self._compact else f"{'▸' if collapsed else '▾'}  {label.upper()} · {count}"
        )
        header.setAccessibleName(label)
        action = tr("nav_group_expand" if collapsed else "nav_group_collapse", group=label)
        header.setToolTip(f"{label if self._compact else action}\n{summary}")
        header.setProperty("collapsed", collapsed)
        header.setProperty("compact", self._compact)
        header.style().unpolish(header)
        header.style().polish(header)
        for key in self._group_keys[group]:
            self._buttons[key].setVisible(not collapsed)

    def toggle_group(self, group: str) -> None:
        """Collapse or expand one group without changing the selected page."""
        if group in self._collapsed:
            self._collapsed.discard(group)
        else:
            self._collapsed.add(group)
        self._apply_group(group)

    def _expand_group_for(self, key: str) -> None:
        group = _GROUP_OF_KEY.get(key)
        if group is not None and group in self._collapsed:
            self._collapsed.discard(group)
            self._apply_group(group)

    def collapsed_groups(self) -> tuple[str, ...]:
        return tuple(group for group in self._group_buttons if group in self._collapsed)

    def set_collapsed_groups(self, groups) -> None:
        self._collapsed = set(groups) & set(self._group_buttons)
        for group in self._group_buttons:
            self._apply_group(group)

    def set_current(self, key: str) -> None:
        self._set_hot(None)
        button = self._buttons.get(key)
        if button is not None:
            self._expand_group_for(key)
            button.setChecked(True)

    def select(self, key: str) -> None:
        button = self._buttons.get(key)
        if button is None:
            return
        self._expand_group_for(key)
        button.setChecked(True)
        self.navigated.emit(key)
