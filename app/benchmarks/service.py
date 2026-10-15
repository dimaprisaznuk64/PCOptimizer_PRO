from __future__ import annotations

import ctypes
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
_READ_CHUNK = _MB


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
        cpu_bytes: int = 16 * _MB,
        ram_bytes: int = 128 * _MB,
        disk_bytes: int = 256 * _MB,
        runs: int = 5,
        disk_runs: int = 5,
        target_ms: int = 400,
        max_repeats: int = 20000,
        workers: int | None = None,
    ) -> None:
        self._now = now or time.perf_counter
        self.cpu_bytes = max(1, cpu_bytes)
        self.ram_bytes = max(1, ram_bytes)
        self.disk_bytes = max(1, disk_bytes)
        self.runs = max(1, runs)
        self.disk_runs = max(1, disk_runs)
        # Each timed run is calibrated (via repetition) to last at least this
        # long, so sub-millisecond workloads do not produce noisy numbers.
        self._target_s = max(0.0, target_ms / 1000)
        self._max_repeats = max(1, max_repeats)
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

        The first call doubles as a warm-up and a calibration probe: the call
        is repeated inside every timed block just enough times to reach
        ``target_ms`` (bounded by ``max_repeats``). Returns the median
        throughput (bytes/s), the median block duration (ms) and the number of
        timed runs.
        """
        count = runs if runs is not None else self.runs
        start = self._now()
        processed = work()
        first = self._now() - start
        repeats = 1
        if self._target_s > 0 and first > 0 and processed:
            repeats = max(1, min(self._max_repeats, int(self._target_s / first) + 1))

        # The warm-up call is slower than the steady state, so the first
        # estimate usually undershoots. Run one discarded probe block and
        # scale the repeat count to actually reach the target duration.
        if self._target_s > 0:
            start = self._now()
            total = 0
            for _ in range(repeats):
                total += work()
            elapsed = self._now() - start
            if elapsed > 0 and elapsed < self._target_s and repeats < self._max_repeats:
                scaled = int(repeats * (self._target_s / elapsed)) + 1
                repeats = max(repeats + 1, min(self._max_repeats, scaled))

        rates: list[float] = []
        durations: list[float] = []
        for _ in range(count):
            start = self._now()
            total = 0
            for _ in range(repeats):
                total += work()
            elapsed = self._now() - start
            if elapsed > 0 and total:
                rates.append(total / elapsed)
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
        # Python-level ``dst[:] = src`` holds the GIL, so it cannot saturate
        # memory bandwidth. ``ctypes.memmove`` releases the GIL, which lets a
        # thread pool copy several slices in parallel for a realistic figure.
        workers = self._workers_count()
        size = self.ram_bytes
        src = ctypes.create_string_buffer(size)
        dst = ctypes.create_string_buffer(size)
        src_ptr = ctypes.cast(src, ctypes.c_void_p).value or 0
        dst_ptr = ctypes.cast(dst, ctypes.c_void_p).value or 0

        step = size // workers
        slices: list[tuple[int, int]] = []
        for index in range(workers):
            offset = index * step
            length = step if index < workers - 1 else size - offset
            if length > 0:
                slices.append((offset, length))
        if not slices:
            slices = [(0, size)]

        def copy_slice(region: tuple[int, int]) -> int:
            offset, length = region
            ctypes.memmove(dst_ptr + offset, src_ptr + offset, length)
            return length

        pool = ThreadPoolExecutor(max_workers=workers)

        def copy() -> int:
            return sum(pool.map(copy_slice, slices))

        try:
            rate, duration_ms, runs = self._measure(copy)
        finally:
            pool.shutdown()

        return [
            BenchmarkResult(
                type=BenchmarkType.RAM,
                metric="ram_copy",
                value=round(rate / 1e9, 2),
                unit="GB/s",
                duration_ms=duration_ms,
                runs=runs,
                detail=f"memcpy · {self.ram_bytes // _MB} MB · {len(slices)} threads",
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

        # A freshly written file is served straight from the OS cache, so a
        # plain read reports far more than the disk can actually deliver. Read
        # with FILE_FLAG_NO_BUFFERING to bypass the cache; fall back to a
        # buffered read (and say so) if the filesystem refuses.
        mode = "unbuffered"

        def read() -> int:
            nonlocal mode
            if mode == "unbuffered":
                try:
                    return _read_unbuffered(path)
                except Exception:
                    mode = "cached"
            return _read_buffered(path)

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
                detail=f"seq read · {size_mb} MB · {mode}",
            ),
        ]


def _read_buffered(path: Path) -> int:
    """Plain sequential read, served from the OS cache when available."""
    total = 0
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_READ_CHUNK)
            if not chunk:
                break
            total += len(chunk)
    return total


def _read_unbuffered(path: Path) -> int:
    """Sequential read that bypasses the OS cache (FILE_FLAG_NO_BUFFERING).

    Uses the raw Win32 API via ctypes because the buffer must be sector
    aligned; ``VirtualAlloc`` returns page-aligned memory that satisfies both
    the alignment and the sector-size multiple requirements.
    """
    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    create_file = kernel32.CreateFileW
    create_file.restype = wintypes.HANDLE
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    read_file = kernel32.ReadFile
    read_file.restype = wintypes.BOOL
    read_file.argtypes = [
        wintypes.HANDLE,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        ctypes.c_void_p,
    ]
    virtual_alloc = kernel32.VirtualAlloc
    virtual_alloc.restype = ctypes.c_void_p
    virtual_alloc.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD]
    virtual_free = kernel32.VirtualFree
    virtual_free.argtypes = [ctypes.c_void_p, ctypes.c_size_t, wintypes.DWORD]
    close_handle = kernel32.CloseHandle

    generic_read = 0x80000000
    file_share_read = 0x00000001
    open_existing = 3
    file_flag_no_buffering = 0x20000000
    mem_commit_reserve = 0x1000 | 0x2000
    mem_release = 0x8000
    page_readwrite = 0x04

    handle = create_file(
        str(path),
        generic_read,
        file_share_read,
        None,
        open_existing,
        file_flag_no_buffering,
        None,
    )
    if handle is None or handle == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_last_error(), f"CreateFile failed: {path}")

    buffer = virtual_alloc(None, _READ_CHUNK, mem_commit_reserve, page_readwrite)
    if not buffer:
        error = ctypes.get_last_error()
        close_handle(handle)
        raise OSError(error, "VirtualAlloc failed")

    total = 0
    read = wintypes.DWORD(0)
    try:
        while True:
            if not read_file(handle, buffer, _READ_CHUNK, ctypes.byref(read), None):
                raise OSError(ctypes.get_last_error(), "ReadFile failed")
            if read.value == 0:
                break
            total += read.value
    finally:
        virtual_free(buffer, 0, mem_release)
        close_handle(handle)
    return total


def _temp_bin_path() -> Path:
    from tempfile import gettempdir

    return Path(gettempdir()) / "pcoptimizer_bench.bin"
