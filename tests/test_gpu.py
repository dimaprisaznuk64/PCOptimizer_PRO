from __future__ import annotations

from app.sensors import GpuStat, MockBackend, SensorManager
from app.sensors.types import Snapshot
from app.ui.gpu import GpuPage
from app.ui.main_window import MainWindow


def _snapshot(gpus: tuple[GpuStat, ...], errors: dict[str, str] | None = None) -> Snapshot:
    return Snapshot(ts=0.0, gpus=gpus, errors=errors or {})


def test_gpu_page_from_mock(qapp) -> None:
    page = GpuPage()
    page.apply_snapshot(SensorManager([MockBackend()]).snapshot())
    assert len(page._panels) == 1
    panel = page._panels[0]
    assert "Mock GPU 3050" in panel.name.text()
    assert panel.util.value.text() == "25%"
    assert panel.vram.value.text() == "2.0GB"
    assert panel.vram.bar._percent == 50.0
    assert panel.temp.value.text() == "55C"
    assert panel.power.value.text() == "45W"
    assert panel.power.bar._percent == 45.0 / 80.0 * 100.0
    assert "fan 60%" in panel.info.text()
    assert "clock 1500MHz" in panel.info.text()
    assert "power limit 80W" in panel.info.text()
    assert page.errors.isHidden()
    assert page.empty.isHidden()


def test_gpu_page_shows_n_a_for_missing_values(qapp) -> None:
    page = GpuPage()
    g = GpuStat(index=0, name="Laptop GPU", utilization=10.0, memory_used=1, memory_total=2)
    page.apply_snapshot(_snapshot((g,)))
    panel = page._panels[0]
    assert "fan n/a" in panel.info.text()
    assert panel.temp.value.text() == "—"
    assert panel.power.value.text() == "—"
    assert panel.power.bar._percent == 0.0


def test_gpu_page_without_gpu_shows_reason(qapp) -> None:
    page = GpuPage()
    page.apply_snapshot(_snapshot((), {"nvml": "NVML init failed"}))
    assert page._panels == []
    assert not page.empty.isHidden()
    assert "NVML init failed" in page.empty.text()
    # the placeholder already explains the error, so the bottom error line stays hidden
    assert page.errors.isHidden()


def test_gpu_page_handles_multiple_gpus(qapp) -> None:
    page = GpuPage()
    first = GpuStat(index=0, name="GPU A", utilization=1.0, memory_used=1, memory_total=2)
    second = GpuStat(index=1, name="GPU B", utilization=2.0, memory_used=3, memory_total=4)
    page.apply_snapshot(_snapshot((second, first)))
    assert len(page._panels) == 2
    assert "GPU A" in page._panels[0].name.text()
    assert "GPU B" in page._panels[1].name.text()
    page.apply_snapshot(_snapshot((first,)))
    assert len(page._panels) == 1


def test_main_window_broadcast_reaches_gpu_page(qapp) -> None:
    window = MainWindow()
    window.show_page("gpu")
    window.handle_snapshot(SensorManager([MockBackend(gpu_percent=77.0)]).snapshot())
    gpu_page = window.stack.widget(window._index_by_key["gpu"])
    assert gpu_page._panels[0].util.value.text() == "77%"
    window.close()
