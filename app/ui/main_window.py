from __future__ import annotations

import faulthandler
import sys
import threading

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QStatusBar, QWidget

from app.logs import get_logger
from app.settings import SettingsService

from .pages import build_pages
from .sampler import SensorSampler
from .sidebar import NAV_ITEMS, Sidebar
from .theme import apply
from .tray import AppTray

log = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PCOptimizer PRO")
        self.setMinimumSize(1024, 640)
        self.resize(1280, 800)
        self.sampler: SensorSampler | None = None
        self.tray: AppTray | None = None
        self.settings = settings or SettingsService()
        self._force_quit = False

        root = QWidget()
        root.setObjectName("root")
        self._root_layout = QHBoxLayout(root)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self._index_by_key: dict[str, int] = {}
        for i, (key, page) in enumerate(build_pages(self.settings)):
            self._index_by_key[key] = i
            self.stack.addWidget(page)

        self.sidebar.navigated.connect(self.show_page)
        self._root_layout.addWidget(self.sidebar)
        self._root_layout.addWidget(self.stack, 1)

        self.setCentralWidget(root)

        status = QStatusBar()
        status.setSizeGripEnabled(False)
        self.setStatusBar(status)
        status.showMessage("Ready")

        missing = set(key for key, _ in NAV_ITEMS) - set(self._index_by_key)
        if missing:
            raise RuntimeError(f"pages missing for nav keys: {sorted(missing)}")

        self.show_page("dashboard")

    @property
    def current_key(self) -> str:
        for key, index in self._index_by_key.items():
            if index == self.stack.currentIndex():
                return key
        return ""

    def show_page(self, key: str) -> None:
        index = self._index_by_key.get(key)
        if index is None:
            return
        self.stack.setCurrentIndex(index)
        self.sidebar.set_current(key)
        self.statusBar().showMessage(f"{dict(NAV_ITEMS).get(key, key)}")

    def page(self, key: str):
        index = self._index_by_key.get(key)
        return None if index is None else self.stack.widget(index)

    # ---------- tray ----------

    def attach_tray(self, tray: AppTray) -> None:
        self.tray = tray
        tray.open_requested.connect(self.open_window)
        tray.gaming_requested.connect(self.open_gaming)
        tray.quit_requested.connect(self.quit_app)

    def open_window(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()

    def open_gaming(self) -> None:
        self.show_page("gaming")
        self.open_window()

    def quit_app(self) -> None:
        self._force_quit = True
        self.close()

    # ---------- snapshots ----------

    def handle_snapshot(self, snapshot) -> None:
        for i in range(self.stack.count()):
            widget = self.stack.widget(i)
            handler = getattr(widget, "apply_snapshot", None)
            if handler is not None:
                try:
                    handler(snapshot)
                except Exception as exc:
                    log.warning("error applying snapshot to %s: %s", type(widget).__name__, exc)
        try:
            self._update_tray_tooltip(snapshot)
        except Exception as exc:
            log.warning("error updating tray tooltip: %s", exc)

    def _update_tray_tooltip(self, snapshot) -> None:
        if self.tray is None or not self.settings.get("tray_metrics"):
            return
        parts: list[str] = []
        if snapshot.cpu is not None:
            parts.append(f"CPU {snapshot.cpu.percent:.0f}%")
        if snapshot.memory is not None:
            parts.append(f"RAM {snapshot.memory.percent:.0f}%")
        if parts:
            self.tray.set_tooltip("PCOptimizer PRO\n" + " · ".join(parts))

    # ---------- lifecycle ----------

    def closeEvent(self, event) -> None:
        tray_ok = (
            not self._force_quit
            and self.tray is not None
            and self.tray.visible
            and self.settings.get("minimize_to_tray")
        )
        if tray_ok:
            event.ignore()
            self.hide()
            return
        if self.sampler is not None:
            self.sampler.stop()
        super().closeEvent(event)


def run(argv: list[str] | None = None) -> int:
    from app.logs import get_logger, setup_logging
    from app.sensors import SensorManager

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("PCOptimizer PRO")
    app.setApplicationDisplayName("PCOptimizer PRO")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    apply(app)

    settings = SettingsService()
    if not settings.path.exists():
        settings.save()
    log_file = setup_logging(settings.get("log_level"))
    log = get_logger("main")
    log.info("starting PCOptimizer PRO (settings: %s, log: %s)", settings.path, log_file)

    crash_log = log_file.with_name("crash.log")
    try:
        faulthandler.enable(crash_log.open("a"))
    except Exception:
        faulthandler.enable()

    def _log_uncaught(kind: str, exc: BaseException, tb) -> None:
        log.error("%s uncaught: %s", kind, exc)

    sys.excepthook = lambda etype, exc, tb: _log_uncaught("main thread", exc, tb)
    threading.excepthook = lambda args: _log_uncaught("worker thread", args.exc_value, args.exc_traceback)

    manager = SensorManager.with_defaults()
    window = MainWindow(settings=settings)
    sampler = SensorSampler(manager, interval_ms=settings.get("sample_interval_ms"))
    sampler.snapshot_ready.connect(window.handle_snapshot)
    window.sampler = sampler

    tray = AppTray(parent=app)
    window.attach_tray(tray)
    tray.show()

    if settings.get("start_minimized"):
        window.showMinimized()
    else:
        window.show()
    sampler.start()
    try:
        code = app.exec()
    finally:
        sampler.stop()
        tray.hide()
        log.info("stopped")
        manager.close()
    if not isinstance(code, int):
        code = 0
    log.info("exiting (code %s)", code)
    return code


if __name__ == "__main__":
    raise SystemExit(run())
