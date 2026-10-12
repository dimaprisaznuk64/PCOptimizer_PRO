from __future__ import annotations

from threading import Event

from PySide6.QtCore import QThread, Signal

from app.sensors import SensorManager


class SensorSampler(QThread):
    snapshot_ready = Signal(object)

    def __init__(self, manager: SensorManager, interval_ms: int = 1000, parent: QThread | None = None) -> None:
        super().__init__(parent)
        self._manager = manager
        self._interval_s = max(interval_ms, 50) / 1000.0
        self._stop = Event()

    def run(self) -> None:
        try:
            import pythoncom
            pythoncom.CoInitialize()
        except Exception:
            pass
        try:
            while not self._stop.is_set():
                try:
                    snapshot = self._manager.snapshot()
                except Exception:
                    self._stop.wait(self._interval_s)
                    continue
                self.snapshot_ready.emit(snapshot)
                self._stop.wait(self._interval_s)
        finally:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass

    def stop(self, timeout_ms: int = 5000) -> None:
        self._stop.set()
        if self.isRunning():
            self.wait(timeout_ms)
