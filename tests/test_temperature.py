from __future__ import annotations

from time import sleep, time

import pytest

from app.alerts.service import TEMP_CPU_C, TEMP_GPU_C
from app.history.service import HistorySample
from app.i18n import I18nService
from app.i18n.translations import TRANSLATIONS
from app.sensors.types import GpuStat, Snapshot, ThermalStat
from app.temperature import (
    GPU_WARN_C,
    SYSTEM_WARN_C,
    TemperatureService,
    classify,
    target_temperatures,
    thresholds,
)
from app.ui.temperature import TemperaturePage


class _History:
    def __init__(self, samples=(), error: str | None = None) -> None:
        self.samples = list(samples)
        self.error = error
        self.calls: list[float] = []

    def query(self, minutes: float) -> list[HistorySample]:
        self.calls.append(minutes)
        if self.error:
            raise RuntimeError(self.error)
        return self.samples


def _wait_until(qapp, condition, timeout: float = 8.0) -> bool:
    deadline = time() + timeout
    while time() < deadline:
        if condition():
            return True
        qapp.processEvents()
        sleep(0.02)
    return condition()


def _gpu(
    name: str = "RTX 3050 Ti",
    temperature: float | None = 68.0,
    hotspot: float | None = 74.0,
    stale: bool = False,
) -> GpuStat:
    return GpuStat(
        index=0 if not stale else 1,
        name=name,
        utilization=45.0,
        memory_used=2,
        memory_total=4,
        temperature=temperature,
        temperature_hotspot=hotspot,
        stale=stale,
        throttle_reasons=0,
    )


def _snapshot(
    thermal=(("zone0", 62.0), ("zone1", 73.0)),
    gpus=None,
    errors=None,
) -> Snapshot:
    if gpus is None:
        gpus = (_gpu(), _gpu(name="Sleeping iGPU", temperature=95.0, hotspot=99.0, stale=True))
    return Snapshot(
        ts=100.0,
        thermal=ThermalStat("wmi_acpi", tuple(thermal)),
        gpus=tuple(gpus),
        errors=errors or {},
    )


def _samples() -> list[HistorySample]:
    return [
        HistorySample(ts=100.0, temp_cpu=70.0, temp_gpu=60.0, gpu_hotspot=65.0),
        HistorySample(ts=200.0, temp_cpu=80.0, temp_gpu=70.0, gpu_hotspot=75.0),
    ]


def test_readings_from_snapshot_names_sources_honestly() -> None:
    report = TemperatureService().readings_from_snapshot(_snapshot())
    sources = [reading.source for reading in report.readings]
    assert len(sources) == 4
    assert any("wmi_acpi" in source and "System zone 0 (ACPI)" in source for source in sources)
    assert any("wmi_acpi" in source and "System zone 1 (ACPI)" in source for source in sources)
    assert any("RTX 3050 Ti core" in source for source in sources)
    assert any("RTX 3050 Ti hotspot" in source for source in sources)
    assert not any("Sleeping iGPU" in source for source in sources)
    assert not any("CPU package" in source for source in sources)


def test_classification_boundaries() -> None:
    assert classify(84.9, SYSTEM_WARN_C, TEMP_CPU_C) == "OK"
    assert classify(85.0, SYSTEM_WARN_C, TEMP_CPU_C) == "WARN"
    assert classify(89.9, SYSTEM_WARN_C, TEMP_CPU_C) == "WARN"
    assert classify(TEMP_CPU_C, SYSTEM_WARN_C, TEMP_CPU_C) == "DANGER"
    assert classify(79.9, GPU_WARN_C, TEMP_GPU_C) == "OK"
    assert classify(80.0, GPU_WARN_C, TEMP_GPU_C) == "WARN"
    assert classify(TEMP_GPU_C, GPU_WARN_C, TEMP_GPU_C) == "DANGER"

    snapshot = _snapshot(
        thermal=(("zone0", TEMP_CPU_C),),
        gpus=(_gpu(temperature=80.0, hotspot=TEMP_GPU_C),),
    )
    statuses = {reading.status for reading in TemperatureService().readings_from_snapshot(snapshot).readings}
    assert statuses == {"DANGER", "WARN"}


def test_missing_sources_are_not_invented() -> None:
    snapshot = Snapshot(ts=0.0, thermal=None, gpus=(), errors={"nvml": "offline"})
    report = TemperatureService().readings_from_snapshot(snapshot)
    assert report.readings == ()
    assert report.errors == ("nvml: offline",)


def test_from_history_uses_real_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(TRANSLATIONS["EN"], "temp_src_gpu_core", "GPU core")
    monkeypatch.setitem(TRANSLATIONS["EN"], "temp_src_gpu_hotspot", "GPU hotspot")
    history = _History(_samples())
    service = TemperatureService(history, now=lambda: 123.0)
    report = service.from_history(60.0)
    assert history.calls == [60.0]
    assert report.generated == 123.0
    assert len(report.readings) == 3

    system, core, hotspot = report.readings
    assert system.source == "wmi_acpi · System zone max (ACPI)"
    assert (system.current, system.peak, system.avg, system.min, system.max) == (
        80.0,
        80.0,
        75.0,
        70.0,
        80.0,
    )
    assert core.source == "nvml · GPU core"
    assert hotspot.source == "nvml · GPU hotspot"
    assert core.current == 70.0
    assert hotspot.peak == 75.0
    assert service.history_series(60.0)["system"] == [70.0, 80.0]


