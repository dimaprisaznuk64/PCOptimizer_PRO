from __future__ import annotations

import sys
from threading import Event

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import (
    QColor,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QRadialGradient,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QMainWindow,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.alerts import (
    COOLDOWN_S,
    CPU_PERCENT,
    DISK_PERCENT,
    RAM_PERCENT,
    TEMP_CPU_C,
    TEMP_GPU_C,
    TemperatureAlertMonitor,
    UsageAlertMonitor,
    max_cpu_thermal,
    max_cpu_usage,
    max_disk_usage,
    max_gpu_thermal,
    max_memory_usage,
)
from app.gaming import GamingService
from app.history import PerformanceHistory
from app.i18n import I18nService, tr
from app.logs import get_logger
from app.monitor.profiles import profile_for
from app.processes.service import ProcessService
from app.settings import SettingsService

from .pages import build_pages
from .sampler import SensorSampler
from .sidebar import NAV_ITEMS, NAV_KEYS, Sidebar
from .tasks import Task
from .theme import set_application_fonts
from .topbar import TopBar
from .tray import AppTray

# Below this window width the sidebar collapses to icons only.
COMPACT_SIDEBAR_WIDTH = 1200

_log = get_logger("ui.main_window")


class _GamePresenceWatcher(QThread):
    """Polls process names off the GUI thread for quiet-hours alert suppression."""

    presence = Signal(bool)

    def __init__(
        self,
        gaming: GamingService,
        *,
        interval_s: float = 5.0,
        parent: QThread | None = None,
    ) -> None:
        super().__init__(parent)
        self._gaming = gaming
        self._interval_s = max(0.05, interval_s)
        self._stop = Event()

    def set_interval_s(self, interval_s: float) -> None:
        """Change the polling cadence; the running loop picks it up on its next tick."""
        self._interval_s = max(0.05, interval_s)

    def run(self) -> None:
        while not self._stop.is_set():
            try:
                running = self._gaming.is_game_running()
            except Exception as exc:
                _log.warning("game presence check failed: %s", exc)
                running = False
            self.presence.emit(bool(running))
            self._stop.wait(self._interval_s)

    def stop(self, timeout_ms: int = 3000) -> bool:
        self._stop.set()
        if self.isRunning():
            return self.wait(timeout_ms)
        return True


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
        *,
        gaming: GamingService | None = None,
        processes: ProcessService | None = None,
        history: PerformanceHistory | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("PCOptimizer PRO")
        from .icons import app_icon
        from .theme import load_fonts

        load_fonts()

        self.setWindowIcon(app_icon())
        self.setMinimumSize(1024, 640)
        self.resize(1280, 800)
        self.sampler: SensorSampler | None = None
        self.tray: AppTray | None = None
        self._update_task: Task | None = None
        self.settings = settings or SettingsService()
        self._monitor_profile = profile_for(self.settings.get("monitor_profile"))
        from . import theme as th

        th.set_ui_scale(int(self.settings.get("ui_scale")))
        self._gaming = gaming or GamingService()
        self._processes = processes or ProcessService()
        self._game_running = False
        self._game_watcher: _GamePresenceWatcher | None = None
        self._force_quit = False
        self._last_snapshot = None
        self._nav_history: list[str] = []
        self._nav_limit = 50
        self._back_shortcut = QShortcut(QKeySequence("Alt+Left"), self)
        self._back_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._back_shortcut.activated.connect(self.go_back)
        self._search_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self._search_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self._search_shortcut.activated.connect(self.open_search)
        self._history = history or PerformanceHistory(
            process_top=self._processes.top_by_memory,
            interval_s=self._monitor_profile.history_interval_s,
        )
        cooldown = COOLDOWN_S
        self._cpu_monitor = TemperatureAlertMonitor(
            reading=max_cpu_thermal, cooldown_s=cooldown
        )
        self._gpu_monitor = TemperatureAlertMonitor(
            reading=max_gpu_thermal, cooldown_s=cooldown
        )
        self._cpu_usage_monitor = UsageAlertMonitor(
            kind="cpu", reading=max_cpu_usage, cooldown_s=cooldown
        )
        self._ram_usage_monitor = UsageAlertMonitor(
            kind="ram", reading=max_memory_usage, cooldown_s=cooldown
        )
        self._disk_usage_monitor = UsageAlertMonitor(
            kind="disk", reading=max_disk_usage, cooldown_s=cooldown
        )
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
        self.topbar.back_requested.connect(self.go_back)
        self.topbar.search_requested.connect(self.open_search)
        self.topbar.notifications_requested.connect(self.open_notifications)
        self.topbar.set_can_go_back(bool(self._nav_history))
        self._connect_palette()
        self._connect_notifications()
        self.stack = QStackedWidget()

        self._index_by_key: dict[str, int] = {}
        for i, (key, page) in enumerate(
            build_pages(
                self.settings,
                on_theme_applied=self.apply_theme,
                on_scale_applied=self.apply_ui_scale,
                on_wizard_requested=lambda: self.open_first_run(force=True),
                on_dashboard_hidden_applied=self.apply_dashboard_hidden,
                on_monitor_profile_applied=self.apply_monitor_profile,
                monitor_profile=str(self.settings.get("monitor_profile")),
                history=self._history,
            )
        ):
            self._index_by_key[key] = i
            self.stack.addWidget(self._page_host(page))

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

    @staticmethod
    def _nav_label(key: str) -> str:
        """Live nav label: NAV_ITEMS freezes translations at import time."""
        return tr(dict(NAV_KEYS).get(key, key))

    def show_page(self, key: str) -> None:
        if key not in self._index_by_key:
            return
        current = self.current_key
        if current and current != key:
            self._nav_history.append(current)
            if len(self._nav_history) > self._nav_limit:
                del self._nav_history[: len(self._nav_history) - self._nav_limit]
        self._select_page(key)
        self.topbar.set_can_go_back(bool(self._nav_history))

    def go_back(self) -> None:
        """Return to the previously viewed page (Alt+Left / toolbar arrow)."""
        while self._nav_history:
            key = self._nav_history.pop()
            if key in self._index_by_key and key != self.current_key:
                self._select_page(key)
                self.topbar.set_can_go_back(bool(self._nav_history))
                return
        self.topbar.set_can_go_back(False)

    def _connect_palette(self) -> None:
        from .command_palette import CommandPalette

        old = getattr(self, "_palette", None)
        if old is not None:
            old.deleteLater()
        self._palette = CommandPalette(self)
        self._palette.selected.connect(self.show_page)

    def open_search(self) -> None:
        """Open the global search palette (Ctrl+K / topbar button)."""
        palette = getattr(self, "_palette", None)
        if palette is None:
            self._connect_palette()
            palette = self._palette
        palette.open(list(reversed(self._nav_history[-5:])))

    def _connect_notifications(self) -> None:
        from .activity import ActivityLog
        from .notifications import NotificationCenter

        old = getattr(self, "_notifications", None)
        if old is not None:
            old.deleteLater()
        self._notifications = NotificationCenter(self)
        log = ActivityLog.instance()
        if getattr(self, "_unread_connected", False):
            try:
                log.changed.disconnect(self._update_unread)
            except (RuntimeError, TypeError):
                pass
        log.changed.connect(self._update_unread)
        self._unread_connected = True
        self._update_unread()

    def _update_unread(self) -> None:
        from .activity import ActivityLog

        topbar = getattr(self, "topbar", None)
        if topbar is not None:
            topbar.set_unread_count(ActivityLog.instance().unread_count())

    def open_notifications(self) -> None:
        """Open the notification center from the bell button."""
        center = getattr(self, "_notifications", None)
        if center is None:
            self._connect_notifications()
            center = self._notifications
        center.open(getattr(self.topbar, "notify_button", None))

    def open_first_run(self, *, force: bool = False) -> None:
        """Show the setup wizard, optionally again from Settings."""
        from PySide6.QtWidgets import QDialog

        from .first_run import FirstRunWizard

        if force:
            self.settings.set("first_run_completed", False)
        before = {
            key: self.settings.get(key) for key in ("language", "theme", "ui_scale")
        }
        wizard = FirstRunWizard(self.settings, self)
        wizard.open_settings_requested.connect(lambda: self.show_page("settings"))
        result = wizard.exec()
        if result == QDialog.DialogCode.Accepted:
            self._apply_wizard_settings(before, wizard.changes)

    def _apply_wizard_settings(self, before: dict, changes: dict) -> None:
        from . import theme as th

        language = changes.get("language")
        theme_name = changes.get("theme")
        scale = changes.get("ui_scale")
        if scale is not None and int(scale) != int(before.get("ui_scale", 100)):
            th.set_ui_scale(int(scale))
        if language is not None and language != before.get("language"):
            I18nService.instance().set_language(str(language))
        if theme_name is not None and theme_name != before.get("theme"):
            self.apply_theme(str(theme_name))
        elif scale is not None and int(scale) != int(before.get("ui_scale", 100)):
            self.apply_ui_scale(int(scale))

    def _select_page(self, key: str) -> None:
        index = self._index_by_key[key]
        changed = self.stack.currentIndex() != index
        self.stack.setCurrentIndex(index)
        if changed:
            self._fade_in(self.stack.widget(index))
        self.sidebar.set_current(key)
        self.topbar.set_title(self._nav_label(key))
        nav_keys = [k for k, _ in NAV_KEYS]
        if key in nav_keys:
            self.topbar.set_page_index(nav_keys.index(key) + 1, total=len(nav_keys))

    def _fade_in(self, page) -> None:
        """Short fade when switching pages (effect is removed afterwards)."""
        from PySide6.QtCore import QPropertyAnimation
        from PySide6.QtWidgets import QGraphicsOpacityEffect

        from . import theme as th

        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", page)
        anim.setDuration(th.MOTION_FAST)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.finished.connect(lambda: page.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        # Narrow windows get the icon-only rail so the page keeps its room.
        self.sidebar.set_compact(self.width() < COMPACT_SIDEBAR_WIDTH)

    def _on_language_changed(self, _lang: str = "") -> None:
        """Re-translate the whole shell + all pages after a language switch."""
        self.settings.set("language", I18nService.instance().current_language)
        self.sidebar.retranslate()
        self.topbar.retranslate()
        palette = getattr(self, "_palette", None)
        if palette is not None:
            palette.retranslate()
        notifications = getattr(self, "_notifications", None)
        if notifications is not None:
            notifications.retranslate()
        if self.tray is not None:
            self.tray.retranslate()
        for i in range(self.stack.count()):
            page = self._page_widget(self.stack.widget(i))
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

    @staticmethod
    def _page_widget(widget) -> QWidget:
        if widget.objectName() == "pageHost":
            scroll = widget.findChild(QScrollArea, "pageScroll")
            if scroll is not None:
                page = scroll.widget()
                if isinstance(page, QWidget):
                    return page
        if isinstance(widget, QWidget):
            return widget
        raise TypeError(f"expected QWidget, got {type(widget)!r}")

    @staticmethod
    def _page_host(page: QWidget) -> QWidget:
        host = QWidget()
        host.setObjectName("pageHost")
        layout = QVBoxLayout(host)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        scroll = QScrollArea(host)
        scroll.setObjectName("pageScroll")
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setWidget(page)
        layout.addWidget(scroll)
        return host

    def page(self, key: str):
        index = self._index_by_key.get(key)
        return None if index is None else self._page_widget(self.stack.widget(index))

    def _connect_page_navigation(self) -> None:
        """Let any page that exposes a `navigate` signal jump to another page."""
        for i in range(self.stack.count()):
            signal = getattr(self._page_widget(self.stack.widget(i)), "navigate", None)
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
            "theme", "icons", "components", "command_palette", "notifications",
            "operations", "first_run", "monitor", "temperature", "dashboard", "gpu",
            "hardware", "hardware_benchmark", "processes", "cleaner", "startup",
            "optimizer", "gaming", "launcher", "benchmarks", "history", "network",
            "disk", "diagnostics", "drivers", "system_report", "export_center",
            "health", "settings", "sidebar", "topbar", "tray", "pages",
        ):
            module = sys.modules.get(f"app.ui.{name}")
            if module is not None:
                importlib.reload(module)

    def apply_dashboard_hidden(self, hidden: str) -> None:
        index = self._index_by_key.get("dashboard")
        if index is None:
            return
        page = self._page_widget(self.stack.widget(index))
        if page is not None and hasattr(page, "set_hidden_widgets"):
            page.set_hidden_widgets(hidden)

    def apply_monitor_profile(self, key: str, sample_interval_ms: int) -> None:
        """Apply saved monitoring cadences without restarting the application."""
        profile = profile_for(key)
        self._monitor_profile = profile
        if self.sampler is not None:
            self.sampler.set_interval_ms(sample_interval_ms)
        self._history.set_interval_s(profile.history_interval_s)
        if self._game_watcher is not None:
            self._game_watcher.set_interval_s(profile.game_presence_s)
        page = self.page("monitor")
        if page is not None and hasattr(page, "set_process_refresh_ms"):
            page.set_process_refresh_ms(profile.process_refresh_ms)

    def apply_ui_scale(self, percent: int) -> None:
        """Apply a new interface scale instantly (reuses the theme rebuild path)."""
        from . import theme as th

        th.set_ui_scale(percent)
        self.apply_theme(th.CURRENT_THEME)

    def apply_theme(self, name: str) -> None:
        """Apply a new theme instantly (no restart): restyle the app + rebuild every page."""
        from PySide6.QtWidgets import QApplication

        from . import theme as th
        from .icons import app_icon
        from .pages import build_pages
        from .sidebar import Sidebar
        from .tasks import stop_all
        from .topbar import TopBar

        if not stop_all():
            _log.warning("theme change postponed: a background task is still running")
            return

        th.set_theme(name)
        self._reload_ui_modules()
        app = QApplication.instance()
        if app is not None:
            th.apply(app)
        if self.tray is not None:
            self.tray.tray.setIcon(app_icon())

        geometry = self.geometry()
        key = self.current_key
        collapsed_groups = self.sidebar.collapsed_groups()

        self.sidebar.deleteLater()
        self.topbar.deleteLater()
        while self.stack.count():
            widget = self.stack.widget(0)
            if widget is not None:
                self.stack.removeWidget(widget)
                widget.deleteLater()
        self._root_layout.removeWidget(self._content)
        self._content.deleteLater()

        self.sidebar = Sidebar()
        self.sidebar.set_collapsed_groups(collapsed_groups)
        self.topbar = TopBar()
        self.topbar.settings_requested.connect(lambda: self.show_page("settings"))
        self.topbar.back_requested.connect(self.go_back)
        self.topbar.search_requested.connect(self.open_search)
        self.topbar.notifications_requested.connect(self.open_notifications)
        self.topbar.set_can_go_back(bool(self._nav_history))
        self._connect_palette()
        self._connect_notifications()
        self.stack = QStackedWidget()
        self._index_by_key = {}
        for i, (page_key, page) in enumerate(
            build_pages(
                self.settings,
                on_theme_applied=self.apply_theme,
                on_scale_applied=self.apply_ui_scale,
                on_wizard_requested=lambda: self.open_first_run(force=True),
                on_dashboard_hidden_applied=self.apply_dashboard_hidden,
                on_monitor_profile_applied=self.apply_monitor_profile,
                monitor_profile=str(self.settings.get("monitor_profile")),
                history=self._history,
            )
        ):
            self._index_by_key[page_key] = i
            self.stack.addWidget(self._page_host(page))
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
        self._select_page(key if key in self._index_by_key else "dashboard")
        self.topbar.set_can_go_back(bool(self._nav_history))
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
            handler = getattr(self._page_widget(self.stack.widget(i)), "apply_snapshot", None)
            if handler is not None:
                handler(snapshot)
        self._update_sidebar_health(snapshot)
        self._update_tray_tooltip(snapshot)
        game_running = self._game_is_running()
        self._check_temp_alert(snapshot, game_running)
        self._check_usage_alert(snapshot, game_running)

    def start_game_watcher(self) -> None:
        if self._game_watcher is not None:
            return
        watcher = _GamePresenceWatcher(self._gaming, interval_s=self._monitor_profile.game_presence_s)
        watcher.presence.connect(self._set_game_running)
        self._game_watcher = watcher
        watcher.start()

    def _set_game_running(self, running: bool) -> None:
        self._game_running = bool(running)

    def _game_is_running(self) -> bool:
        if not self.settings.get("alerts_quiet_during_games"):
            return False
        if self._game_watcher is not None:
            return self._game_running
        try:
            return self._gaming.is_game_running()
        except Exception:
            return False

    def _check_temp_alert(self, snapshot, game_running: bool = False) -> None:
        if not self.settings.get("temp_alerts_enabled"):
            return
        checks = (
            (self._cpu_monitor, TEMP_CPU_C, True),
            (self._gpu_monitor, TEMP_GPU_C, True),
        )
        for monitor, limit, quiet_in_game in checks:
            if game_running and quiet_in_game:
                monitor.reset()
                continue
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
        record(title, body, level="warn", source="monitor")
        get_logger("alerts").warning(
            "temperature alert: %s at %.0f°C (limit %.0f°C)", source, alert.temperature, alert.limit
        )

    def _check_usage_alert(self, snapshot, game_running: bool = False) -> None:
        if not self.settings.get("usage_alerts_enabled"):
            return
        checks = (
            (self._cpu_usage_monitor, CPU_PERCENT, True),
            (self._ram_usage_monitor, RAM_PERCENT, False),
            (self._disk_usage_monitor, DISK_PERCENT, False),
        )
        for monitor, limit, quiet_in_game in checks:
            if game_running and quiet_in_game:
                monitor.reset()
                continue
            alert = monitor.check(snapshot, limit)
            if alert is not None:
                self._emit_usage_alert(alert)

    def _emit_usage_alert(self, alert) -> None:
        from app.logs import get_logger

        from .activity import record

        title = tr(f"alert_{alert.kind}_title")
        body = tr("alert_usage_body", source=alert.source, value=alert.value, limit=alert.limit)
        if self.tray is not None:
            self.tray.show_message(title, body)
        record(title, body, level="warn", source="monitor")
        get_logger("alerts").warning(
            "usage alert: %s at %.0f%% (limit %.0f%%)", alert.source, alert.value, alert.limit
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

        if ActivityLog.instance().health is not None:
            return
        service = HealthService()
        task = Task(lambda: service.scan(include_junk=False), parent=self, com=True)
        task.done.connect(self._on_auto_health)
        task.failed.connect(lambda _msg: None)
        task.start()

    def _on_auto_health(self, report) -> None:
        from .activity import ActivityLog

        try:
            ActivityLog.instance().set_health(report.score, str(report.grade))
        except (AttributeError, RuntimeError):
            pass

    # ---------- update check ----------

    def schedule_update_check(self, delay_ms: int = 4000) -> None:
        """Ask GitHub for a newer release once, shortly after startup."""
        from PySide6.QtCore import QTimer

        if not self.settings.get("update_check_enabled"):
            return
        QTimer.singleShot(delay_ms, self._auto_update_check)

    def _auto_update_check(self) -> None:
        from app.update import UpdateService

        if self._update_task is not None:
            return
        task = Task(UpdateService().check, parent=self)
        task.done.connect(self._on_update_result)
        task.failed.connect(self._on_update_check_failed)
        self._update_task = task
        task.start()

    def _on_update_check_failed(self, _message: str) -> None:
        self._update_task = None

    def _on_update_result(self, info) -> None:
        self._update_task = None
        if not getattr(info, "available", False):
            return
        from app.logs import get_logger

        from .activity import record

        title = tr("upd_title")
        body = tr("upd_available_msg", version=info.latest)
        if self.tray is not None:
            self.tray.show_message(title, body)
        record(title, body, level="warn", source="settings")
        get_logger("update").info("update available: %s (%s)", info.latest, info.url)

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
        if self._game_watcher is not None:
            self._game_watcher.stop()
        from .tasks import stop_all

        if not stop_all():
            _log.warning("close postponed: a background task is still running")
            event.ignore()
            return
        super().closeEvent(event)

    def shutdown(self) -> None:
        """Destroy the full widget tree before interpreter teardown.

        Without this the window and pages survive to interpreter exit, where
        the underlying Qt objects are collected in a nondeterministic order
        and can crash natively (access violation on the offscreen platform).
        """
        try:
            import warnings

            with warnings.catch_warnings():
                warnings.filterwarnings(
                    "ignore",
                    message=r"^libpyside: Failed to disconnect ",
                    category=RuntimeWarning,
                )
                I18nService.instance().language_changed.disconnect(self._on_language_changed)
        except (RuntimeError, TypeError):
            pass
        if getattr(self, "_unread_connected", False):
            from .activity import ActivityLog

            try:
                import warnings

                with warnings.catch_warnings():
                    warnings.filterwarnings(
                    "ignore",
                    message=r"^libpyside: Failed to disconnect ",
                    category=RuntimeWarning,
                )
                    ActivityLog.instance().changed.disconnect(self._update_unread)
            except (RuntimeError, TypeError):
                pass
            self._unread_connected = False
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
    settings = SettingsService()
    fresh_install = not settings.path.exists()
    if fresh_install:
        settings.set("first_run_completed", False)
        settings.save()
    from . import theme as th

    th.load_fonts()
    th.set_ui_scale(int(settings.get("ui_scale")))
    # Initialize application-wide font settings
    set_application_fonts()
    app.setApplicationName("PCOptimizer PRO")
    app.setApplicationDisplayName("PCOptimizer PRO")
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    th.apply(app)

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
    if not settings.get("first_run_completed"):
        window.open_first_run()
    window.schedule_health_scan()
    window.schedule_update_check()
    window.start_game_watcher()
    sampler.start()
    try:
        return app.exec()
    finally:
        sampler_ok = sampler.stop()
        if window._game_watcher is not None:
            window._game_watcher.stop()
        tray.hide()
        guard.close()
        from .tasks import stop_all

        tasks_ok = stop_all()
        log.info("stopped")
        if tasks_ok:
            window.shutdown()
        else:
            log.warning("background tasks still running; skipping widget teardown")
        app.processEvents()
        if sampler_ok:
            manager.close()
        else:
            log.warning("sampler did not stop in time; sensor backends left open")


if __name__ == "__main__":
    raise SystemExit(run())
