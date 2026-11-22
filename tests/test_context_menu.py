from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QTableWidget

from app.ui.context_menu import TableContextMenu, copy_text


def test_context_menu_triggers_row_action_and_updates_labels(qapp) -> None:
    table = QTableWidget(2, 1)
    context = TableContextMenu(table)
    state = {"label": "EN", "row": None}
    context.add(lambda: state["label"], lambda row: state.__setitem__("row", row), enabled=lambda row: row == 1)
    context.separator()

    menu = context.build_menu(1)
    actions = menu.actions()
    assert actions[0].text() == "EN"
    assert actions[1].isSeparator()
    assert actions[0].isEnabled()
    actions[0].trigger()
    assert state["row"] == 1

    state["label"] = "UA"
    disabled = context.build_menu(0).actions()[0]
    assert disabled.text() == "UA"
    assert not disabled.isEnabled()


def test_copy_text_uses_clipboard(qapp) -> None:
    copy_text("PCOptimizer")
    assert QGuiApplication.clipboard().text() == "PCOptimizer"
