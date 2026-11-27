from __future__ import annotations

import csv
import io
import json
import math
import os
import time
from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from app.sensors.temperature_names import KIND_BOARD, KIND_SYSTEM, temperature_kind
from app.settings import data_root

SESSION_COMPARE_METRICS = ("cpu", "ram", "gpu", "gpu_temp", "fps")
LATEST_TAIL_BYTES = 128 * 1024


@dataclass(frozen=True, slots=True)
class FrameSample:
    ts: float
    frametime_ms: float
    fps: float
    source: str = ""


@dataclass(frozen=True, slots=True)
class ResourceMetrics:
    cpu_percent: float | None = None
    ram_percent: float | None = None
    gpu_percent: float | None = None
    gpu_temp: float | None = None
    gpu_hotspot: float | None = None
    system_temp: float | None = None
    commit_percent: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        return {
            "cpu_percent": self.cpu_percent,
            "ram_percent": self.ram_percent,
            "gpu_percent": self.gpu_percent,
            "gpu_temp": self.gpu_temp,
            "gpu_hotspot": self.gpu_hotspot,
            "system_temp": self.system_temp,
            "commit_percent": self.commit_percent,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> ResourceMetrics:
        if not isinstance(d, dict):
            return cls()
        return cls(
            cpu_percent=d.get("cpu_percent"),
            ram_percent=d.get("ram_percent"),
            gpu_percent=d.get("gpu_percent"),
            gpu_temp=d.get("gpu_temp"),
            gpu_hotspot=d.get("gpu_hotspot"),
            system_temp=d.get("system_temp"),
            commit_percent=d.get("commit_percent"),
        )


@dataclass(frozen=True, slots=True)
class FrameStats:
    fps_avg: float = 0.0
    frametime_avg: float = 0.0
    low_1: float | None = None
    low_01: float | None = None
    samples: int = 0
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "fps_avg": self.fps_avg,
            "frametime_avg": self.frametime_avg,
            "low_1": self.low_1,
            "low_01": self.low_01,
            "samples": self.samples,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> FrameStats:
        if not isinstance(d, dict):
            return cls()
        return cls(
            fps_avg=float(d.get("fps_avg") or 0.0),
            frametime_avg=float(d.get("frametime_avg") or 0.0),
            low_1=d.get("low_1"),
            low_01=d.get("low_01"),
            samples=int(d.get("samples") or 0),
            source=str(d.get("source") or ""),
        )


@dataclass(frozen=True, slots=True)
class GameSession:
    game_id: str
    game_name: str
    profile: str
    started: float
    ended: float = 0.0
    before: ResourceMetrics = ResourceMetrics()
    after: ResourceMetrics = ResourceMetrics()
    stats: FrameStats = FrameStats()
    frames_count: int = 0

    def to_dict(self) -> dict:
        return {
            "game_id": self.game_id,
            "game_name": self.game_name,
            "profile": self.profile,
            "started": self.started,
            "ended": self.ended,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "stats": self.stats.to_dict(),
            "frames_count": self.frames_count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> GameSession | None:
        try:
            return cls(
                game_id=str(d["game_id"]),
                game_name=str(d.get("game_name") or d["game_id"]),
                profile=str(d.get("profile") or "GAMING"),
                started=float(d["started"]),
                ended=float(d.get("ended") or 0.0),
                before=ResourceMetrics.from_dict(d.get("before")),
                after=ResourceMetrics.from_dict(d.get("after")),
                stats=FrameStats.from_dict(d.get("stats")),
                frames_count=int(d.get("frames_count") or 0),
            )
        except (KeyError, TypeError, ValueError):
            return None


class FrameProvider(ABC):
    @abstractmethod
    def source_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def available(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read_frames(self) -> list[FrameSample]:
        raise NotImplementedError

    def latest_frame(self) -> FrameSample | None:
        frames = self.read_frames()
        return frames[-1] if frames else None

    def read_new_frames(self, since_ts: float = -math.inf) -> list[FrameSample]:
        return [frame for frame in self.read_frames() if frame.ts > since_ts]


class CsvFrameProvider(FrameProvider):
    def __init__(self, path: str | Path | None = None, source: str = "PresentMon CSV") -> None:
        self.path = Path(path) if path else None
        self.source = source

    def source_name(self) -> str:
        return self.source

    @property
    def available(self) -> bool:
        return self.path is not None and self.path.is_file()

    def _frame(self, row: dict[str, str], index: int = 0) -> FrameSample | None:
        frametime = _first_float(
            row,
            ("MsBetweenPresents", "msBetweenPresents", "FrameTime", "FrameTime(ms)", "FrameTimeMS"),
        )
        if frametime is None or frametime <= 0:
            return None
        ts = _first_float(
            row,
            (
                "CPUStartTime",
                "CPUStartQPCTime",
                "CPUStartQPC",
                "Time",
                "Timestamp",
                "FrameNumber",
                "PresentTime",
            ),
        )
        return FrameSample(
            ts=ts if ts is not None else float(index),
            frametime_ms=frametime,
            fps=1000.0 / frametime,
            source=self.source,
        )

    def read_frames(self) -> list[FrameSample]:
        if not self.available or self.path is None:
            return []
        try:
            with open(self.path, encoding="utf-8-sig", newline="") as f:
                rows = list(csv.DictReader(f))
        except (OSError, UnicodeError, csv.Error):
            return []
        frames: list[FrameSample] = []
        for index, row in enumerate(rows):
            frame = self._frame(row, index)
            if frame is not None:
                frames.append(frame)
        return frames

    def _tail_frames(self) -> list[FrameSample]:
        if not self.available or self.path is None:
            return []
        try:
            with open(self.path, "rb") as f:
                header = f.readline()
                size = os.fstat(f.fileno()).st_size
                if size <= len(header):
                    return []
                tail_size = min(size - len(header), LATEST_TAIL_BYTES)
                f.seek(size - tail_size)
                tail = f.read(tail_size)
        except OSError:
            return []
        if not header.endswith(b"\n"):
            header += b"\n"
        text = (header + tail).decode("utf-8-sig", errors="replace")
        try:
            rows = list(csv.DictReader(io.StringIO(text)))
        except csv.Error:
            return []
        frames: list[FrameSample] = []
        for index, row in enumerate(rows):
            frame = self._frame(row, index)
            if frame is not None:
                frames.append(frame)
        return frames

    def latest_frame(self) -> FrameSample | None:
        frames = self._tail_frames()
        return frames[-1] if frames else None

    def read_new_frames(self, since_ts: float = -math.inf) -> list[FrameSample]:
        return [frame for frame in self._tail_frames() if frame.ts > since_ts]


class StaticFrameProvider(FrameProvider):
    def __init__(self, frames: Sequence[FrameSample], source: str = "mock") -> None:
        self._frames = list(frames)
        self._source = source

    def source_name(self) -> str:
        return self._source

    @property
    def available(self) -> bool:
        return bool(self._frames)

    def read_frames(self) -> list[FrameSample]:
        return list(self._frames)

    def latest_frame(self) -> FrameSample | None:
        return self._frames[-1] if self._frames else None


def default_frame_provider(path: str | Path | None = None) -> FrameProvider:
    raw = str(path) if path else ""
    if not raw:
        raw = os.environ.get("PCOPTIMIZER_PRESENTMON_CSV") or ""
    return CsvFrameProvider(raw) if raw else CsvFrameProvider()


def resource_metrics(snapshot) -> ResourceMetrics:
    cpu = snapshot.cpu.percent if snapshot.cpu else None
    ram = snapshot.memory.percent if snapshot.memory else None
    commit_percent = None
    if (
        snapshot.memory
        and getattr(snapshot.memory, "commit_limit", None)
        and getattr(snapshot.memory, "commit_used", None) is not None
    ):
        commit_percent = snapshot.memory.commit_used / snapshot.memory.commit_limit * 100.0
    system_temp = None
    if snapshot.thermal and snapshot.thermal.temperatures:
        values = [
            value
            for name, value in snapshot.thermal.temperatures
            if temperature_kind(name) in (KIND_BOARD, KIND_SYSTEM)
        ]
        if values:
            system_temp = max(values)
    gpu_percent = gpu_temp = gpu_hotspot = None
    if snapshot.gpus:
        gpu = snapshot.gpus[0]
        gpu_percent = getattr(gpu, "utilization", None)
        gpu_temp = getattr(gpu, "temperature", None)
        gpu_hotspot = getattr(gpu, "temperature_hotspot", None)
    return ResourceMetrics(
        cpu_percent=cpu,
        ram_percent=ram,
        gpu_percent=gpu_percent,
        gpu_temp=gpu_temp,
        gpu_hotspot=gpu_hotspot,
        system_temp=system_temp,
        commit_percent=commit_percent,
    )


def session_metric_value(session: GameSession, metric: str, phase: str) -> float | None:
    if metric == "fps":
        if phase != "after" or not session.stats.samples:
            return None
        return session.stats.fps_avg
    values = session.before if phase == "before" else session.after
    if metric == "cpu":
        return values.cpu_percent
    if metric == "ram":
        return values.ram_percent
    if metric == "gpu":
        return values.gpu_percent
    if metric == "gpu_temp":
        return values.gpu_temp
    return None


def session_metric_unit(metric: str) -> str:
    if metric == "gpu_temp":
        return "°C"
    if metric == "fps":
        return ""
    return "%"


def frame_stats(frames: Sequence[FrameSample]) -> FrameStats:
    values = sorted(f.frametime_ms for f in frames if f.frametime_ms > 0)
    if not values:
        return FrameStats()
    avg_ms = sum(values) / len(values)
    source = next((f.source for f in frames if f.source), "")
    return FrameStats(
        fps_avg=1000.0 / avg_ms,
        frametime_avg=avg_ms,
        low_1=1000.0 / _percentile(values, 0.99),
        low_01=1000.0 / _percentile(values, 0.999),
        samples=len(values),
        source=source,
    )


class GamingTelemetryService:
    def __init__(
        self,
        provider: FrameProvider | None = None,
        store: str | Path | None = None,
        now: Callable[[], float] | None = None,
        max_sessions: int = 50,
    ) -> None:
        self.provider = provider or default_frame_provider()
        self.store = Path(store) if store else data_root() / "gaming_sessions.jsonl"
        self._now = now or time.time
        self._max_sessions = max_sessions
        self._session: GameSession | None = None
        self._frames: list[FrameSample] = []
        self._last_ts = -math.inf

    @property
    def session(self) -> GameSession | None:
        return self._session

    @property
    def active(self) -> bool:
        return self._session is not None

    @property
    def source_name(self) -> str:
        return self.provider.source_name()

    @property
    def available(self) -> bool:
        return self.provider.available

    def start_session(self, game_id: str, game_name: str, profile: str, snapshot=None) -> GameSession:
        if self._session is not None:
            raise ValueError("a telemetry session is already running")
        self._frames = []
        self._last_ts = -math.inf
        self._session = GameSession(
            game_id=game_id,
            game_name=game_name,
            profile=profile,
            started=self._now(),
            before=resource_metrics(snapshot),
            after=resource_metrics(snapshot),
            stats=FrameStats(source=self.source_name),
        )
        return self._session

    def poll(self, snapshot=None) -> GameSession | None:
        if self._session is None:
            return None
        if snapshot is not None:
            self._session = replace(self._session, after=resource_metrics(snapshot))
        for frame in self.provider.read_frames():
            if frame.ts > self._last_ts:
                self._frames.append(frame)
                self._last_ts = frame.ts
        stats = frame_stats(self._frames)
        if not stats.source:
            stats = replace(stats, source=self.source_name)
        self._session = replace(self._session, stats=stats, frames_count=len(self._frames))
        return self._session

    def finish_session(self) -> GameSession | None:
        if self._session is None:
            return None
        session = replace(
            self._session,
            ended=self._now(),
            stats=frame_stats(self._frames),
            frames_count=len(self._frames),
        )
        if not session.stats.source:
            session = replace(session, stats=replace(session.stats, source=self.source_name))
        self._append(session)
        self._session = None
        self._frames = []
        self._last_ts = -math.inf
        return session

    def sessions(self, limit: int = 10) -> list[GameSession]:
        if not self.store.exists():
            return []
        try:
            lines = self.store.read_text(encoding="utf-8").splitlines()
        except OSError:
            return []
        result: list[GameSession] = []
        for line in reversed(lines):
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(data, dict):
                session = GameSession.from_dict(data)
                if session is not None:
                    result.append(session)
            if limit and len(result) >= limit:
                break
        return result

    def _append(self, session: GameSession) -> None:
        try:
            self.store.parent.mkdir(parents=True, exist_ok=True)
            with open(self.store, "a", encoding="utf-8") as f:
                f.write(json.dumps(session.to_dict()) + "\n")
            stored = self.sessions(limit=0)
            if len(stored) > self._max_sessions:
                tmp = self.store.with_suffix(".tmp")
                with open(tmp, "w", encoding="utf-8") as f:
                    for item in stored[: self._max_sessions]:
                        f.write(json.dumps(item.to_dict()) + "\n")
                tmp.replace(self.store)
        except OSError:
            return


def _first_float(row: dict, keys: Sequence[str]) -> float | None:
    lowered = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    index = max(0, min(len(sorted_values) - 1, math.floor(q * len(sorted_values))))
    return sorted_values[index]
