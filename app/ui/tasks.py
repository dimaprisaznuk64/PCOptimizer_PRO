from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from app.logs import get_logger

log = get_logger("tasks")


class _TaskFailed(Exception):
    pass


_RUNNING: set[Task] = set()


def stop_all(timeout_ms: int = 5000) -> bool:
    """Wait for every started Task to finish. Returns False if any is still alive.

    Without this, QThreads still running while the interpreter tears down
    can crash (native psutil GC race) — see GamingPage.detect.

    A task is only dropped from the registry once it has really stopped: if it
    is still running after *timeout_ms* we keep it (dropping it would let the
    interpreter destroy a live QThread and crash) and log a warning.
    """
    all_stopped = True
    for task in list(_RUNNING):
        if task.isRunning():
            if not task.wait(timeout_ms):
                all_stopped = False
                log.warning(
                    "task %s did not stop within %d ms; kept registered",
                    getattr(task._fn, "__name__", task._fn),
                    timeout_ms,
                )
                continue
        _RUNNING.discard(task)
    return all_stopped


class Task(QThread):
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[[], object], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._fn = fn
        self.finished.connect(lambda: _RUNNING.discard(self))

    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> None:
        _RUNNING.add(self)
        super().start(priority)

    def run(self) -> None:
        from app.wincom import run_in_com

        def execute() -> object:
            try:
                return self._fn()
            except Exception as e:
                log.warning("task %s failed: %s", getattr(self._fn, "__name__", self._fn), e)
                self.failed.emit(str(e) or type(e).__name__)
                raise _TaskFailed from e

        try:
            result = run_in_com(execute)
        except _TaskFailed:
            return
        self.done.emit(result)
