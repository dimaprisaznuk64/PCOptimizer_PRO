from __future__ import annotations

from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtWidgets import QApplication

from app.settings import SettingsService
from app.ui.main_window import MainWindow
from app.ui.tray import AppTray, build_icon


def test_build_icon_returns_icon(qapp) -> None:
    icon = build_icon()
    assert not icon.isNull()


def test_tray_menu_structure(qapp) -> None:
    tray = AppTray(parent=qapp)
    actions = tray.menu.actions()
    labels = [a.text() for a in actions if a.text()]
    assert "Open PCOptimizer" in labels
    assert "Gaming Mode" in labels
    assert "Quit" in labels


def test_tray_signals(qapp) -> None:
    tray = AppTray(parent=qapp)
    opened: list[int] = []
    gaming: list[int] = []
    quit_: list[int] = []
    tray.open_requested.connect(lambda: opened.append(1))
    tray.gaming_requested.connect(lambda: gaming.append(1))
    tray.quit_requested.connect(lambda: quit_.append(1))

    tray.open_action.trigger()
    tray.gaming_action.trigger()
    tray.quit_action.trigger()

    assert opened == [1]
    assert gaming == [1]
    assert quit_ == [1]


def test_tray_tooltip(qapp) -> None:
    tray = AppTray(parent=qapp)
    tray.set_tooltip("CPU 10%")
    assert tray.tray.toolTip() == "CPU 10%"


def test_tray_activation_emits_open(qapp) -> None:
    tray = AppTray(parent=qapp)
    opened: list[int] = []
    tray.open_requested.connect(lambda: opened.append(1))
    tray._on_activated(QSystemTrayIcon.ActivationReason.Trigger)
    tray._on_activated(QSystemTrayIcon.ActivationReason.Context)
    assert opened == [1]


def test_close_minimizes_to_tray(qapp, tmp_path) -> None:
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("minimize_to_tray", True)
    window = MainWindow(settings=settings)
    tray = AppTray(parent=qapp)
    tray.show()
    window.attach_tray(tray)
    window.show()

    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()
    assert window.tray is tray
    window._force_quit = True
    window.close()


def test_close_quits_when_tray_disabled(qapp, tmp_path) -> None:
    settings = SettingsService(tmp_path / "settings.json")
    settings.set("minimize_to_tray", False)
    window = MainWindow(settings=settings)
    tray = AppTray(parent=qapp)
    tray.show()
    window.attach_tray(tray)
    window.show()

    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()
    window.close()
    assert not window.isVisible()


def test_quit_app_forces_close(qapp, tmp_path) -> None:
    window = MainWindow(settings=SettingsService(tmp_path / "settings.json"))
    tray = AppTray(parent=qapp)
    tray.show()
    window.attach_tray(tray)
    window.show()

    window.quit_app()
    assert window._force_quit is True
    assert not window.isVisible()


def test_quit_app_exits_event_loop(qapp, tmp_path, monkeypatch) -> None:
    window = MainWindow(settings=SettingsService(tmp_path / "settings.json"))
    tray = AppTray(parent=qapp)
    window.attach_tray(tray)
    window.hide()

    calls: list[int] = []
    monkeypatch.setattr(QApplication, "quit", lambda self: calls.append(1))
    window.quit_app()
    assert calls == [1]


def test_gaming_action_opens_page(qapp, tmp_path) -> None:
    window = MainWindow(settings=SettingsService(tmp_path / "settings.json"))
    tray = AppTray(parent=qapp)
    window.attach_tray(tray)
    tray.gaming_action.trigger()
    assert window.current_key == "gaming"
    window._force_quit = True
    window.close()


def test_tray_tooltip_updates_from_snapshot(qapp, tmp_path) -> None:
    from app.sensors.types import CpuStat, MemoryStat, Snapshot

    settings = SettingsService(tmp_path / "settings.json")
    settings.set("tray_metrics", True)
    window = MainWindow(settings=settings)
    tray = AppTray(parent=qapp)
    window.attach_tray(tray)

    snapshot = Snapshot(
        ts=0.0,
        cpu=CpuStat(
            percent=42.5,
            per_core=(40.0, 45.0),
            physical_cores=8,
            logical_cores=16,
            freq_mhz=3000.0,
        ),
        memory=MemoryStat(
            total=16_000_000_000,
            used=8_000_000_000,
            available=8_000_000_000,
            percent=50.0,
            swap_total=0,
            swap_used=0,
            swap_percent=0.0,
        ),
    )
    window.handle_snapshot(snapshot)
    tooltip = tray.tray.toolTip()
    assert "CPU 43%" in tooltip or "CPU 42%" in tooltip
    assert "RAM 50%" in tooltip
    window._force_quit = True
    window.close()


def test_tray_tooltip_disabled_by_setting(qapp, tmp_path) -> None:
    from app.sensors.types import CpuStat, Snapshot

    settings = SettingsService(tmp_path / "settings.json")
    settings.set("tray_metrics", False)
    window = MainWindow(settings=settings)
    tray = AppTray(parent=qapp)
    window.attach_tray(tray)

    snapshot = Snapshot(
        ts=0.0,
        cpu=CpuStat(percent=10.0, per_core=(10.0,), physical_cores=1, logical_cores=1, freq_mhz=None),
    )
    window.handle_snapshot(snapshot)
    assert tray.tray.toolTip() == "PCOptimizer PRO"
    window._force_quit = True
    window.close()