def test_history_failure_is_reported() -> None:
    service = TemperatureService(_History(error="boom"), now=lambda: 5.0)
    report = service.from_history(60.0)
    assert report.readings == ()
    assert report.errors == ("history: boom",)


def test_injected_selectors_are_used_for_missing_raw_data() -> None:
    service = TemperatureService(
        system_selector=lambda snapshot: (92.0, "custom-zone"),
        gpu_selector=lambda snapshot: (85.0, "custom-gpu"),
    )
    report = service.readings_from_snapshot(Snapshot(ts=0.0))
    assert [reading.source for reading in report.readings] == [
        "wmi_acpi · custom-zone",
        "nvml · custom-gpu",
    ]
    assert [reading.status for reading in report.readings] == ["DANGER", "WARN"]


def test_thresholds_match_alerts_and_health() -> None:
    assert thresholds() == {
        "system": (85.0, TEMP_CPU_C),
        "cpu": (85.0, TEMP_CPU_C),
        "board": (85.0, TEMP_CPU_C),
        "gpu": (80.0, TEMP_GPU_C),
        "hotspot": (80.0, TEMP_GPU_C),
    }
    assert TemperatureService().thresholds() == thresholds()


def test_target_temperatures_uses_explicit_sources_only() -> None:
    snapshot = _snapshot(
        thermal=(("zone0", 62.0), ("cpu", 78.0), ("board", 44.0)),
        gpus=(_gpu(temperature=68.0),),
    )
    targets = target_temperatures(snapshot)
    assert targets["cpu"] == (78.0, "CPU")
    assert targets["board"] == (44.0, "Motherboard")
    assert targets["gpu"] == (68.0, "RTX 3050 Ti core")


def test_target_temperatures_never_invents_missing_sources() -> None:
    targets = target_temperatures(_snapshot(thermal=(("zone0", 62.0),), gpus=()))
    assert targets == {"cpu": (None, ""), "board": (None, ""), "gpu": (None, "")}


def test_temperature_page_shows_cpu_board_gpu_summary(qapp) -> None:
    page = TemperaturePage(service=TemperatureService(now=lambda: 1.0))
    page.apply_snapshot(
        _snapshot(
            thermal=(("cpu", 78.0), ("board", 44.0)),
            gpus=(_gpu(temperature=68.0),),
        )
    )
    values = [label.text() for _title, label in page._target_labels.values()]
    assert values == ["78°C", "44°C", "68°C"]


def test_page_renders_live_snapshot(qapp) -> None:
    page = TemperaturePage(service=TemperatureService(now=lambda: 1.0))
    snapshot = _snapshot(
        thermal=(("zone0", 86.0), ("zone1", 61.0)),
        gpus=(_gpu(temperature=81.0, hotspot=88.0),),
    )
    page.apply_snapshot(snapshot)
    assert page.table.rowCount() == 4
    sources = [page.table.item(row, 0).text() for row in range(page.table.rowCount())]
    assert any("System zone 0 (ACPI)" in source for source in sources)
    assert not any("CPU package" in source for source in sources)
    assert page.system_card.value.text().startswith("86")
    assert page.gpu_card.value.text().startswith("81")
    assert page.hotspot_card.value.text().startswith("88")
    assert page.clock_card.value.text()
    assert page.errors.isHidden()


def test_page_empty_state(qapp) -> None:
    page = TemperaturePage()
    page.apply_snapshot(Snapshot(ts=0.0))
    assert page.table.rowCount() == 0
    assert page.system_card.value.text() == "—"
    assert page.gpu_card.value.text() == "—"
    assert page.errors.isHidden()


def test_range_switch_loads_history(qapp) -> None:
    history = _History(_samples())
    page = TemperaturePage(history=history)
    assert page.range_combo.count() == 4
    page.range_combo.setCurrentIndex(2)
    assert _wait_until(qapp, lambda: page._task is None and page.table.rowCount() > 0)
    assert history.calls == [1440.0]
    sources = [page.table.item(row, 0).text() for row in range(page.table.rowCount())]
    assert any("System zone max (ACPI)" in source for source in sources)
    assert any("hotspot" in source.lower() for source in sources)


def test_refresh_button_loads_history(qapp) -> None:
    history = _History(_samples())
    page = TemperaturePage(history=history)
    page.refresh_button.click()
    assert _wait_until(qapp, lambda: page._task is None and page.table.rowCount() > 0)
    assert history.calls == [360.0]


