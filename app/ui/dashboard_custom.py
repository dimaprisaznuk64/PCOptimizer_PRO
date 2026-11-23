from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr

from .theme import SPACING_SM, SPACING_XS

DASH_WIDGET_KEYS = (
    "cpu",
    "ram",
    "gpu",
    "disk",
    "temp",
    "health",
    "chart",
    "history",
    "thermal",
    "disks",
    "processes",
    "quick",
    "gaming",
    "network",
    "notifications",
    "recent",
    "recommendations",
)

DASH_WIDGET_SECTION = {
    "cpu": 0,
    "ram": 0,
    "gpu": 0,
    "disk": 0,
    "temp": 0,
    "health": 0,
    "chart": 1,
    "history": 1,
    "thermal": 1,
    "disks": 2,
    "processes": 2,
    "quick": 2,
    "gaming": 2,
    "network": 2,
    "notifications": 2,
    "recent": 3,
    "recommendations": 3,
}

_SECTION_KEYS = (
    "dash_sec_overview",
    "dash_sec_monitoring",
    "dash_sec_system",
    "dash_sec_activity",
)


def parse_dashboard_hidden(value: object) -> set[str]:
    if isinstance(value, str):
        items = value.split(",")
    elif isinstance(value, (set, list, tuple)):
        items = list(value)
    else:
        items = []
    return {key.strip() for key in map(str, items) if key.strip() in DASH_WIDGET_KEYS}


def serialize_dashboard_hidden(keys: object) -> str:
    selected = parse_dashboard_hidden(keys)
    return ",".join(key for key in DASH_WIDGET_KEYS if key in selected)


class DashboardCustomizerDialog(QDialog):
    def __init__(self, hidden: object, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("dash_custom_title"))
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        desc = QLabel(tr("dash_custom_desc"))
        desc.setWordWrap(True)
        layout.addWidget(desc)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.viewport().setAutoFillBackground(False)
        host = QWidget()
        form = QVBoxLayout(host)
        form.setContentsMargins(SPACING_XS, SPACING_XS, SPACING_XS, SPACING_XS)
        form.setSpacing(SPACING_SM)

        self._checks: dict[str, QCheckBox] = {}
        for section, section_key in enumerate(_SECTION_KEYS):
            heading = QLabel(tr(section_key).upper())
            heading.setObjectName("hudTag")
            form.addWidget(heading)
            for key in DASH_WIDGET_KEYS:
                if DASH_WIDGET_SECTION[key] != section:
                    continue
                check = QCheckBox(tr(f"dash_custom_{key}"))
                check.setChecked(key not in parse_dashboard_hidden(hidden))
                form.addWidget(check)
                self._checks[key] = check
        scroll.setWidget(host)
        layout.addWidget(scroll, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> set[str]:
        return {key for key, check in self._checks.items() if not check.isChecked()}
