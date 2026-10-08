from __future__ import annotations

BG = "#0f1115"
PANEL = "#161a21"
PANEL_ALT = "#1c2129"
BORDER = "#262c37"
TEXT = "#dfe4ec"
TEXT_DIM = "#8b93a3"
ACCENT = "#4f8cff"
ACCENT_HOVER = "#6ba0ff"
ACCENT_TINT = "#1e2c4a"
DANGER = "#e5534b"
OK = "#3fb950"

NAV_WIDTH = 232


def build_stylesheet() -> str:
    return f"""
* {{
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget#sidebar {{
    background: {PANEL};
    border-right: 1px solid {BORDER};
}}
QLabel#brand {{
    font-size: 16px;
    font-weight: 700;
    color: {TEXT};
    padding: 20px 18px 16px 18px;
    border-bottom: 1px solid {BORDER};
}}
QLabel#brandSub {{
    font-size: 11px;
    color: {TEXT_DIM};
    padding: 0 18px 14px 18px;
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: {TEXT_DIM};
    text-align: left;
    padding: 11px 16px;
    margin: 2px 10px;
}}
QPushButton[nav="true"]:hover {{
    background: {PANEL_ALT};
    color: {TEXT};
}}
QPushButton[nav="true"]:checked {{
    background: {ACCENT_TINT};
    border-left: 3px solid {ACCENT};
    color: {TEXT};
    font-weight: 600;
    padding-left: 13px;
}}
QWidget#sidebarFooter {{
    border-top: 1px solid {BORDER};
}}
QLabel#footerText {{
    color: {TEXT_DIM};
    font-size: 11px;
    padding: 12px 18px;
}}
QWidget#page {{
    background: {BG};
}}
QLabel#pageTitle {{
    font-size: 22px;
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
    border-radius: 12px;
}}
QLabel#cardTitle {{
    font-size: 12px;
    font-weight: 600;
    color: {TEXT_DIM};
    letter-spacing: 1px;
}}
QLabel#cardValue {{
    font-size: 27px;
    font-weight: 700;
    color: {TEXT};
}}
QLabel#scoreValue {{
    font-size: 58px;
    font-weight: 800;
    color: {ACCENT};
}}
QLabel#cardSub {{
    font-size: 11px;
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
    color: {TEXT_DIM};
    border-top: 1px solid {BORDER};
}}
QStatusBar::item {{
    border: none;
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
    background: {BG};
    color: {TEXT_DIM};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px;
    font-size: 11px;
    font-weight: 600;
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
    background: #3a1d1c;
    color: {DANGER};
    border: 1px solid #6e2b27;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}}
QPushButton[danger="true"]:hover {{
    background: #4a2422;
}}
QPushButton[danger="true"]:disabled {{
    background: {PANEL_ALT};
    color: {TEXT_DIM};
    border: 1px solid {BORDER};
}}
QSplitter::handle {{
    background: {BORDER};
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

    app.setStyle("Fusion")
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
