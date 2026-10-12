from __future__ import annotations

_BASE = {
    "BG": "#070A13",
    "PANEL": "#0B1120",
    "PANEL_ALT": "#10182B",
    "BORDER": "#16233B",
    "BORDER_HI": "#24375A",
    "TEXT": "#F1F5F9",
    "TEXT_DIM": "#8292AA",
    "ACCENT": "#1E6BFF",
    "ACCENT_HOVER": "#3B82F6",
    "ACCENT_TINT": "#0D2247",
    "ACCENT_PRESSED": "#0052CC",
    "ON_ACCENT": "#FFFFFF",
    "DANGER": "#EF4444",
    "OK": "#00E599",
    "WARN": "#F59E0B",
    "SIDEBAR_TOP": "#080D1A",
    "SIDEBAR_BOTTOM": "#050812",
    "HOVER": "#131E33",
    "DANGER_BG": "#2E151B",
    "DANGER_BORDER": "#5C222D",
    "DANGER_BG_HOVER": "#3D1A23",
    "OK_BG": "#0B261C",
    "WARN_BG": "#2B2110",
    "HERO_TOP": "#0E1C38",
    "BRAND_A": "#1E6BFF",
    "BRAND_B": "#00D2FF",
    "GLOW_A": "#0066FF",
    "GLOW_B": "#9B51E0",
    "GLOW_ALPHA_A": 45,
    "GLOW_ALPHA_B": 30,
    "C1": "#00D2FF",
    "C2": "#2F80ED",
    "C3": "#A855F7",
    "C4": "#0080FF",
}

PALETTES: dict[str, dict] = {
    "DARK": dict(_BASE),
    "PURPLE": {
        **_BASE,
        "BG": "#0c0817", "PANEL": "#151026", "PANEL_ALT": "#1d1736", "BORDER": "#2b2350", "BORDER_HI": "#43377a",
        "TEXT": "#eee8ff", "TEXT_DIM": "#9d93c8", "ACCENT": "#a259ff", "ACCENT_HOVER": "#b97dff",
        "ACCENT_TINT": "#2c1d52", "ACCENT_PRESSED": "#8640dc", "SIDEBAR_TOP": "#1a1230", "SIDEBAR_BOTTOM": "#110b22",
        "HOVER": "#241c42", "HERO_TOP": "#2b1b52", "BRAND_A": "#c27dff", "BRAND_B": "#ff4fd8",
        "GLOW_A": "#a259ff", "GLOW_B": "#ff4fd8", "C1": "#a259ff", "C2": "#ff4fd8", "C3": "#5ac8fa", "C4": "#ffb03a",
    },
    "GREEN": {
        **_BASE,
        "BG": "#08100d", "PANEL": "#0f1a15", "PANEL_ALT": "#15241d", "BORDER": "#1d3a2e", "BORDER_HI": "#2d5a47",
        "TEXT": "#e3f4ec", "TEXT_DIM": "#86aa99", "ACCENT": "#2ed39a", "ACCENT_HOVER": "#55e4b2",
        "ACCENT_TINT": "#123b2d", "ACCENT_PRESSED": "#1faa7c", "ON_ACCENT": "#04130d",
        "SIDEBAR_TOP": "#10201a", "SIDEBAR_BOTTOM": "#0b1511", "HOVER": "#1a2d24", "HERO_TOP": "#11392b",
        "BRAND_A": "#55e4b2", "BRAND_B": "#2f9bff", "GLOW_A": "#2ed39a", "GLOW_B": "#3fb950",
        "C1": "#2ed39a", "C2": "#5ac8fa", "C3": "#b6e04a", "C4": "#f0a03a",
    },
    "LIGHT": {
        **_BASE,
        "BG": "#eef2f8", "PANEL": "#ffffff", "PANEL_ALT": "#f4f7fb", "BORDER": "#dde4ef", "BORDER_HI": "#c3cee0",
        "TEXT": "#1b2433", "TEXT_DIM": "#66748b", "ACCENT": "#3b82f6", "ACCENT_HOVER": "#5a9bff",
        "ACCENT_TINT": "#e1ecff", "ACCENT_PRESSED": "#2a6fe0", "DANGER": "#d9423a", "OK": "#1fa65a", "WARN": "#e08a00",
        "SIDEBAR_TOP": "#ffffff", "SIDEBAR_BOTTOM": "#f6f8fc", "HOVER": "#edf2fa",
        "DANGER_BG": "#fde8e7", "DANGER_BORDER": "#f1b4b0", "DANGER_BG_HOVER": "#fbd6d4", "WARN_BG": "#fff3d6",
        "OK_BG": "#dcf4e5",
        "HERO_TOP": "#dce9ff", "BRAND_A": "#5a9bff", "BRAND_B": "#8b5cf6", "GLOW_A": "#3b82f6", "GLOW_B": "#8b5cf6",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 28, "C1": "#3b82f6", "C2": "#8b5cf6", "C3": "#14b8a6", "C4": "#f59e0b",
    },
    "AMOLED": {
        **_BASE,
        "BG": "#000000", "PANEL": "#08090b", "PANEL_ALT": "#101216", "BORDER": "#1a1d24", "BORDER_HI": "#2a2f3a",
        "TEXT": "#f1f3f7", "TEXT_DIM": "#858c9a", "ACCENT": "#2f80ff", "ACCENT_HOVER": "#5a9bff",
        "ACCENT_TINT": "#0f2347", "ACCENT_PRESSED": "#1f66d6", "SIDEBAR_TOP": "#050608", "SIDEBAR_BOTTOM": "#000000",
        "HOVER": "#14171d", "DANGER_BG": "#2a0f0e", "DANGER_BORDER": "#5c2420", "DANGER_BG_HOVER": "#3a1412",
        "OK_BG": "#0e2616", "HERO_TOP": "#0d1d3d", "BRAND_A": "#5a9bff", "BRAND_B": "#7a5cff",
        "GLOW_ALPHA_A": 55, "GLOW_ALPHA_B": 35, "C1": "#2f80ff", "C2": "#9b6dff", "C3": "#19d3e0", "C4": "#ffb03a",
    },
}

