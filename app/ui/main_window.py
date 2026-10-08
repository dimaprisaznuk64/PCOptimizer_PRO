from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMainWindow, QStackedWidget, QStatusBar, QWidget

from .pages import build_pages
from .sampler import SensorSampler
from .sidebar import NAV_ITEMS, Sidebar
from .theme import apply


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PCOptimizer PRO")
        self.setMinimumSize(1024, 640)
        self.resize(1280, 800)
        self.sampler: SensorSampler | None = None

        root = QWidget()
        root.setObjectName("root")
        self._root_layout = QHBoxLayout(root)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.stack = QStackedWidget()

        self._index_by_key: dict[str, int] = {}
        for i, (key, page) in enumerate(build_pages()):
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
        self.statusBar().showMessage(f"{dict(NAV_ITEMS).get(key, key)}")

    def handle_snapshot(self, snapshot) -> None:
        for i in range(self.stack.count()):
            handler = getattr(self.stack.widget(i), "apply_snapshot", None)
            if handler is not None:
                handler(snapshot)

    def closeEvent(self, event) -> None:
        if self.sampler is not None:
            self.sampler.stop()
        super().closeEvent(event)


def run(argv: list[str] | None = None) -> int:
    from app.sensors import SensorManager

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("PCOptimizer PRO")
    app.setApplicationDisplayName("PCOptimizer PRO")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    apply(app)

    manager = SensorManager.with_defaults()
    window = MainWindow()
    sampler = SensorSampler(manager, interval_ms=1000)
    sampler.snapshot_ready.connect(window.handle_snapshot)
    window.sampler = sampler

    window.show()
    sampler.start()
    try:
        return app.exec()
    finally:
        sampler.stop()
        manager.close()


if __name__ == "__main__":
    raise SystemExit(run())
