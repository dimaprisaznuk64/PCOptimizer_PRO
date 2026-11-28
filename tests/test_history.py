from __future__ import annotations

import json
import time
from types import SimpleNamespace

import pytest

from app.history import (
    HistorySample,
    PerformanceHistory,
    downsample,
    stats,
    top_process_summary,
)
from app.ui.history import HistoryPage


class FakeSnapshot:
    """Minimal snapshot mimicking app.sensors.types.Snapshot for record()."""

    def __init__(
        self,
        cpu_pct: float | None = 42.0,
        ram_pct: float | None = 55.0,
        gpu_util: float | None = 10.0,
        gpu_mem_used: int = 1_000,
        gpu_mem_total: int = 4_000,
        gpu_temp: float | None = 60.0,
        thermal_max: float | None = 55.0,
        gpu_hotspot: float | None = 72.0,
        gpu_mem_clock: float | None = 7000.0,
        gpu_power: float | None = 45.0,
        gpu_throttling: bool = False,
        commit_used: int | None = None,
        commit_limit: int | None = None,
    ) -> None:
        self.cpu = type("C", (), {"percent": cpu_pct})() if cpu_pct is not None else None
        memory_values = {"percent": ram_pct, "commit_used": commit_used, "commit_limit": commit_limit}
        self.memory = type("M", (), memory_values)() if ram_pct is not None else None
        if gpu_util is not None:
            gpu = type(
                "G",
                (),
                {
                    "utilization": gpu_util,
                    "memory_used": gpu_mem_used,
                    "memory_total": gpu_mem_total,
                    "temperature": gpu_temp,
                    "temperature_hotspot": gpu_hotspot,
                    "memory_clock_mhz": gpu_mem_clock,
                    "power_w": gpu_power,
                    "throttling": gpu_throttling,
                },
            )()
            self.gpus: tuple = (gpu,)
        else:
            self.gpus = ()
        if thermal_max is not None:
            self.thermal = type("T", (), {"temperatures": (("zone0", thermal_max),)})()
        else:
            self.thermal = None


# ---------- HistorySample ----------


def test_sample_roundtrip():
    s = HistorySample(
        ts=100.0,
        cpu=42.0,
        ram=55.0,
        gpu=10.0,
        gpu_mem=25.0,
        temp_cpu=60.0,
        temp_gpu=70.0,
        gpu_hotspot=82.0,
        gpu_mem_clock=7000.0,
        gpu_power=45.0,
        gpu_throttling=True,
        commit_percent=80.0,
    )
    d = s.to_dict()
    back = HistorySample.from_dict(d)
    assert back == s


def test_sample_from_dict_bad():
    assert HistorySample.from_dict({}) is None
    assert HistorySample.from_dict({"ts": "not-a-number"}) is None


def test_sample_none_fields():
    s = HistorySample(ts=1.0)
    d = s.to_dict()
    assert d["cpu"] is None
    assert HistorySample.from_dict(d) == s


def test_sample_from_legacy_dict_defaults_new_fields():
    s = HistorySample.from_dict({"ts": 1.0, "cpu": 50.0})
    assert s is not None
    assert s.gpu_hotspot is None
    assert s.commit_percent is None
    assert s.gpu_throttling is None
    assert s.top_processes == ()


def test_sample_top_processes_roundtrip():
    s = HistorySample(ts=1.0, top_processes=(("chrome.exe", 1200.5), ("python.exe", 300.0)))
    back = HistorySample.from_dict(s.to_dict())
    assert back == s
    legacy = HistorySample.from_dict({"ts": 1.0, "top_processes": [["bad"], ["x", -1]]})
    assert legacy is not None
    assert legacy.top_processes == ()


# ---------- PerformanceHistory.record / query ----------


def test_record_and_query(tmp_path):
    store = tmp_path / "h.jsonl"
    t = [1000.0]

    def now():
        return t[0]

    h = PerformanceHistory(store=store, now=now)
    assert h.record(FakeSnapshot()) is True
    t[0] = 1031.0  # >30s later
    assert h.record(FakeSnapshot(cpu_pct=80.0)) is True

    samples = h.query(minutes=60.0)
    assert len(samples) == 2
    assert samples[0].cpu == 42.0
    assert samples[1].cpu == 80.0


