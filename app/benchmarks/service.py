from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from statistics import median


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
    metric: str
    value: float
    unit: str
    duration_ms: int
    runs: int = 1
    detail: str = ""


_MB = 1024 * 1024


class BenchmarkService:
    """Honest, repeatable micro-benchmarks using real workloads.

    * CPU  — SHA-256 hashing throughput (single thread + all cores), MB/s.
    * RAM  — ``memcpy`` copy bandwidth of a real buffer, GB/s.
    * Disk — sequential write (with fsync) and read throughput, MB/s.

    Sizes are configurable so tests can run tiny workloads. Warm-up passes are
    discarded and every metric is the median of several timed runs.
    """

    def __init__(
        self,
        *,
        now: Callable[[], float] | None = None,
        cpu_bytes: int = 8 * _MB,
        ram_bytes: int = 128 * _MB,
        disk_bytes: int = 64 * _MB,
        runs: int = 3,
        disk_runs: int = 2,
        workers: int | None = None,
    ) -> None:
        self._now = now or time.perf_counter
        self.cpu_bytes = max(1, cpu_bytes)
        self.ram_bytes = max(1, ram_bytes)
        self.disk_bytes = max(1, disk_bytes)
        self.runs = max(1, runs)
        self.disk_runs = max(1, disk_runs)
        self._workers = workers

    def run(self, btype: BenchmarkType, *, disk_path: Path | None = None) -> list[BenchmarkResult]:
        if btype == BenchmarkType.ALL:
            results: list[BenchmarkResult] = []
            results.extend(self._cpu())
            results.extend(self._ram())
            results.extend(self._disk(disk_path))
            return results
        if btype == BenchmarkType.CPU:
            return self._cpu()
        if btype == BenchmarkType.RAM:
            return self._ram()
        if btype == BenchmarkType.DISK:
            return self._disk(disk_path)
        raise BenchmarkError(f"Unknown benchmark type: {btype}")

    # ---------- helpers ----------

    def _workers_count(self) -> int:
        return max(1, self._workers or (os.cpu_count() or 1))

    def _measure(self, work: Callable[[], int], runs: int | None = None) -> tuple[float, int, int]:
        """Run *work* (returns bytes processed per call) several times.

        Performs one discarded warm-up run, then returns the median throughput
        (bytes/s), median duration (ms) and the number of timed runs.
        """
        count = runs if runs is not None else self.runs
        work()  # warm-up
        rates: list[float] = []
        durations: list[float] = []
        for _ in range(count):
            start = self._now()
            processed = work()
            elapsed = self._now() - start
            if elapsed > 0 and processed:
                rates.append(processed / elapsed)
                durations.append(elapsed)
        if not rates:
            return 0.0, 0, 0
        return median(rates), int(median(durations) * 1000), len(rates)

    @staticmethod
    def _sha256(data: bytes) -> None:
        hashlib.sha256(data).digest()

    # ---------- cpu ----------

    def _cpu(self) -> list[BenchmarkResult]:
        buf = os.urandom(self.cpu_bytes)

        def single() -> int:
            self._sha256(buf)
            return len(buf)

        rate, duration_ms, runs = self._measure(single)

        workers = self._workers_count()
        step = len(buf) // workers + 1
        chunks = [buf[i * step : (i + 1) * step] for i in range(workers)]
        chunks = [chunk for chunk in chunks if chunk]

        def hash_chunk(chunk: bytes) -> int:
            hashlib.sha256(chunk).digest()
            return len(chunk)

        pool = ThreadPoolExecutor(max_workers=workers)

        def multi() -> int:
            return sum(pool.map(hash_chunk, chunks))

        try:
            multi_rate, multi_ms, multi_runs = self._measure(multi)
        finally:
            pool.shutdown()

        return [
            BenchmarkResult(
                type=BenchmarkType.CPU,
                metric="cpu_single",
                value=round(rate / 1e6, 1),
                unit="MB/s",
                duration_ms=duration_ms,
                runs=runs,
                detail="SHA-256 · 1 thread",
            ),
            BenchmarkResult(
                type=BenchmarkType.CPU,
                metric="cpu_multi",
                value=round(multi_rate / 1e6, 1),
                unit="MB/s",
                duration_ms=multi_ms,
                runs=multi_runs,
                detail=f"SHA-256 · {workers} threads",
            ),
        ]

    # ---------- ram ----------

    def _ram(self) -> list[BenchmarkResult]:
        src = bytes(self.ram_bytes)
        dst = bytearray(self.ram_bytes)

        def copy() -> int:
            dst[:] = src
            return len(src)

        rate, duration_ms, runs = self._measure(copy)
        return [
            BenchmarkResult(
                type=BenchmarkType.RAM,
                metric="ram_copy",
                value=round(rate / 1e9, 2),
                unit="GB/s",
                duration_ms=duration_ms,
                runs=runs,
                detail=f"memcpy · {self.ram_bytes // _MB} MB",
            )
        ]

    # ---------- disk ----------

    def _disk(self, disk_path: Path | None) -> list[BenchmarkResult]:
        path = Path(disk_path) if disk_path else _temp_bin_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        block = os.urandom(_MB)
        blocks = max(1, self.disk_bytes // _MB)

        def write() -> int:
            with open(path, "wb") as handle:
                for _ in range(blocks):
                    handle.write(block)
                handle.flush()
                os.fsync(handle.fileno())
            return blocks * _MB

        write_rate, write_ms, write_runs = self._measure(write, self.disk_runs)

        def read() -> int:
            total = 0
            with open(path, "rb") as handle:
                while True:
                    chunk = handle.read(4 * _MB)
                    if not chunk:
                        break
                    total += len(chunk)
            return total

        read_rate, read_ms, read_runs = self._measure(read, self.disk_runs)

        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

        size_mb = blocks
        return [
            BenchmarkResult(
                type=BenchmarkType.DISK,
                metric="disk_write",
                value=round(write_rate / 1e6, 1),
                unit="MB/s",
                duration_ms=write_ms,
                runs=write_runs,
                detail=f"seq write · {size_mb} MB · fsync",
            ),
            BenchmarkResult(
                type=BenchmarkType.DISK,
                metric="disk_read",
                value=round(read_rate / 1e6, 1),
                unit="MB/s",
                duration_ms=read_ms,
                runs=read_runs,
                detail=f"seq read · {size_mb} MB",
            ),
        ]


def _temp_bin_path() -> Path:
    from tempfile import gettempdir

    return Path(gettempdir()) / "pcoptimizer_bench.bin"
