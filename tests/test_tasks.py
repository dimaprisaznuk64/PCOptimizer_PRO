import threading
import time

from app.ui import tasks as tasks_module
from app.ui.tasks import Task, stop_all


def test_stop_all_waits_for_running_task() -> None:
    started = threading.Event()

    def work() -> int:
        started.set()
        time.sleep(0.4)
        return 1

    task = Task(fn=work, parent=None)
    task.start()
    assert started.wait(2.0)

    t0 = time.monotonic()
    stop_all(timeout_ms=2000)
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.3
    assert not task.isRunning()


def test_stop_all_keeps_task_still_running_after_timeout() -> None:
    # A task that outlives the timeout must NOT be dropped from the registry:
    # dropping it lets the interpreter destroy a live QThread and crash.
    task = Task(fn=lambda: (time.sleep(0.6) or 1), parent=None)
    task.start()
    stop_all(timeout_ms=1)

    if task.isRunning():
        assert task in tasks_module._RUNNING
    else:
        assert task not in tasks_module._RUNNING

    # Let it finish so the rest of the suite is not left with a live QThread.
    task.wait(2000)
    stop_all(timeout_ms=50)
    assert task not in tasks_module._RUNNING


def test_stop_all_idempotent_and_clears() -> None:
    task = Task(fn=lambda: 1, parent=None)
    task.start()
    stop_all(timeout_ms=2000)
    stop_all(timeout_ms=100)
    assert not task.isRunning()


def test_stop_all_requests_interruption_before_wait() -> None:
    class InterruptAwareTask(Task):
        def __init__(self) -> None:
            super().__init__(fn=lambda: (time.sleep(0.2) or 1), parent=None)
            self.was_requested = False

        def requestInterruption(self) -> None:
            self.was_requested = True
            super().requestInterruption()

    task = InterruptAwareTask()
    task.start()

    assert stop_all(timeout_ms=2000)
    assert task.was_requested
    assert not task.isRunning()


def test_task_skips_work_when_cancelled_before_start() -> None:
    called: list[str] = []
    task = Task(fn=lambda: called.append("ran"), parent=None)
    task.requestInterruption()
    task.start()

    assert task.wait(2000)
    assert called == []
    stop_all(timeout_ms=50)
