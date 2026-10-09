from __future__ import annotations

# PCOptimizer PRO visual system — graphite surfaces with electric cyan/blue accents.
BG = "#0a0e14"
PANEL = "#101722"
PANEL_ALT = "#151f2d"
BORDER = "#243247"
TEXT = "#edf4ff"
TEXT_DIM = "#8798ae"
ACCENT = "#54a8ff"
ACCENT_HOVER = "#69e0dc"
ACCENT_TINT = "#142e49"
DANGER = "#ff647c"
OK = "#45d6a0"

NAV_WIDTH = 248


def build_stylesheet() -> str:
    return f"""
* {{
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
    color: {TEXT};
    outline: none;
}}
QMainWindow, QWidget#root {{
    background: {BG};
}}
QWidget#sidebar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #111a27, stop:1 #0d131d);
    border-right: 1px solid #202d40;
}}
QWidget#brandBlock {{
    background: transparent;
}}
QLabel#brandMark {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #67c8ff, stop:1 #5a7cff);
    color: #07111e;
    border-radius: 11px;
    font-size: 20px;
    font-weight: 900;
    min-width: 42px;
    max-width: 42px;
    min-height: 42px;
    max-height: 42px;
    qproperty-alignment: AlignCenter;
}}
QLabel#brand {{
    font-size: 16px;
    font-weight: 800;
    color: #f4f8ff;
    padding: 0;
    border: none;
}}
QLabel#brandAccent {{
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
    color: {ACCENT};
    padding: 0;
}}
QLabel#brandSub {{
    font-size: 11px;
    color: {TEXT_DIM};
    padding: 0 0 14px 0;
}}
QLabel#navSection {{
    color: #60738d;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.8px;
    padding: 16px 16px 7px 17px;
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 9px;
    color: #9cacc1;
    text-align: left;
    padding: 10px 13px;
    margin: 2px 10px;
    font-size: 13px;
    font-weight: 550;
}}
QPushButton[nav="true"]:hover {{
    background: #172333;
    border-color: #263b54;
    color: #f4f8ff;
}}
QPushButton[nav="true"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #183958, stop:1 #142a42);
    border: 1px solid #2d5a80;
    color: #f5fbff;
    font-weight: 700;
}}
QWidget#sidebarFooter {{
    border-top: 1px solid #202d40;
    background: transparent;
}}
QLabel#footerText {{
    color: #71849d;
    font-size: 11px;
    padding: 12px 16px;
}}
QLabel#footerStatus {{
    color: {OK};
    font-size: 10px;
    font-weight: 700;
    padding: 0 16px 12px 16px;
}}
QWidget#page {{
    background: {BG};
}}
QLabel#pageTitle {{
    font-size: 27px;
    font-weight: 800;
    color: #f3f7ff;
    padding: 0;
}}
QLabel#pageDesc {{
    font-size: 13px;
    color: #91a2b8;
}}
QLabel#pageEyebrow {{
    color: {ACCENT};
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2px;
}}
QFrame#card {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #131d2a, stop:1 #0f1722);
    border: 1px solid #26364b;
    border-radius: 15px;
}}
QFrame#card:hover {{
    border-color: #365574;
}}
QLabel#cardTitle {{
    font-size: 11px;
    font-weight: 800;
    color: #8fa3bc;
    letter-spacing: 1.4px;
}}
QLabel#cardValue {{
    font-size: 30px;
    font-weight: 800;
    color: #f2f7ff;
}}
QLabel#scoreValue {{
    font-size: 60px;
    font-weight: 900;
    color: {ACCENT};
}}
QLabel#cardSub {{
    font-size: 11px;
    color: #879ab2;
}}
QLabel#cardRow {{
    font-size: 12px;
    color: #dce7f7;
}}
QLabel#errorLine {{
    font-size: 12px;
    color: {DANGER};
    background: #281923;
    border: 1px solid #623044;
    border-radius: 8px;
    padding: 8px 12px;
}}
QLabel#gpuName {{
    font-size: 16px;
    font-weight: 800;
    color: {TEXT};
}}
QLabel#pageBadge {{
    background: #173653;
    color: #8dd0ff;
    border: 1px solid #28577b;
    border-radius: 7px;
    padding: 5px 10px;
    font-size: 10px;
    font-weight: 800;
}}
QStatusBar {{
    background: #0e1520;
    color: #8194ab;
    border-top: 1px solid #202d40;
    min-height: 25px;
}}
QStatusBar::item {{ border: none; }}
QTableWidget, QTreeWidget, QListWidget {{
    background: #101823;
    border: 1px solid #26364b;
    border-radius: 11px;
    gridline-color: transparent;
    alternate-background-color: #141f2d;
    selection-background-color: #1a3d5b;
    selection-color: #f2f8ff;
    padding: 5px;
}}
QTableWidget::item, QTreeWidget::item, QListWidget::item {{
    padding: 7px 5px;
    border-bottom: 1px solid #1d2a3a;
}}
QHeaderView::section {{
    background: #151f2d;
    color: #91a5bd;
    border: none;
    border-bottom: 1px solid #2a3c52;
    padding: 10px 8px;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.8px;
}}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background: #111c29;
    border: 1px solid #2b3c52;
    border-radius: 9px;
    padding: 9px 11px;
    selection-background-color: {ACCENT};
    selection-color: #ffffff;
    min-height: 18px;
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QPlainTextEdit:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
    background: #142235;
}}
QComboBox::drop-down {{
    border: none;
    width: 25px;
}}
QComboBox QAbstractItemView {{
    background: #111c29;
    border: 1px solid #2b3c52;
    selection-background-color: #1a3d5b;
}}
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #2679c8, stop:1 #1b5da0);
    border: 1px solid #3989d4;
    border-radius: 9px;
    padding: 9px 15px;
    color: #ffffff;
    font-weight: 700;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #3691e5, stop:1 #2474bc);
    border-color: #65b5ff;
}}
QPushButton:pressed {{ background: #174d7e; }}
QPushButton:disabled {{
    background: #1a2533;
    color: #63748a;
    border: 1px solid #26364b;
}}
QPushButton[secondary="true"] {{
    background: #172333;
    border: 1px solid #2b4059;
    border-radius: 9px;
    padding: 9px 14px;
    color: #dce8f8;
}}
QPushButton[secondary="true"]:hover {{
    background: #20344a;
    border-color: #4c769d;
}}
QPushButton[danger="true"] {{
    background: #351d2a;
    color: #ff8b9d;
    border: 1px solid #73364a;
    border-radius: 9px;
    padding: 9px 14px;
    font-weight: 700;
}}
QPushButton[danger="true"]:hover {{ background: #492333; border-color: #a34b63; }}
QPushButton[danger="true"]:disabled {{
    background: #1a2533;
    color: #63748a;
    border: 1px solid #26364b;
}}
QCheckBox {{ spacing: 9px; color: #dce7f7; }}
QCheckBox::indicator {{ width: 17px; height: 17px; }}
QCheckBox::indicator:unchecked {{ background: #111c29; border: 1px solid #3a4d65; border-radius: 5px; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border: 1px solid {ACCENT}; border-radius: 5px; }}
QProgressBar {{
    background: #1a2736;
    border: 1px solid #293d54;
    border-radius: 6px;
    text-align: center;
    color: #f0f6ff;
    min-height: 12px;
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #398bff, stop:1 #5ed7dc);
    border-radius: 5px;
}}
QSplitter::handle {{ background: #26364b; }}
QMessageBox {{ background: #111a26; }}
QToolTip {{
    background: #172333;
    color: #eff6ff;
    border: 1px solid #38516c;
    padding: 6px 8px;
    border-radius: 6px;
}}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 3px 1px; }}
QScrollBar::handle:vertical {{ background: #30445c; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #486987; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 1px 3px; }}
QScrollBar::handle:horizontal {{ background: #30445c; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
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