THEME_LABELS: dict[str, str] = {
    "DARK": "Black Cyber",
    "PURPLE": "Purple Neon",
    "GREEN": "Green Nature",
    "LIGHT": "Light",
    "AMOLED": "AMOLED",
}

BG: str
PANEL: str
PANEL_ALT: str
BORDER: str
BORDER_HI: str
TEXT: str
TEXT_DIM: str
ACCENT: str
ACCENT_HOVER: str
ACCENT_TINT: str
ACCENT_PRESSED: str
ON_ACCENT: str
DANGER: str
OK: str
WARN: str
SIDEBAR_TOP: str
SIDEBAR_BOTTOM: str
HOVER: str
DANGER_BG: str
DANGER_BORDER: str
DANGER_BG_HOVER: str
OK_BG: str
WARN_BG: str
HERO_TOP: str
BRAND_A: str
BRAND_B: str
GLOW_A: str
GLOW_B: str
GLOW_ALPHA_A: int
GLOW_ALPHA_B: int
C1: str
C2: str
C3: str
C4: str


def saved_theme() -> str:
    try:
        from app.settings import SettingsService

        name = str(SettingsService().get("theme")).upper()
    except Exception:
        name = "DARK"
    return name if name in PALETTES else "DARK"


CURRENT_THEME = saved_theme()
globals().update(PALETTES[CURRENT_THEME])

NAV_WIDTH = 232


