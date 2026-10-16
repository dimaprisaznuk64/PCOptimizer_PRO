from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal

from app.logs import get_logger

log = get_logger("tasks")

_RUNNING: set[Task] = set()


def stop_all(timeout_ms: int = 5000) -> None:
    """Wait for every started Task to finish (used at app shutdown).

    Without this, QThreads still running while the interpreter tears down
    can crash (native psutil GC race) — see GamingPage.detect.

    A task is only dropped from the registry once it has really stopped: if it
    is still running after *timeout_ms* we keep it (dropping it would let the
    interpreter destroy a live QThread and crash) and log a warning.
    """
    for task in list(_RUNNING):
        if task.isRunning():
            if not task.wait(timeout_ms):
                log.warning(
                    "task %s did not stop within %d ms; kept registered",
                    getattr(task._fn, "__name__", task._fn),
                    timeout_ms,
                )
                continue
        _RUNNING.discard(task)


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
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        try:
            result = self._fn()
        except Exception as e:
            log.warning("task %s failed: %s", getattr(self._fn, "__name__", self._fn), e)
            self.failed.emit(str(e) or type(e).__name__)
            return
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
        self.done.emit(result)
