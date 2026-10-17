from __future__ import annotations

from app.alerts import (
    TemperatureAlertMonitor,
    max_cpu_thermal,
    max_gpu_thermal,
    max_thermal,
)
from app.sensors import GpuStat, Snapshot, ThermalStat


def _snap(thermal=(), gpus=(), ts: float = 0.0) -> Snapshot:
    return Snapshot(
        ts=ts,
        thermal=ThermalStat(source="test", temperatures=tuple(thermal)) if thermal else None,
        gpus=tuple(gpus),
    )


def test_max_thermal_picks_hottest_zone() -> None:
    snap = _snap(thermal=[("cpu", 55.0), ("zone0", 72.0), ("zone1", 61.0)])
    assert max_thermal(snap) == (72.0, "zone0")


def test_max_thermal_considers_gpu() -> None:
    snap = _snap(
        thermal=[("cpu", 55.0)],
        gpus=[GpuStat(0, "RTX 3050 Ti", 30.0, 1, 2, temperature=83.0)],
    )
    assert max_thermal(snap) == (83.0, "RTX 3050 Ti")


def test_max_thermal_none_without_readings() -> None:
    assert max_thermal(_snap()) is None


def test_max_cpu_thermal_ignores_gpu() -> None:
    snap = _snap(
        thermal=[("cpu", 70.0)],
        gpus=[GpuStat(0, "RTX", 30.0, 1, 2, temperature=99.0)],
    )
    assert max_cpu_thermal(snap) == (70.0, "cpu")


def test_max_gpu_thermal_ignores_cpu_zones() -> None:
    snap = _snap(
        thermal=[("cpu", 99.0)],
        gpus=[GpuStat(0, "RTX", 30.0, 1, 2, temperature=75.0)],
    )
    assert max_gpu_thermal(snap) == (75.0, "RTX")


def test_max_cpu_thermal_none_without_zones() -> None:
    snap = _snap(gpus=[GpuStat(0, "RTX", 30.0, 1, 2, temperature=75.0)])
    assert max_cpu_thermal(snap) is None


def test_max_gpu_thermal_none_without_gpus() -> None:
    assert max_gpu_thermal(_snap(thermal=[("cpu", 50.0)])) is None


def test_monitor_uses_custom_reading_selector() -> None:
    monitor = TemperatureAlertMonitor(clock=lambda: 0.0, reading=max_gpu_thermal)
    # CPU is hot but GPU is cool → GPU-only monitor must stay silent.
    snap = _snap(
        thermal=[("cpu", 99.0)],
        gpus=[GpuStat(0, "RTX", 30.0, 1, 2, temperature=50.0)],
    )
    assert monitor.check(snap, 90.0) is None


def test_alert_fires_when_crossing_limit() -> None:
    now = [0.0]
    monitor = TemperatureAlertMonitor(cooldown_s=300.0, clock=lambda: now[0])
    snap = _snap(thermal=[("cpu", 95.0)])
    alert = monitor.check(snap, 90.0)
    assert alert is not None
    assert alert.temperature == 95.0
    assert alert.limit == 90.0


def test_alert_silent_below_limit() -> None:
    monitor = TemperatureAlertMonitor(clock=lambda: 0.0)
    assert monitor.check(_snap(thermal=[("cpu", 70.0)]), 90.0) is None


def test_alert_suppressed_within_cooldown() -> None:
    now = [0.0]
    monitor = TemperatureAlertMonitor(cooldown_s=300.0, clock=lambda: now[0])
    hot = _snap(thermal=[("cpu", 95.0)])
    assert monitor.check(hot, 90.0) is not None
    now[0] = 100.0
    assert monitor.check(hot, 90.0) is None


def test_alert_repeats_after_cooldown() -> None:
    now = [0.0]
    monitor = TemperatureAlertMonitor(cooldown_s=300.0, clock=lambda: now[0])
    hot = _snap(thermal=[("cpu", 95.0)])
    assert monitor.check(hot, 90.0) is not None
    now[0] = 301.0
    assert monitor.check(hot, 90.0) is not None


def test_alert_rearms_after_cooling() -> None:
    now = [0.0]
    monitor = TemperatureAlertMonitor(cooldown_s=300.0, clock=lambda: now[0])
    hot = _snap(thermal=[("cpu", 95.0)])
    cool = _snap(thermal=[("cpu", 60.0)])
    assert monitor.check(hot, 90.0) is not None
    assert monitor.check(cool, 90.0) is None
    now[0] = 10.0
    assert monitor.check(hot, 90.0) is not None


class _StubTray:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str]] = []
        self.tooltip = ""
        self.visible = False

    def show_message(self, title: str, body: str) -> None:
        self.messages.append((title, body))

    def set_tooltip(self, text: str) -> None:
        self.tooltip = text


def test_main_window_alerts_on_hot_snapshot(qapp) -> None:
    from app.sensors import SensorManager
    from app.sensors.mock_backend import MockBackend
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(
        data={"temp_alerts_enabled": True, "temp_alert_cpu": 90, "temp_alert_gpu": 90}
    )
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    snap = SensorManager([MockBackend(temperature_c=99.0)]).snapshot()
    window.handle_snapshot(snap)
    # MockBackend reports both a hot CPU zone and a hot GPU → two independent alerts.
    assert len(tray.messages) == 2
    bodies = " ".join(body for _, body in tray.messages)
    assert "cpu" in bodies.lower()
    assert "gpu" in bodies.lower()
    assert all("99" in body for _, body in tray.messages)


def test_main_window_separate_cpu_gpu_thresholds(qapp) -> None:
    from app.sensors import SensorManager
    from app.sensors.mock_backend import MockBackend
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    # CPU limit low (fires), GPU limit high (silent) even though both read 99°C.
    settings = SettingsService(
        data={"temp_alerts_enabled": True, "temp_alert_cpu": 90, "temp_alert_gpu": 100}
    )
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    snap = SensorManager([MockBackend(temperature_c=99.0)]).snapshot()
    window.handle_snapshot(snap)
    assert len(tray.messages) == 1
    assert "cpu" in tray.messages[0][1].lower()


def test_main_window_respects_disabled_alerts(qapp) -> None:
    from app.sensors import SensorManager
    from app.sensors.mock_backend import MockBackend
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(data={"temp_alerts_enabled": False})
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    snap = SensorManager([MockBackend(temperature_c=99.0)]).snapshot()
    window.handle_snapshot(snap)
    assert tray.messages == []
