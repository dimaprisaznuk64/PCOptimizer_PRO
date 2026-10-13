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
    "MATRIX": {
        **_BASE,
        "BG": "#050A06", "PANEL": "#08130B", "PANEL_ALT": "#0E1F12", "BORDER": "#17361F", "BORDER_HI": "#245C33",
        "TEXT": "#E6FFEE", "TEXT_DIM": "#7FB894", "ACCENT": "#22FF88", "ACCENT_HOVER": "#5CFFAA",
        "ACCENT_TINT": "#0A3320", "ACCENT_PRESSED": "#00CC66", "ON_ACCENT": "#04140A",
        "DANGER": "#FF4D4D", "OK": "#33FF88", "WARN": "#FFC53D",
        "SIDEBAR_TOP": "#07140B", "SIDEBAR_BOTTOM": "#040A06", "HOVER": "#10281A",
        "DANGER_BG": "#251012", "DANGER_BORDER": "#5C2226", "DANGER_BG_HOVER": "#33171A",
        "OK_BG": "#0A2616", "WARN_BG": "#2A2410", "HERO_TOP": "#0A2A18",
        "BRAND_A": "#22FF88", "BRAND_B": "#00E0B0", "GLOW_A": "#00FF7F", "GLOW_B": "#22FF88",
        "GLOW_ALPHA_A": 40, "GLOW_ALPHA_B": 28,
        "C1": "#33FF88", "C2": "#00E0B0", "C3": "#A0FF3C", "C4": "#FFD24A",
    },
    "CYBERPUNK": {
        **_BASE,
        "BG": "#0A0410", "PANEL": "#140A1F", "PANEL_ALT": "#1E1030", "BORDER": "#33184F", "BORDER_HI": "#5A2A88",
        "TEXT": "#FCE9FF", "TEXT_DIM": "#B78FD6", "ACCENT": "#FF2FB4", "ACCENT_HOVER": "#FF6CC8",
        "ACCENT_TINT": "#3A1040", "ACCENT_PRESSED": "#D40094", "ON_ACCENT": "#FFFFFF",
        "DANGER": "#FF4D6D", "OK": "#00E5D4", "WARN": "#FFB020",
        "SIDEBAR_TOP": "#160725", "SIDEBAR_BOTTOM": "#0A0410", "HOVER": "#241236",
        "DANGER_BG": "#2E0F1E", "DANGER_BORDER": "#5C1E38", "DANGER_BG_HOVER": "#3D1428",
        "OK_BG": "#06322E", "WARN_BG": "#33260A", "HERO_TOP": "#2A0B3A",
        "BRAND_A": "#FF2FB4", "BRAND_B": "#00E5D4", "GLOW_A": "#FF2FB4", "GLOW_B": "#00E5D4",
        "GLOW_ALPHA_A": 50, "GLOW_ALPHA_B": 32,
        "C1": "#FF2FB4", "C2": "#00E5D4", "C3": "#8A5CFF", "C4": "#FFD24A",
    },
    "NORD": {
        **_BASE,
        "BG": "#2E3440", "PANEL": "#3B4252", "PANEL_ALT": "#434C5E", "BORDER": "#4C566A", "BORDER_HI": "#5E6B82",
        "TEXT": "#ECEFF4", "TEXT_DIM": "#AEB8C6", "ACCENT": "#88C0D0", "ACCENT_HOVER": "#9ED2E0",
        "ACCENT_TINT": "#3A4C57", "ACCENT_PRESSED": "#6FA9BA", "ON_ACCENT": "#2E3440",
        "DANGER": "#BF616A", "OK": "#A3BE8C", "WARN": "#EBCB8B",
        "SIDEBAR_TOP": "#333A47", "SIDEBAR_BOTTOM": "#2B313C", "HOVER": "#434C5E",
        "DANGER_BG": "#3D2E30", "DANGER_BORDER": "#6A464A", "DANGER_BG_HOVER": "#4A3639",
        "OK_BG": "#2F3A2E", "WARN_BG": "#3D3A2C", "HERO_TOP": "#3A4353",
        "BRAND_A": "#88C0D0", "BRAND_B": "#81A1C1", "GLOW_A": "#88C0D0", "GLOW_B": "#B48EAD",
        "GLOW_ALPHA_A": 38, "GLOW_ALPHA_B": 26,
        "C1": "#88C0D0", "C2": "#81A1C1", "C3": "#B48EAD", "C4": "#EBCB8B",
    },
}

THEME_LABELS: dict[str, str] = {
    "DARK": "Black Cyber",
    "PURPLE": "Purple Neon",
    "GREEN": "Green Nature",
    "LIGHT": "Light",
    "AMOLED": "AMOLED",
    "MATRIX": "Matrix",
    "CYBERPUNK": "Cyberpunk",
    "NORD": "Nord",
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

FONT_UI = '"Segoe UI Variable Text", "Segoe UI", "Inter", system-ui, sans-serif'
FONT_DISPLAY = '"Segoe UI Variable Display", "Segoe UI Semibold", "Segoe UI", system-ui, sans-serif'
FONT_MONO = '"Cascadia Mono", "Consolas", "Segoe UI", monospace'


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
    font-family: {FONT_UI};
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
    font-family: {FONT_DISPLAY};
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
    border-radius: 16px;
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
QLabel#cardValue, QLabel#gaugeValue, QLabel#heroValue, QLabel#ringValue,
QLabel#scoreValue, QLabel#statValue, QLabel#clock {{
    font-family: {FONT_MONO};
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
    padding: 8px 10px;
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
    padding: 11px 10px;
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