def test_threshold_legend_shows_limits(qapp) -> None:
    page = TemperaturePage()
    text = page._legend.text()
    assert "85/90" in text
    assert "80/87" in text


def test_retranslate_updates_headers_and_rerenders(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(TRANSLATIONS["EN"], "temp_col_source", "Source EN")
    monkeypatch.setitem(TRANSLATIONS["UA"], "temp_col_source", "Джерело UA")
    page = TemperaturePage(service=TemperatureService(now=lambda: 1.0))
    page.apply_snapshot(_snapshot(thermal=(("zone0", 72.0),), gpus=(_gpu(),)))
    assert page.table.horizontalHeaderItem(0).text() == "Source EN"

    I18nService.instance().set_language("UA")
    try:
        page.retranslate()
        assert page.table.horizontalHeaderItem(0).text() == "Джерело UA"
        assert "Системна зона 0 (ACPI)" in page.table.item(0, 0).text()
        assert "85/90" in page._legend.text()
    finally:
        I18nService.instance().set_language("EN")


def test_invalidate_cache_allows_refreshed_history() -> None:
    history = _History(_samples())
    service = TemperatureService(history, now=lambda: 1.0)
    first = service.from_history(60.0)
    assert first.readings[0].current == 80.0

    history.samples = [HistorySample(ts=300.0, temp_cpu=95.0)]
    assert service.from_history(60.0).readings[0].current == 80.0
    service.invalidate_cache()
    refreshed = service.from_history(60.0)
    assert refreshed.readings[0].current == 95.0
    assert refreshed.readings[0].status == "DANGER"


def test_refresh_button_invalidates_service_cache(qapp, monkeypatch: pytest.MonkeyPatch) -> None:
    service = TemperatureService(_History(_samples()), now=lambda: 1.0)
    calls: list[int] = []
    original = service.invalidate_cache

    def tracked() -> None:
        calls.append(1)
        original()

    monkeypatch.setattr(service, "invalidate_cache", tracked)
    page = TemperaturePage(service=service)
    page.refresh_button.click()
    assert _wait_until(qapp, lambda: page._task is None and page.table.rowCount() > 0)
    assert calls == [1]


def test_live_readings_accumulate_honest_session_stats() -> None:
    service = TemperatureService(now=lambda: 1.0)
    cold = _snapshot(
        thermal=(("zone0", 50.0),),
        gpus=(_gpu(temperature=60.0, hotspot=65.0),),
    )
    hot = _snapshot(
        thermal=(("zone0", 70.0),),
        gpus=(_gpu(temperature=58.0, hotspot=64.0),),
    )
    service.readings_from_snapshot(cold)
    service.readings_from_snapshot(hot)
    report = service.readings_from_snapshot(hot, record=False)

    zone = next(r for r in report.readings if r.kind == "system")
    core = next(r for r in report.readings if r.kind == "gpu")
    hotspot = next(r for r in report.readings if r.kind == "hotspot")
    assert (zone.current, zone.peak, zone.avg, zone.min, zone.max) == (
        70.0,
        70.0,
        60.0,
        50.0,
        70.0,
    )
    assert (core.current, core.peak, core.avg, core.min, core.max) == (
        58.0,
        60.0,
        59.0,
        58.0,
        60.0,
    )
    assert (hotspot.current, hotspot.peak, hotspot.avg, hotspot.min, hotspot.max) == (
        64.0,
        65.0,
        64.5,
        64.0,
        65.0,
    )


def test_retranslate_preserves_session_peaks(qapp) -> None:
    service = TemperatureService(now=lambda: 1.0)
    page = TemperaturePage(service=service)
    page.apply_snapshot(_snapshot(thermal=(("zone0", 60.0),), gpus=()))
    page.apply_snapshot(_snapshot(thermal=(("zone0", 85.0),), gpus=()))
    assert page.table.item(0, 2).text() == "85°C"

    I18nService.instance().set_language("UA")
    try:
        page.retranslate()
        assert page.table.item(0, 2).text() == "85°C"
    finally:
        I18nService.instance().set_language("EN")


def test_kind_field_identifies_hotspot_without_localized_text(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(TRANSLATIONS["UA"], "temp_src_gpu_core", "Ядро")
    monkeypatch.setitem(TRANSLATIONS["UA"], "temp_src_gpu_hotspot", "Точка нагріву")
    report = TemperatureService(now=lambda: 1.0).readings_from_snapshot(
        _snapshot(thermal=(), gpus=(_gpu(temperature=61.0, hotspot=79.0),))
    )
    assert [(reading.kind, reading.current) for reading in report.readings] == [
        ("gpu", 61.0),
        ("hotspot", 79.0),
    ]

    page = TemperaturePage(history=_History(_samples()))
    I18nService.instance().set_language("UA")
    try:
        page.refresh_button.click()
        assert _wait_until(qapp, lambda: page._task is None and page.table.rowCount() > 0)
        assert page.gpu_card.value.text() == "70°C"
        assert page.hotspot_card.value.text() == "75°C"
    finally:
        I18nService.instance().set_language("EN")
