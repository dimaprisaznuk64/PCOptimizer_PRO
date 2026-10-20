from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QRadialGradient
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.alerts import TemperatureAlertMonitor, max_cpu_thermal, max_gpu_thermal
from app.history import PerformanceHistory
from app.i18n import I18nService, tr
from app.settings import SettingsService

from .pages import build_pages
from .sampler import SensorSampler
from .sidebar import NAV_ITEMS, Sidebar
from .theme import apply, set_application_fonts
from .topbar import TopBar
from .tray import AppTray


class _GlowRoot(QWidget):
    """Window background: flat dark base, soft coloured glows and a faint HUD grid."""

    def paintEvent(self, event) -> None:
        from . import theme

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(theme.BG))
        w, h = self.width(), self.height()

        # Faint HUD grid (two levels for a cockpit feel).
        grid = QColor(theme.TEXT)
        grid.setAlpha(10)
        painter.setPen(grid)
        step = 44
        for x in range(0, w, step):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, step):
            painter.drawLine(0, y, w, y)
        grid_hi = QColor(theme.TEXT)
        grid_hi.setAlpha(16)
        painter.setPen(grid_hi)
        big = step * 4
        for x in range(0, w, big):
            painter.drawLine(x, 0, x, h)
        for y in range(0, h, big):
            painter.drawLine(0, y, w, y)

        for cx, cy, radius, color, alpha in (
            (w * 0.92, h * 0.02, max(w, h) * 0.55, theme.GLOW_A, theme.GLOW_ALPHA_A),
            (w * 0.35, h * 1.05, max(w, h) * 0.5, theme.GLOW_B, theme.GLOW_ALPHA_B),
        ):
            glow = QRadialGradient(cx, cy, radius)
            inner = QColor(color)
            inner.setAlpha(alpha)
            outer = QColor(color)
            outer.setAlpha(0)
            glow.setColorAt(0.0, inner)
            glow.setColorAt(1.0, outer)
            painter.fillRect(self.rect(), glow)