def _chevron_path(color: str) -> str:
    """Render a small down-chevron PNG (for combo boxes) and return its path for QSS url()."""
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPolygonF

    path = Path(tempfile.gettempdir()) / f"pcopt_chevron_{color.lstrip('#')}.png"
    img = QImage(24, 24, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 2.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.drawPolyline(QPolygonF([QPointF(6, 9), QPointF(12, 15), QPointF(18, 9)]))
    p.end()
    img.save(str(path))
    return path.as_posix()


def build_stylesheet() -> str:
    CHEVRON = _chevron_path(TEXT_DIM)
    return f"""
* {{
    font-family: "Segoe UI Variable Text", "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {SIDEBAR_TOP}, stop:1 {SIDEBAR_BOTTOM});
    border-right: 1px solid {BORDER};
}}
QLabel#brand {{
    font-size: 15px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#brandSub {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: 9px;
    color: {TEXT_DIM};
    text-align: left;
    padding: 10px 14px 10px 14px;
    margin: 2px 10px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton[nav="true"]:hover {{
    background: {PANEL_ALT};
    color: #FFFFFF;
}}
QPushButton[nav="true"]:focus {{
    border: none;
    outline: none;
}}
QPushButton[nav="true"]:checked, QPushButton[nav="true"]:checked:focus, QPushButton[nav="true"]:checked:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    border: none;
    border-radius: 9px;
    color: #FFFFFF;
    font-weight: 700;
    padding-left: 14px;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 6px;
    margin: 0px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    min-height: 24px;
    border-radius: 3px;
}}
QScrollBar::handle:vertical:hover {{
    background: {BORDER_HI};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}
QWidget#sidebarFooter {{
    border-top: 1px solid {BORDER};
}}
QLabel#footerText {{
    color: {TEXT_DIM};
    font-size: 12px;
    padding: 12px 18px;
}}
QWidget#page {{
    background: {BG};
}}
QLabel#pageTitle, QLabel#welcome, QLabel#heroValue, QLabel#scoreValue {{
    font-family: "Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", sans-serif;
    letter-spacing: -0.3px;
}}
QLabel#pageTitle {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageDesc {{
    font-size: 13px;
    color: {TEXT_DIM};
}}
QFrame#card {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 14px;
}}
QLabel#cardTitle {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_DIM};
    letter-spacing: 1px;
}}
QLabel#cardValue {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#gaugeValue {{
    font-size: 28px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#gaugeTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#iconTile {{
    background: {ACCENT_TINT};
    border-radius: 10px;
}}
QLabel#heroValue {{
    font-size: 40px;
    font-weight: 800;
    color: {TEXT};
}}
QLabel#welcome {{
    font-size: 30px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#tileTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#tileArrow {{
    font-size: 22px;
    color: {TEXT_DIM};
}}
QPushButton#linkButton {{
    background: transparent;
    border: none;
    padding: 4px 0;
    color: {ACCENT};
    font-weight: 600;
    text-align: left;
}}
QPushButton#linkButton:hover {{
    color: {ACCENT_HOVER};
    background: transparent;
}}
QPushButton[tile="true"] {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 12px;
    text-align: left;
    padding: 0;
}}
QPushButton[tile="true"]:hover {{
    background: {PANEL_ALT};
    border-color: {ACCENT};
}}
QFrame#hero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {HERO_TOP}, stop:1 {PANEL});
    border: 1px solid {BORDER_HI};
    border-radius: 14px;
}}
QLabel#ringValue {{
    font-size: 26px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#ringSub {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT};
}}
QLabel#clock {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#sysStatus {{
    font-size: 11px;
    font-weight: 600;
    color: {OK};
    padding: 12px 18px 2px 18px;
}}
QLabel#sysStatus[level="warn"] {{
    color: {WARN};
}}
QLabel#sysStatus[level="danger"] {{
    color: {DANGER};
}}
QPushButton[seg="true"] {{
    background: transparent;
    border: none;
    border-radius: 6px;
    padding: 4px 12px;
    color: {TEXT_DIM};
    font-size: 12px;
}}
QPushButton[seg="true"]:hover {{
    color: {TEXT};
    background: {PANEL_ALT};
}}
QPushButton[seg="true"]:checked {{
    background: {ACCENT_TINT};
    color: {ACCENT};
    font-weight: 600;
}}
QPushButton[quick="true"] {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 9px;
    text-align: left;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton[quick="true"]:hover {{
    border-color: {ACCENT};
    background: {ACCENT_TINT};
}}
QLabel#scoreValue {{
    font-size: 44px;
    font-weight: 800;
    color: {TEXT};
    background: transparent;
}}
QLabel#statValue {{
    font-size: 20px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#livePill {{
    background: {OK_BG};
    color: {OK};
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#cardSub {{
    font-size: 12px;
    color: {TEXT_DIM};
}}
QLabel#cardRow {{
    font-size: 12px;
    color: {TEXT};
}}
QLabel#errorLine {{
    font-size: 12px;
    color: {DANGER};
}}
QLabel#gpuName {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#pageBadge {{
    background: {ACCENT_TINT};
    color: {ACCENT};
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 600;
}}
QStatusBar {{
    background: {PANEL};
    padding-left: 8px;
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{
    border: none;
}}
QWidget#topBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QLabel#topBarTitle {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#topBarStatus {{
    font-size: 12px;
    font-weight: 600;
    color: {OK};
    padding: 4px 12px;
    border-radius: 14px;
    background: {OK_BG};
}}
QLabel#topBarStatus[level="warn"] {{
    background: {WARN_BG};
    color: {WARN};
}}
QLabel#topBarStatus[level="danger"] {{
    background: {DANGER_BG};
    color: {DANGER};
}}
QPushButton#topBarIcon {{
    background: transparent;
    border: none;
    border-radius: 8px;
    padding: 6px;
}}
QPushButton#topBarIcon:hover {{
    background: {PANEL_ALT};
}}
QPushButton#topBarIcon::menu-indicator {{
    image: none;
}}
QFrame#card:hover {{
    border-color: {BORDER_HI};
}}
QTableWidget::item {{
    padding: 6px 8px;
}}
QTableWidget::item:hover {{
    background: {HOVER};
}}
QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 10px;
    gridline-color: transparent;
    alternate-background-color: {PANEL_ALT};
    selection-background-color: {ACCENT_TINT};
    selection-color: {TEXT};
    padding: 4px;
}}
QHeaderView::section {{
    background: {PANEL};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 10px 8px;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
}}
QLineEdit {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
}}
QLineEdit:focus {{
    border-color: {ACCENT};
}}
QPushButton[secondary="true"] {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    color: {TEXT};
}}
QPushButton[secondary="true"]:hover {{
    border-color: {ACCENT};
}}
QPushButton[danger="true"] {{
    background: {DANGER_BG};
    color: {DANGER};
    border: 1px solid {DANGER_BORDER};
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton[danger="true"]:hover {{
    background: {DANGER_BG_HOVER};
}}
QPushButton[danger="true"]:disabled {{
    background: {PANEL_ALT};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}
QPushButton {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 8px 14px;
}}
QPushButton:hover {{
    border-color: {ACCENT};
    background: {HOVER};
}}
QPushButton:pressed {{
    background: {ACCENT_TINT};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    background: {PANEL};
    border-color: {BORDER};
}}
QPushButton:focus {{
    outline: none;
    border-color: {ACCENT};
}}
QPushButton[primary="true"] {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: {ON_ACCENT};
    font-weight: 600;
}}
QPushButton[primary="true"]:hover {{
    background: {ACCENT_HOVER};
    border-color: {ACCENT_HOVER};
}}
QPushButton[primary="true"]:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton[primary="true"]:disabled {{
    background: {ACCENT_TINT};
    border-color: {ACCENT_TINT};
    color: {TEXT_DIM};
}}
QToolTip {{
    background: {PANEL_ALT};
    color: {TEXT};
    border: 1px solid {BORDER_HI};
    padding: 5px 8px;
}}
QCheckBox {{
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 1px solid {BORDER_HI};
    background: {PANEL_ALT};
}}
QCheckBox::indicator:hover {{
    border-color: {ACCENT};
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
}}
QComboBox, QSpinBox {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
}}
QComboBox {{
    padding-right: 28px;
}}
QComboBox::drop-down {{
    border: none;
    width: 26px;
    subcontrol-origin: padding;
    subcontrol-position: center right;
}}
QComboBox::down-arrow {{
    image: url({CHEVRON});
    width: 12px;
    height: 12px;
}}
QComboBox:hover, QSpinBox:hover, QComboBox:focus, QSpinBox:focus {{
    border-color: {ACCENT};
}}
QComboBox QAbstractItemView {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER_HI};
    selection-background-color: {ACCENT_TINT};
    outline: none;
}}
QMenu {{
    background: {PANEL_ALT};
    border: 1px solid {BORDER_HI};
    border-radius: 8px;
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 5px;
}}
QMenu::item:selected {{
    background: {ACCENT_TINT};
}}
QLabel#navSection {{
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1.5px;
    color: {TEXT_DIM};
    padding: 16px 26px 4px 26px;
}}
QLabel#brandMark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 {BRAND_A}, stop:1 {BRAND_B});
    color: #ffffff;
    border-radius: 8px;
    font-weight: 800;
    font-size: 13px;
}}
QWidget#brandBox {{
    border-bottom: 1px solid {BORDER};
}}
QSplitter::handle {{
    background: transparent;
}}
QSplitter::handle:horizontal {{
    width: 10px;
}}
QSplitter::handle:vertical {{
    height: 10px;
}}
QMessageBox {{
    background: {PANEL};
}}
QScrollBar:vertical {{
    background: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG};
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER};
    border-radius: 5px;
    min-width: 30px;
}}
"""


def apply(app) -> None:
    from PySide6.QtGui import QColor, QPalette

    from PySide6.QtGui import QFont

    app.setStyle("Fusion")
    base = QFont()
    base.setFamilies(["Segoe UI Variable Text", "Segoe UI", "Inter"])
    base.setPixelSize(13)
    base.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
    base.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    app.setFont(base)
    app.setStyleSheet(build_stylesheet())
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(BG))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Base, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Button, QColor(PANEL))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(PANEL_ALT))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(TEXT))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_DIM))
    app.setPalette(palette)
