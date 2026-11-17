from __future__ import annotations

from app.alerts import (
    TemperatureAlertMonitor,
    UsageAlert,
    UsageAlertMonitor,
    max_cpu_thermal,
    max_cpu_usage,
    max_disk_usage,
    max_gpu_thermal,
    max_memory_usage,
    max_thermal,
)
from app.sensors import CpuStat, DiskStat, GpuStat, MemoryStat, Snapshot, ThermalStat


def _snap(thermal=(), gpus=(), ts: float = 0.0) -> Snapshot:
    return Snapshot(
        ts=ts,
        thermal=ThermalStat(source="test", temperatures=tuple(thermal)) if thermal else None,
        gpus=tuple(gpus),
    )


def _usage_snap(
    cpu: float | None = 42.0,
    ram: float | None = 60.0,
    disks: tuple[float, ...] = (50.0,),
) -> Snapshot:
    return Snapshot(
        ts=0.0,
        cpu=(
            CpuStat(percent=cpu, per_core=(cpu,), physical_cores=1, logical_cores=1)
            if cpu is not None
            else None
        ),
        memory=(
            MemoryStat(
                total=100,
                used=int(ram),
                available=100 - int(ram),
                percent=ram,
                swap_total=0,
                swap_used=0,
                swap_percent=0.0,
            )
            if ram is not None
            else None
        ),
        disks=tuple(
            DiskStat(f"{i}:\\", f"{i}:\\", "NTFS", 100, int(p), 100 - int(p), p)
            for i, p in enumerate(disks)
        ),
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


def test_usage_selectors_read_cpu_ram_and_fullest_disk() -> None:
    snap = _usage_snap(cpu=95.0, ram=88.0, disks=(60.0, 97.0, 80.0))
    assert max_cpu_usage(snap) == (95.0, "CPU")
    assert max_memory_usage(snap) == (88.0, "RAM")
    assert max_disk_usage(snap) == (97.0, "1:\\")


def test_usage_selectors_tolerate_missing_sensors() -> None:
    snap = _usage_snap(cpu=None, ram=None, disks=())
    assert max_cpu_usage(snap) is None
    assert max_memory_usage(snap) is None
    assert max_disk_usage(snap) is None


def test_usage_monitor_rising_edge_cooldown_and_rearm() -> None:
    now = [0.0]
    monitor = UsageAlertMonitor(
        kind="cpu", reading=max_cpu_usage, cooldown_s=300.0, clock=lambda: now[0]
    )
    hot = _usage_snap(cpu=95.0)
    assert monitor.check(hot, 90.0) == UsageAlert(95.0, "CPU", 90.0, "cpu")
    now[0] = 100.0
    assert monitor.check(hot, 90.0) is None
    assert monitor.check(_usage_snap(cpu=50.0), 90.0) is None
    now[0] = 500.0
    assert monitor.check(hot, 90.0) == UsageAlert(95.0, "CPU", 90.0, "cpu")


def test_main_window_alerts_on_high_cpu_and_ram(qapp) -> None:
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(
        data={
            "temp_alerts_enabled": False,
            "usage_alerts_enabled": True,
            "alert_cpu_percent": 90,
            "alert_ram_percent": 90,
            "alert_disk_percent": 99,
        }
    )
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    window.handle_snapshot(_usage_snap(cpu=97.0, ram=95.0))
    assert len(tray.messages) == 2
    bodies = " ".join(body for _, body in tray.messages)
    assert "CPU" in bodies
    assert "RAM" in bodies


def test_main_window_alerts_on_full_disk(qapp) -> None:
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(
        data={
            "temp_alerts_enabled": False,
            "usage_alerts_enabled": True,
            "alert_cpu_percent": 99,
            "alert_ram_percent": 99,
            "alert_disk_percent": 90,
        }
    )
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    window.handle_snapshot(_usage_snap(disks=(85.0, 98.0)))
    assert len(tray.messages) == 1
    assert "98%" in tray.messages[0][1]


def test_main_window_respects_disabled_usage_alerts(qapp) -> None:
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(data={"usage_alerts_enabled": False})
    window = MainWindow(settings=settings)
    tray = _StubTray()
    window.tray = tray
    window.handle_snapshot(_usage_snap(cpu=99.0, ram=99.0, disks=(99.0,)))
    assert tray.messages == []
