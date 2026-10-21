"""Guard: every visible text size must come from the type scale.

The app has a single type scale in `app/ui/theme.py` (T_MICRO .. T_HERO).
Pages must pick a role instead of inventing a number - this test walks every
page and fails when a visible widget uses a font size outside the scale.
"""

import pytest

from app.ui import theme

PAGES = [
    "dashboard",
    "monitor",
    "gpu",
    "processes",
    "cleaner",
    "startup",
    "optimizer",
    "gaming",
    "network",
    "disk",
    "health",
    "benchmarks",
    "hardware",
    "diagnostics",
    "history",
    "launcher",
    "settings",
]

TEXT_CLASSES = ("QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QToolButton", "QGroupBox")


def _scale():
    return {
        theme.T_MICRO,
        theme.T_CAPTION,
        theme.T_SMALL,
        theme.T_BODY,
        theme.T_LEAD,
        theme.T_H2,
        theme.T_H1,
        theme.T_TITLE,
        theme.T_VALUE,
        theme.T_HERO,
        theme.BASE_FONT_PX,
    }


def _visible_text_sizes(page):
    out = []
    for widget in page.findChildren(object):
        cls = type(widget).__name__
        if cls not in TEXT_CLASSES:
            continue
        if not widget.isVisible():
            continue
        if not (widget.text() or "").strip():
            continue
        font = widget.font()
        size = font.pixelSize()
        if not size:
            continue
        out.append((cls, size, widget.text()[:24]))
    return out


@pytest.mark.parametrize("page_key", PAGES)
def test_page_text_sizes_come_from_the_type_scale(qapp, page_key):
    from app.ui.main_window import MainWindow

    window = MainWindow()
    window.show_page(page_key)
    qapp.processEvents()
    page = window.stack.currentWidget()
    allowed = _scale()
    offenders = [(c, s, t) for c, s, t in _visible_text_sizes(page) if s not in allowed]
    assert not offenders, (
        f"page '{page_key}' uses font sizes outside the type scale {sorted(allowed)}: {offenders}"
    )
    window.close()


def test_stylesheet_font_sizes_come_from_the_type_scale():
    """Every QSS font size must be one of the scale values."""
    import re

    qss = theme.build_stylesheet()
    raw = {int(v) for v in re.findall(r"font-size:\s*(\d+)px", qss)}
    allowed = _scale()
    assert raw, "stylesheet has no font-size rules at all"
    assert raw <= allowed, f"stylesheet uses sizes outside the scale: {sorted(raw - allowed)}"
