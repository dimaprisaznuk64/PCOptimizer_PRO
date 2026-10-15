from __future__ import annotations

import math
import os
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from tempfile import NamedTemporaryFile


class BenchmarkError(Exception):
    pass


class BenchmarkType(Enum):
    CPU = auto()
    RAM = auto()
    DISK = auto()
    ALL = auto()


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    type: BenchmarkType
    score: float
    units: str
    duration_ms: int
    info: str = ""


class BenchmarkService:
    def __init__(
        self,
        *,
        now: Callable[[], float] | None = None,
        sleep: Callable[[float], None] | None = None,
    ) -> None:
        self._now = now or time.perf_counter
        self._sleep = sleep or time.sleep

    def run(self, btype: BenchmarkType, *, disk_path: Path | None = None) -> list[BenchmarkResult]:
        if btype == BenchmarkType.ALL:
            results: list[BenchmarkResult] = []
            results.extend(self.run(BenchmarkType.CPU))
            results.extend(self.run(BenchmarkType.RAM))
            results.extend(self.run(BenchmarkType.DISK, disk_path=disk_path))
            return results
        if btype == BenchmarkType.CPU:
            return [self._cpu()]
        if btype == BenchmarkType.RAM:
            return [self._ram()]
        if btype == BenchmarkType.DISK:
            return [self._disk(disk_path)]
        raise BenchmarkError(f"Unknown benchmark type: {btype}")

    def _cpu(self) -> BenchmarkResult:
        start = self._now()
        # Simple CPU workload: Mandelbrot-like iterations
        count = 0
        for i in range(1, 200000):
            count += math.isqrt(i * i + 1)
        duration_ms = int((self._now() - start) * 1000)
        # Score: higher = faster; scale roughly
        score = max(10.0, 300000.0 / max(1, duration_ms))
        return BenchmarkResult(
            type=BenchmarkType.CPU,
            score=round(score, 1),
            units="ops-like",
            duration_ms=duration_ms,
            info="Mandelbrot iterations",
        )

    def _ram(self) -> BenchmarkResult:
        start = self._now()
        data = bytearray(32 * 1024 * 1024)  # 32MB
        for i in range(0, len(data), 4096):
            data[i] = random.randint(0, 255)
        duration_ms = int((self._now() - start) * 1000)
        score = max(10.0, 4000.0 / max(1, duration_ms))
        return BenchmarkResult(
            type=BenchmarkType.RAM,
            score=round(score, 1),
            units="MB/s-like",
            duration_ms=duration_ms,
            info="32MB copy/loop",
        )

    def _disk(self, disk_path: Path | None) -> BenchmarkResult:
        path = disk_path or Path(tempfile_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        start = self._now()
        block = os.urandom(1024 * 1024)
        with open(path, "wb") as f:
            for _ in range(16):
                f.write(block)
            f.flush()
            os.fsync(f.fileno())
        size = path.stat().st_size
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        duration_ms = int((self._now() - start) * 1000)
        score = max(10.0, (size / 1024**2) / max(0.001, duration_ms / 1000.0))
        return BenchmarkResult(
            type=BenchmarkType.DISK,
            score=round(score, 1),
            units="MB/s",
            duration_ms=duration_ms,
            info=f"16MB write to {path}",
        )


def tempfile_path() -> str:
    tmp = NamedTemporaryFile(delete=False)
    try:
        return tmp.name
    finally:
        try:
            tmp.close()
        except OSError:
            pass
