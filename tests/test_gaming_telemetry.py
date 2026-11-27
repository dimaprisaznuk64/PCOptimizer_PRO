from __future__ import annotations

import time
from types import SimpleNamespace

from app.gaming import (
    CsvFrameProvider,
    DetectedGame,
    FrameSample,
    FrameStats,
    GameSession,
    GamingService,
    GamingTelemetryService,
    ResourceMetrics,
    StaticFrameProvider,
    default_frame_provider,
    frame_stats,
    resource_metrics,
    session_metric_unit,
    session_metric_value,
)
from app.optimizer import ApplyReport, OptimizerService
from app.ui.gaming import GamingPage


def _wait_until(qapp, cond, timeout: float = 5.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _snapshot() -> SimpleNamespace:
    return SimpleNamespace(
        cpu=SimpleNamespace(percent=40.0),
        memory=SimpleNamespace(percent=60.0, commit_used=80, commit_limit=100),
        thermal=SimpleNamespace(temperatures=(("zone0", 66.0),)),
        gpus=(
            SimpleNamespace(
                utilization=55.0,
                temperature=70.0,
                temperature_hotspot=81.0,
            ),
        ),
    )


def test_frame_stats_percentiles() -> None:
    frames = [FrameSample(ts=float(i), frametime_ms=10.0, fps=100.0) for i in range(100)]
    frames[-1] = FrameSample(ts=99.0, frametime_ms=100.0, fps=10.0)
    stats = frame_stats(frames)
    assert stats.fps_avg == 1000 / 10.9
    assert stats.low_1 == 10.0
    assert stats.low_01 == 10.0
    assert stats.samples == 100


def test_csv_provider_parses_presentmon_columns(tmp_path) -> None:
    path = tmp_path / "frames.csv"
    path.write_text(
        "Time,msBetweenPresents\n1.0,16.7\n2.0,33.4\nbad,nope\n",
        encoding="utf-8",
    )
    provider = CsvFrameProvider(path)
    assert provider.available is True
    frames = provider.read_frames()
    assert len(frames) == 2
    assert frames[0].frametime_ms == 16.7
    assert frames[1].fps == 1000 / 33.4


def test_csv_provider_parses_presentmon_2x_headers(tmp_path) -> None:
    path = tmp_path / "presentmon.csv"
    path.write_text(
        "Application,ProcessID,CPUStartTime,MsBetweenPresents,MsGPUTime\n"
        "Game.exe,123,1.0,16.7,12.0\n"
        "Game.exe,123,2.0,8.0,7.0\n",
        encoding="utf-8",
    )
    provider = CsvFrameProvider(path)
    frames = provider.read_frames()
    assert [(frame.ts, frame.frametime_ms) for frame in frames] == [(1.0, 16.7), (2.0, 8.0)]
    assert frames[1].fps == 125.0


def test_csv_provider_without_path_is_unavailable(tmp_path) -> None:
    provider = CsvFrameProvider()
    assert provider.available is False
    assert provider.read_frames() == []


def test_csv_provider_latest_frame_reads_only_tail(tmp_path) -> None:
    path = tmp_path / "frames.csv"
    rows = "1.0,16.7\n" * 18000
    path.write_text("Time,msBetweenPresents\n" + rows + "999.0,8.0\n", encoding="utf-8")
    provider = CsvFrameProvider(path)
    frame = provider.latest_frame()
    assert frame is not None
    assert frame.fps == 125.0
    assert frame.ts == 999.0


def test_csv_provider_read_new_frames_only_returns_later_timestamps(tmp_path) -> None:
    path = tmp_path / "frames.csv"
    path.write_text("Time,msBetweenPresents\n1.0,16.7\n2.0,8.0\n", encoding="utf-8")
    provider = CsvFrameProvider(path)
    frames = provider.read_new_frames(1.0)
    assert [frame.ts for frame in frames] == [2.0]


def test_default_frame_provider_prefers_explicit_path_and_falls_back_to_env(tmp_path, monkeypatch) -> None:
    explicit = tmp_path / "explicit.csv"
    env_csv = tmp_path / "env.csv"
    explicit.write_text("Time,msBetweenPresents\n1,16.7\n", encoding="utf-8")
    env_csv.write_text("Time,msBetweenPresents\n1,8.0\n", encoding="utf-8")
    monkeypatch.setenv("PCOPTIMIZER_PRESENTMON_CSV", str(env_csv))
    assert default_frame_provider(explicit).path == explicit
    assert default_frame_provider(None).path == env_csv
    assert default_frame_provider("").path == env_csv


def test_resource_metrics_reads_advanced_snapshot() -> None:
    metrics = resource_metrics(_snapshot())
    assert metrics.cpu_percent == 40.0
    assert metrics.ram_percent == 60.0
    assert metrics.gpu_percent == 55.0
    assert metrics.gpu_hotspot == 81.0
    assert metrics.system_temp == 66.0
    assert metrics.commit_percent == 80.0


def test_resource_metrics_system_temp_excludes_gpu_sensor() -> None:
    snapshot = _snapshot()
    snapshot.thermal.temperatures = (("board", 44.0), ("gpu", 86.0))
    metrics = resource_metrics(snapshot)
    assert metrics.system_temp == 44.0
    assert metrics.gpu_temp == 70.0


def test_session_metric_value_and_unit() -> None:
    session = GameSession(
        game_id="pubg",
        game_name="PUBG",
        profile="GAMING",
        started=1.0,
        before=ResourceMetrics(cpu_percent=50.0, gpu_temp=70.0),
        after=ResourceMetrics(cpu_percent=40.0, gpu_temp=76.0),
        stats=FrameStats(fps_avg=120.0, samples=10),
    )
    assert session_metric_value(session, "cpu", "before") == 50.0
    assert session_metric_value(session, "cpu", "after") == 40.0
    assert session_metric_value(session, "gpu_temp", "after") == 76.0
    assert session_metric_value(session, "fps", "before") is None
    assert session_metric_value(session, "fps", "after") == 120.0
    assert session_metric_unit("cpu") == "%"
    assert session_metric_unit("gpu_temp") == "°C"
    assert session_metric_unit("fps") == ""


def test_telemetry_session_lifecycle_and_history(tmp_path) -> None:
    frames = [FrameSample(ts=float(i), frametime_ms=20.0, fps=50.0, source="mock") for i in range(3)]
    service = GamingTelemetryService(
        provider=StaticFrameProvider(frames),
        store=tmp_path / "sessions.jsonl",
        now=lambda: 1000.0,
    )
    session = service.start_session("pubg", "PUBG", "GAMING", _snapshot())
    assert session.before == ResourceMetrics(
        cpu_percent=40.0,
        ram_percent=60.0,
        gpu_percent=55.0,
        gpu_temp=70.0,
        gpu_hotspot=81.0,
        system_temp=66.0,
        commit_percent=80.0,
    )
    service.poll(_snapshot())
    service.poll()
    assert service.session is not None
    assert service.session.frames_count == 3
    finished = service.finish_session()
    assert finished is not None
    assert finished.ended == 1000.0
    assert finished.stats.fps_avg == 50.0
    assert finished.frames_count == 3
    stored = service.sessions()
    assert len(stored) == 1
    assert stored[0].game_name == "PUBG"
    assert stored[0].stats.low_1 == 50.0


class _CannedGamingService(GamingService):
    def __init__(self, tmp_path) -> None:
        super().__init__(
            steam_roots=lambda: [],
            custom_store=tmp_path / "custom.json",
            profile_store=tmp_path / "profiles.json",
            mode_store=tmp_path / "mode.json",
            optimizer=OptimizerService(backup_path=tmp_path / "opt.json"),
            running_names=lambda: [],
        )
        self.games = [
            DetectedGame(
                id="pubg",
                name="PUBG: BATTLEGROUNDS",
                source="Steam",
                location=str(tmp_path / "TslGame.exe"),
                installed=True,
                running=False,
            )
        ]

    def detect(self):
        return list(self.games)

    def activate(self, *, with_restore_point: bool = True, profile: str = "GAMING") -> ApplyReport:
        self._active = True
        return ApplyReport(applied=("x",), errors=())


def test_gaming_page_session_buttons_and_snapshot(qapp, tmp_path) -> None:
    frames = [FrameSample(ts=float(i), frametime_ms=10.0, fps=100.0, source="mock") for i in range(5)]
    telemetry = GamingTelemetryService(
        provider=StaticFrameProvider(frames),
        store=tmp_path / "sessions.jsonl",
    )
    page = GamingPage(service=_CannedGamingService(tmp_path), telemetry=telemetry)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)
    page.table.selectRow(0)
    page.apply_snapshot(_snapshot())

    page.start_telemetry_session()
    assert telemetry.active is True
    assert page.session_stop_button.isEnabled()
    assert _wait_until(qapp, lambda: telemetry.session is not None and telemetry.session.frames_count == 5)
    assert "FPS 100" in page.telemetry_values.text()
    assert "CPU 40%" in page.telemetry_resources.text()

    page.stop_telemetry_session()
    assert telemetry.active is False
    assert page.session_history.rowCount() == 1
    assert page.session_history.item(0, 1).text() == "PUBG: BATTLEGROUNDS"
    assert len(page._compare_sessions) == 1
    assert not page.compare_chart.grab().isNull()
    assert "Average change" in page.compare_summary.text()
    fps_index = page.compare_metric_combo.findData("fps")
    page.compare_metric_combo.setCurrentIndex(fps_index)
    assert page.compare_chart._metric == "fps"
    assert page.compare_summary.text() == "Record sessions with before/after readings to see a delta"
