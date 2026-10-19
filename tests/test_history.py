from __future__ import annotations

import json
import time

import pytest

from app.history import HistorySample, PerformanceHistory, downsample, stats


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
    ) -> None:
        self.cpu = type("C", (), {"percent": cpu_pct})() if cpu_pct is not None else None
        self.memory = type("M", (), {"percent": ram_pct})() if ram_pct is not None else None
        if gpu_util is not None:
            gpu = type(
                "G",
                (),
                {
                    "utilization": gpu_util,
                    "memory_used": gpu_mem_used,
                    "memory_total": gpu_mem_total,
                    "temperature": gpu_temp,
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
    s = HistorySample(ts=100.0, cpu=42.0, ram=55.0, gpu=10.0, gpu_mem=25.0, temp_cpu=60.0, temp_gpu=70.0)
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
    assert s.temp_cpu == 65.0


def test_record_no_gpu_no_thermal(tmp_path):
    h = PerformanceHistory(store=tmp_path / "h.jsonl")
    h.record(FakeSnapshot(gpu_util=None, thermal_max=None))
    s = h.query(1.0)[0]
    assert s.gpu is None
    assert s.temp_cpu is None
    assert s.temp_gpu is None


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
    finally:
        window.shutdown()
        window.deleteLater()