class MainWindow(QMainWindow):
    def __init__(
        self,
        settings: SettingsService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PCOptimizer PRO")
        from .icons import app_icon
        from .theme import load_fonts

        load_fonts()

        self.setWindowIcon(app_icon())
        self.setMinimumSize(1120, 680)
        self.resize(1280, 800)
        self.sampler: SensorSampler | None = None
        self.tray: AppTray | None = None
        self.settings = settings or SettingsService()
        self._force_quit = False
        self._last_snapshot = None
        self._history = PerformanceHistory()
        self._cpu_monitor = TemperatureAlertMonitor(reading=max_cpu_thermal)
        self._gpu_monitor = TemperatureAlertMonitor(reading=max_gpu_thermal)
        I18nService.instance().set_language(self.settings.get("language"), emit=False)
        I18nService.instance().language_changed.connect(self._on_language_changed)

        root = _GlowRoot()
        root.setObjectName("root")
        self._root_layout = QHBoxLayout(root)
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.topbar = TopBar()
        self.topbar.settings_requested.connect(lambda: self.show_page("settings"))
        self.stack = QStackedWidget()

        self._index_by_key: dict[str, int] = {}
        for i, (key, page) in enumerate(build_pages(self.settings, on_theme_applied=self.apply_theme)):
            self._index_by_key[key] = i
            self.stack.addWidget(page)

        self.sidebar.navigated.connect(self.show_page)
        self._connect_page_navigation()
        self._root_layout.addWidget(self.sidebar)

        self._content = QWidget()
        self._content.setObjectName("root")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.topbar)
        content_layout.addWidget(self.stack, 1)
        self._root_layout.addWidget(self._content, 1)

        self.setCentralWidget(root)

        missing = {key for key, _ in NAV_ITEMS} - set(self._index_by_key)
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
        changed = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index)
        if changed:
            self._fade_in(self.stack.widget(index))
        self.sidebar.set_current(key)
        self.topbar.set_title(dict(NAV_ITEMS).get(key, key))
        nav_keys = [k for k, _ in NAV_ITEMS]
        if key in nav_keys:
            self.topbar.set_page_index(nav_keys.index(key) + 1, total=len(nav_keys))

    def _fade_in(self, page) -> None:
        """Short fade when switching pages (effect is removed afterwards)."""
        from PySide6.QtCore import QPropertyAnimation
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(170)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def _on_language_changed(self, _lang: str = "") -> None:
        """Re-translate the whole shell + all pages after a language switch."""
        self.settings.set("language", I18nService.instance().current_language)
        self.sidebar.retranslate()
        self.topbar.retranslate()
        if self.tray is not None:
            self.tray.retranslate()
        for i in range(self.stack.count()):
            page = self.stack.widget(i)
            retranslate = getattr(page, "retranslate", None)
            if retranslate is None:
                continue
            try:
                retranslate()
            except RuntimeError:
                pass
        if self._last_snapshot is not None:
            self._update_sidebar_health(self._last_snapshot)
        self.show_page(self.current_key)

    def page(self, key: str):
        index = self._index_by_key.get(key)
        return None if index is None else self.stack.widget(index)

    def _connect_page_navigation(self) -> None:
        """Let any page that exposes a `navigate` signal jump to another page."""
        for i in range(self.stack.count()):
            signal = getattr(self.stack.widget(i), "navigate", None)
            if signal is not None:
                signal.connect(self.show_page)

    # ---------- live theme switching ----------

    def _reload_ui_modules(self) -> None:
        """Re-import every module that snapshots theme tokens via 'from .theme import ...'.

        importlib.reload re-executes each module's code in its shared module dict,
        so the module-level token bindings are refreshed before pages are rebuilt.
        """
        import importlib

        for name in (
            "theme", "icons", "components", "monitor", "dashboard", "gpu",
            "hardware", "processes", "cleaner", "startup", "optimizer", "gaming",
            "launcher", "benchmarks", "history", "network", "disk", "diagnostics", "health",
            "settings",
            "sidebar", "topbar", "tray", "pages",
        ):
            module = sys.modules.get(f"app.ui.{name}")
            if module is not None:
                importlib.reload(module)

    def apply_theme(self, name: str) -> None:
        """Apply a new theme instantly (no restart): restyle the app + rebuild every page."""
        from PySide6.QtWidgets import QApplication

        from . import theme as th
        from .icons import app_icon
        from .pages import build_pages
        from .sidebar import Sidebar
        from .tasks import stop_all
        from .topbar import TopBar

        th.set_theme(name)
        self._reload_ui_modules()
        app = QApplication.instance()
        if app is not None:
            th.apply(app)
        if self.tray is not None:
            self.tray.tray.setIcon(app_icon())

        geometry = self.geometry()
        key = self.current_key

        stop_all()

        self.sidebar.deleteLater()
        self.topbar.deleteLater()
        while self.stack.count():
            widget = self.stack.widget(0)
            self.stack.removeWidget(widget)
            widget.deleteLater()
        self._root_layout.removeWidget(self._content)
        self._content.deleteLater()

        self.sidebar = Sidebar()
        self.topbar = TopBar()
        self.topbar.settings_requested.connect(lambda: self.show_page("settings"))
        self.stack = QStackedWidget()
        self._index_by_key = {}
        for i, (page_key, page) in enumerate(
            build_pages(self.settings, on_theme_applied=self.apply_theme)
        ):
            self._index_by_key[page_key] = i
            self.stack.addWidget(page)
        self.sidebar.navigated.connect(self.show_page)
        self._connect_page_navigation()
        self._root_layout.addWidget(self.sidebar)

        self._content = QWidget()
        self._content.setObjectName("root")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        content_layout.addWidget(self.topbar)
        content_layout.addWidget(self.stack, 1)
        self._root_layout.addWidget(self._content, 1)

        self.setGeometry(geometry)
        self.show_page(key)
        if self._last_snapshot is not None:
            self.handle_snapshot(self._last_snapshot)
        root = self.centralWidget()
        if root is not None:
            root.update()

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
        app = QApplication.instance()
        if app is not None:
            app.quit()

    # ---------- snapshots ----------

    def handle_snapshot(self, snapshot) -> None:
        self._last_snapshot = snapshot
        self._history.record(snapshot)
        for i in range(self.stack.count()):
            handler = getattr(self.stack.widget(i), "apply_snapshot", None)
            if handler is not None:
                handler(snapshot)
        self._update_sidebar_health(snapshot)
        self._update_tray_tooltip(snapshot)
        self._check_temp_alert(snapshot)

    def _check_temp_alert(self, snapshot) -> None:
        if not self.settings.get("temp_alerts_enabled"):
            return
        checks = (
            (self._cpu_monitor, float(self.settings.get("temp_alert_cpu"))),
            (self._gpu_monitor, float(self.settings.get("temp_alert_gpu"))),
        )
        for monitor, limit in checks:
            alert = monitor.check(snapshot, limit)
            if alert is not None:
                self._emit_temp_alert(alert)

    def _emit_temp_alert(self, alert) -> None:
        from app.logs import get_logger

        from .activity import record
        from .format import zone_label

        source = zone_label(alert.source)
        title = tr("alert_temp_title")
        body = tr("alert_temp_body", source=source, temp=alert.temperature, limit=alert.limit)
        if self.tray is not None:
            self.tray.show_message(title, body)
        record(title, body, level="warn")
        get_logger("alerts").warning(
            "temperature alert: %s at %.0f°C (limit %.0f°C)", source, alert.temperature, alert.limit
        )

    def _update_sidebar_health(self, snapshot) -> None:
        loads = [v for v in (
            snapshot.cpu.percent if snapshot.cpu else None,
            snapshot.memory.percent if snapshot.memory else None,
        ) if v is not None]
        peak = max(loads) if loads else 0.0
        if not loads:
            self.sidebar.set_health(tr("status_no_sensor"), "warn")
            self.topbar.set_status(tr("status_no_sensor"), "warn")
        elif peak >= 90:
            self.sidebar.set_health(tr("status_high"), "danger")
            self.topbar.set_status(tr("status_high"), "danger")
        elif peak >= 75:
            self.sidebar.set_health(tr("status_busy"), "warn")
            self.topbar.set_status(tr("status_busy"), "warn")
        else:
            self.sidebar.set_health(tr("status_healthy"), "ok")
            self.topbar.set_status(tr("status_healthy"), "ok")

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

    # ---------- startup health ----------

    def schedule_health_scan(self, delay_ms: int = 2500) -> None:
        """Fill the dashboard health card once at startup (light scan, no junk walk)."""
        from PySide6.QtCore import QTimer

        QTimer.singleShot(delay_ms, self._auto_health_scan)

    def _auto_health_scan(self) -> None:
        from app.health import HealthService

        from .activity import ActivityLog
        from .tasks import Task

        if ActivityLog.instance().health is not None:
            return
        service = HealthService()
        task = Task(lambda: service.scan(include_junk=False), parent=self)
        task.done.connect(self._on_auto_health)
        task.failed.connect(lambda _msg: None)
        task.start()

    def _on_auto_health(self, report) -> None:
        from .activity import ActivityLog

        try:
            ActivityLog.instance().set_health(report.score, str(report.grade))
        except (AttributeError, RuntimeError):
            pass

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
        from .tasks import stop_all

        stop_all()
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Destroy the full widget tree before interpreter teardown.

        Without this the window and pages survive to interpreter exit, where
        the underlying Qt objects are collected in a nondeterministic order
        and can crash natively (access violation on the offscreen platform).
        """
        try:
            I18nService.instance().language_changed.disconnect(self._on_language_changed)
        except (RuntimeError, TypeError):
            pass
        self._force_quit = True
        self.close()
        self.deleteLater()


def run(argv: list[str] | None = None) -> int:
    from app.logs import get_logger, setup_logging
    from app.sensors import SensorManager

    from .single_instance import SingleInstanceGuard

    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(argv if argv is not None else sys.argv)
    from .theme import load_fonts

    load_fonts()
    # Initialize application-wide font settings
    set_application_fonts()
    app.setApplicationName("PCOptimizer PRO")
    app.setApplicationDisplayName("PCOptimizer PRO")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    apply(app)

    settings = SettingsService()
    if not settings.path.exists():
        settings.save()
    log_file = setup_logging(settings.get("log_level"))
    log = get_logger("main")

    guard = SingleInstanceGuard(parent=app)
    if not guard.acquire():
        log.info("another instance is already running — exiting")
        return 0

    from app import __version__

    log.info("starting PCOptimizer PRO %s (settings: %s, log: %s)", __version__, settings.path, log_file)

    manager = SensorManager.with_defaults()
    window = MainWindow(settings=settings)
    guard.show_requested.connect(window.open_window)
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
    window.schedule_health_scan()
    sampler.start()
    try:
        return app.exec()
    finally:
        sampler.stop()
        tray.hide()
        guard.close()
        from .tasks import stop_all

        stop_all()
        log.info("stopped")
        window.shutdown()
        app.processEvents()
        manager.close()


if __name__ == "__main__":
    raise SystemExit(run())
