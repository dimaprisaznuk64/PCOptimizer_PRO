"""Tests for monitoring frequency profiles."""

from __future__ import annotations

from types import SimpleNamespace

from app.history import PerformanceHistory
from app.monitor.profiles import DEFAULT_PROFILE, PROFILE_KEYS, profile_for
from app.ui.sampler import SensorSampler


def test_profiles_cover_three_frequencies() -> None:
    assert PROFILE_KEYS == ("ECO", "BALANCED", "PERFORMANCE")
    eco, balanced, fast = (profile_for(key) for key in PROFILE_KEYS)
    assert eco.sample_interval_ms > balanced.sample_interval_ms > fast.sample_interval_ms
    assert eco.history_interval_s > balanced.history_interval_s > fast.history_interval_s
    assert eco.process_refresh_ms > balanced.process_refresh_ms > fast.process_refresh_ms
    assert eco.game_presence_s > balanced.game_presence_s > fast.game_presence_s


def test_profile_for_falls_back_to_balanced() -> None:
    assert profile_for(" performance ").key == "PERFORMANCE"
    assert profile_for("unknown").key == DEFAULT_PROFILE
    assert profile_for(None).key == DEFAULT_PROFILE


def test_history_interval_is_configurable(tmp_path) -> None:
    now = [100.0]
    snapshot = SimpleNamespace(cpu=None, memory=None, gpus=(), thermal=None)
    history = PerformanceHistory(store=tmp_path / "h.jsonl", now=lambda: now[0], interval_s=10.0)
    assert history.record(snapshot) is True
    now[0] = 105.0
    assert history.record(snapshot) is False
    history.set_interval_s(4.0)
    assert history.record(snapshot) is True


def test_sampler_interval_can_change_at_runtime() -> None:
    sampler = SensorSampler(object(), interval_ms=1000)
    assert sampler.interval_ms == 1000
    sampler.set_interval_ms(250)
    assert sampler.interval_ms == 250
    sampler.set_interval_ms(10)
    assert sampler.interval_ms == 50


def test_settings_page_selects_profile_and_applies_it_live(qapp, tmp_path) -> None:
    from app.settings import SettingsService
    from app.ui.settings import SettingsPage

    applied: list[tuple[str, int]] = []
    service = SettingsService(tmp_path / "settings.json")
    page = SettingsPage(
        service,
        log_directory=tmp_path / "logs",
        on_monitor_profile_applied=lambda key, ms: applied.append((key, ms)),
    )
    assert page.profile_combo.count() == 3
    page.profile_combo.setCurrentIndex(2)
    assert page.interval_combo.currentData() == 500
    page.save()
    assert service.get("monitor_profile") == "PERFORMANCE"
    assert applied[-1] == ("PERFORMANCE", 500)


def test_main_window_applies_profile_to_runtime_services(qapp, tmp_path) -> None:
    from app.settings import SettingsService
    from app.ui.main_window import MainWindow

    settings = SettingsService(tmp_path / "settings.json")
    settings.set("monitor_profile", "ECO")
    settings.set("sample_interval_ms", 2000)
    settings.save()
    window = MainWindow(settings=settings)
    try:
        assert window._history.interval_s == 60.0
        assert window.page("monitor")._proc_timer.interval() == 10_000

        class _Sampler:
            def __init__(self) -> None:
                self.interval_ms = 0

            def set_interval_ms(self, value: int) -> None:
                self.interval_ms = value

            def stop(self, timeout_ms: int = 100) -> bool:
                return True

        sampler = _Sampler()
        window.sampler = sampler
        window.apply_monitor_profile("PERFORMANCE", 500)
        assert sampler.interval_ms == 500
        assert window._history.interval_s == 10.0
        assert window.page("monitor")._proc_timer.interval() == 2_000
    finally:
        window.close()
