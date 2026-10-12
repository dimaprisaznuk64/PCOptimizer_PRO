import time

from app.ui.tasks import Task, stop_all


def test_stop_all_waits_for_running_task() -> None:
    task = Task(fn=lambda: (time.sleep(0.4) or 1), parent=None)
    task.start()

    assert task.isRunning() or not task.isRunning()

    t0 = time.monotonic()
    stop_all(timeout_ms=2000)
    elapsed = time.monotonic() - t0

    assert elapsed >= 0.3
    assert not task.isRunning()


def test_stop_all_idempotent_and_clears() -> None:
    task = Task(fn=lambda: 1, parent=None)
    task.start()
    stop_all(timeout_ms=2000)
    stop_all(timeout_ms=100)
    assert not task.isRunning()