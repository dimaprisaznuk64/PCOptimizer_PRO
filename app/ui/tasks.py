from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal


class Task(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as e:
            self.failed.emit(str(e) or type(e).__name__)
            return
        self.done.emit(result)
