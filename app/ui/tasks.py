from __future__ import annotations

from collections.abc import Callable
from threading import Event

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
        # Cooperative cancellation: a Task that has not started yet will skip
        # its work entirely, and one that is running can check the flag.
        task.requestInterruption()
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

    def __init__(
        self,
        fn: Callable[[], object],
        parent: QObject | None = None,
        *,
        com: bool = False,
    ) -> None:
        super().__init__(parent)
        self._fn = fn
        self._com = com
        self._cancel_requested = Event()
        self.finished.connect(lambda: _RUNNING.discard(self))

    def requestInterruption(self) -> None:
        # Qt ignores interruption requests made before start(); remember them
        # ourselves so a queued Task can still skip its work.
        self._cancel_requested.set()
        super().requestInterruption()

    def _is_cancelled(self) -> bool:
        return self._cancel_requested.is_set() or self.isInterruptionRequested()

    def start(self, priority: QThread.Priority = QThread.Priority.InheritPriority) -> None:
        _RUNNING.add(self)
        super().start(priority)

    def run(self) -> None:
        def execute() -> object:
            if self._is_cancelled():
                return None
            try:
                return self._fn()
            except Exception as e:
                if self._is_cancelled():
                    return None
                log.warning("task %s failed: %s", getattr(self._fn, "__name__", self._fn), e)
                self.failed.emit(str(e) or type(e).__name__)
                raise _TaskFailed from e

        try:
            if self._com:
                from app.wincom import run_in_com

                result = run_in_com(execute)
            else:
                result = execute()
        except _TaskFailed:
            return
        if self._is_cancelled():
            return
        self.done.emit(result)