def test_record_throttled(tmp_path):
    store = tmp_path / "h.jsonl"
    t = [1000.0]
    h = PerformanceHistory(store=store, now=lambda: t[0])
    assert h.record(FakeSnapshot()) is True
    t[0] = 1010.0  # only 10s later
    assert h.record(FakeSnapshot()) is False


def test_failed_append_is_not_throttled(tmp_path, monkeypatch):
    t = [1000.0]
    h = PerformanceHistory(store=tmp_path / "h.jsonl", now=lambda: t[0])
    calls: list[float] = []

    def append(sample):
        calls.append(sample.ts)
        return len(calls) > 1

    monkeypatch.setattr(h, "_append", append)

    assert h.record(FakeSnapshot()) is False
    t[0] = 1001.0
    assert h.record(FakeSnapshot()) is True
    assert calls == [1000.0, 1001.0]


def test_append_returns_false_on_disk_error(tmp_path, monkeypatch):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")

    def fail_open(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("builtins.open", fail_open)

    assert h.record(FakeSnapshot()) is False


def test_query_filters_old(tmp_path):
    store = tmp_path / "h.jsonl"
    t = [10000.0]
    h = PerformanceHistory(store=store, now=lambda: t[0])
    h.record(FakeSnapshot())
    t[0] = 10000.0 + 7200.0  # 2h later
    h.record(FakeSnapshot())
    # query only last 60 min -> only the 2nd sample
    samples = h.query(minutes=60.0)
    assert len(samples) == 1
    assert samples[0].ts == 17200.0


def test_query_empty(tmp_path):
    h = PerformanceHistory(store=tmp_path / "nope.jsonl")
    assert h.query(60.0) == []


def test_clear(tmp_path):
    store = tmp_path / "h.jsonl"
    h = PerformanceHistory(store=store)
    h.record(FakeSnapshot())
    assert store.exists()
    h.clear()
    assert not store.exists()


def test_record_extracts_fields(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    h.record(FakeSnapshot(cpu_pct=33.0, ram_pct=44.0, gpu_util=50.0, gpu_temp=77.0, thermal_max=65.0))
    samples = h.query(1.0)
    assert len(samples) == 1
    s = samples[0]
    assert s.cpu == 33.0
    assert s.ram == 44.0
    assert s.gpu == 50.0
    assert s.gpu_mem == pytest.approx(25.0)
    assert s.temp_gpu == 77.0
    assert s.temp_cpu is None


def test_record_extracts_advanced_telemetry(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    h.record(
        FakeSnapshot(
            gpu_hotspot=88.0,
            gpu_mem_clock=7500.0,
            gpu_power=55.0,
            gpu_throttling=True,
            commit_used=80,
            commit_limit=100,
        )
    )
    s = h.query(1.0)[0]
    assert s.gpu_hotspot == 88.0
    assert s.gpu_mem_clock == 7500.0
    assert s.gpu_power == 55.0
    assert s.gpu_throttling is True
    assert s.commit_percent == pytest.approx(80.0)


def test_record_captures_top_processes(tmp_path):
    rows = [
        SimpleNamespace(name="chrome.exe", memory_bytes=1024 * 1024 * 800),
        SimpleNamespace(name="python.exe", memory_bytes=1024 * 1024 * 250),
    ]
    h = PerformanceHistory(store=tmp_path / "h.jsonl", process_top=lambda: rows)
    assert h.record(FakeSnapshot()) is True
    sample = h.query(1.0)[0]
    assert sample.top_processes == (("chrome.exe", 800.0), ("python.exe", 250.0))


def test_record_survives_process_scan_failure(tmp_path):
    def broken():
        raise RuntimeError("access denied")

    h = PerformanceHistory(store=tmp_path / "h.jsonl", process_top=broken)
    assert h.record(FakeSnapshot()) is True
    assert h.query(1.0)[0].top_processes == ()


def test_record_no_gpu_no_thermal(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    h.record(FakeSnapshot(gpu_util=None, thermal_max=None))
    s = h.query(1.0)[0]
    assert s.gpu is None
    assert s.temp_cpu is None
    assert s.temp_gpu is None


def test_record_temp_cpu_ignores_non_cpu_thermal_sources(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    snap = FakeSnapshot(gpu_util=None, thermal_max=None)
    snap.thermal = type(
        "T",
        (),
        {
            "temperatures": (
                ("GPU Hot Spot", 82.0),
                ("Motherboard", 45.0),
                ("CPU Package", 60.0),
                ("System", 50.0),
            )
        },
    )()
    h.record(snap)
    assert h.query(1.0)[0].temp_cpu == pytest.approx(60.0)


def test_record_temp_cpu_none_when_only_non_cpu_thermal(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    snap = FakeSnapshot(gpu_util=None, thermal_max=None)
    snap.thermal = type("T", (), {"temperatures": (("GPU Hot Spot", 82.0), ("Board", 45.0))})()
    h.record(snap)
    assert h.query(1.0)[0].temp_cpu is None


def test_skips_corrupt_lines(tmp_path):
    store = tmp_path / "h.jsonl"
    good = HistorySample(ts=time.time(), cpu=50.0).to_dict()
    store.write_text("not json\n" + json.dumps(good) + "\n{}\n", encoding="utf-8")
    h = PerformanceHistory(store=store)
    samples = h.query(10000.0)
    assert len(samples) == 1
    assert samples[0].cpu == 50.0


def test_max_age_trims_on_read(tmp_path):
    store = tmp_path / "h.jsonl"
    now = time.time()
    lines = [
        json.dumps(HistorySample(ts=now - 7200, cpu=1.0).to_dict()),
        json.dumps(HistorySample(ts=now - 100, cpu=2.0).to_dict()),
    ]
    store.write_text("\n".join(lines) + "\n", encoding="utf-8")
    h = PerformanceHistory(store=store, max_age_hours=1.0)
    samples = h.query(minutes=10000)
    assert len(samples) == 1
    assert samples[0].cpu == 2.0
    # A trimmed read must also rewrite the store so the file cannot grow forever.
    kept = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(kept) == 1
    assert kept[0]["cpu"] == 2.0


def test_periodic_compaction_rewrites_store(tmp_path):
    store = tmp_path / "h.jsonl"
    now = 10_000.0
    store.write_text(json.dumps(HistorySample(ts=now - 7200, cpu=1.0).to_dict()) + "\n", encoding="utf-8")
    h = PerformanceHistory(store=store, max_age_hours=1.0, now=lambda: now)
    h._append_count = 119
    assert h.record(FakeSnapshot(cpu_pct=2.0)) is True
    lines = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["cpu"] == 2.0


def test_history_page_shows_7d_range_and_advanced_cards(qapp, tmp_path) -> None:
    store = tmp_path / "h.jsonl"
    now = time.time()
    samples = [
        HistorySample(
            ts=now - 60,
            cpu=40.0,
            ram=50.0,
            gpu=30.0,
            temp_cpu=60.0,
            gpu_hotspot=80.0,
            commit_percent=70.0,
        ),
        HistorySample(
            ts=now,
            cpu=60.0,
            ram=70.0,
            gpu=50.0,
            temp_cpu=70.0,
            gpu_hotspot=90.0,
            commit_percent=90.0,
        ),
    ]
    store.write_text("\n".join(json.dumps(s.to_dict()) for s in samples) + "\n", encoding="utf-8")
    page = HistoryPage(PerformanceHistory(store=store))
    assert "hist_range_7d" in page._range_buttons
    assert page._range_buttons["hist_range_7d"].text() == "7 days"
    assert page._commit_card.value.text() == "80%"
    assert page._hotspot_card.value.text() == "85°C"


def test_history_page_defers_query_until_first_show(qapp) -> None:
    class _CountingHistory:
        def __init__(self) -> None:
            self.calls = 0

        def query(self, _minutes: float) -> list[HistorySample]:
            self.calls += 1
            return []

    history = _CountingHistory()
    page = HistoryPage(history, defer_load=True)
    page.retranslate()  # language changes must not query the hidden page
    assert history.calls == 0
    page.ensure_loaded()
    assert history.calls == 1
    page.ensure_loaded()
    assert history.calls == 1
    page._set_range(60.0, "hist_range_1h")
    assert history.calls == 2


def test_top_process_summary_latest_peak_and_counts():
    samples = [
        HistorySample(ts=1.0, top_processes=(("a.exe", 100.0), ("gone.exe", 50.0))),
        HistorySample(ts=2.0, top_processes=(("a.exe", 180.0), ("b.exe", 90.0))),
        HistorySample(ts=3.0, top_processes=(("a.exe", 120.0), ("b.exe", 200.0))),
    ]
    rows = top_process_summary(samples)
    assert rows[0] == ("a.exe", 120.0, 180.0, 3)
    assert rows[1] == ("b.exe", 200.0, 200.0, 2)
    assert ("gone.exe", None, 50.0, 1) in rows


def test_history_page_renders_top_process_history(qapp, tmp_path):
    store = tmp_path / "h.jsonl"
    now = time.time()
    samples = [
        HistorySample(ts=now - 60, top_processes=(("a.exe", 100.0),)),
        HistorySample(ts=now, top_processes=(("a.exe", 150.0), ("b.exe", 90.0))),
    ]
    store.write_text("\n".join(json.dumps(s.to_dict()) for s in samples) + "\n", encoding="utf-8")
    page = HistoryPage(PerformanceHistory(store=store))
    assert page.proc_table.rowCount() == 2
    assert page.proc_table.item(0, 0).text() == "a.exe"
    assert page.proc_table.item(0, 1).text() == "150 MB"
    assert page.proc_table.item(0, 2).text() == "150 MB"
    assert page.proc_table.item(0, 3).text() == "2"


# ---------- downsample ----------


def test_downsample_small_list():
    data = [HistorySample(ts=float(i), cpu=float(i)) for i in range(5)]
    assert downsample(data, 120) == data


def test_downsample_reduces():
    data = [HistorySample(ts=float(i), cpu=float(i)) for i in range(1000)]
    out = downsample(data, 120)
    assert len(out) == 120
    assert out[0].ts == 0.0
    assert out[-1].ts == 999.0


def test_downsample_target_too_small():
    data = [HistorySample(ts=float(i)) for i in range(10)]
    assert downsample(data, 1) == data


# ---------- stats ----------


def test_stats_basic():
    data = [
        HistorySample(ts=0, cpu=10.0),
        HistorySample(ts=1, cpu=20.0),
        HistorySample(ts=2, cpu=30.0),
    ]
    lo, avg, hi = stats(data, "cpu")
    assert lo == 10.0
    assert avg == 20.0
    assert hi == 30.0


def test_stats_none():
    data = [HistorySample(ts=0), HistorySample(ts=1)]
    assert stats(data, "cpu") is None


def test_stats_mixed_none():
    data = [
        HistorySample(ts=0, cpu=10.0),
        HistorySample(ts=1, cpu=None),
        HistorySample(ts=2, cpu=30.0),
    ]
    lo, avg, hi = stats(data, "cpu")
    assert lo == 10.0
    assert avg == 20.0
    assert hi == 30.0


# ---------- MainWindow integration ----------


def test_main_window_records_history(qapp, tmp_path, monkeypatch):
    monkeypatch.setenv("PCOPTIMIZER_DATA", str(tmp_path))
    from app.ui.main_window import MainWindow

    window = MainWindow()
    try:
        assert window._history is not None
        assert window._history.store == tmp_path / "performance_history.jsonl"
        assert window._history._process_top is not None
    finally:
        window.shutdown()
        window.deleteLater()
