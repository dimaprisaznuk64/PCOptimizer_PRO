from __future__ import annotations

import ctypes
import math
import os
import struct
import time
from collections.abc import Callable

from .temperature_names import (
    KIND_BOARD,
    KIND_CPU,
    KIND_DISK,
    KIND_GPU,
    KIND_HOTSPOT,
    KIND_SYSTEM,
    raw_temperature_kind,
    temperature_priority,
)

_MAP_NAME = "Global\\HWiNFO_SENS_SM2"
_MUTEX_NAME = "Global\\HWiNFO_SM2_MUTEX"
_FILE_MAP_READ = 0x0004
_SYNCHRONIZE = 0x00100000
_WAIT_TIMEOUT_MS = 250
_SIGNATURE = int.from_bytes(b"HWiS", "little")
_HEADER = struct.Struct("<IIIqIIIIII")
_TEMP_READING = 1
_MAX_BYTES = 16 * 1024 * 1024
_KINDS = (KIND_CPU, KIND_BOARD, KIND_GPU, KIND_HOTSPOT, KIND_SYSTEM, KIND_DISK)
# HWiNFO refreshes shared memory every poll (1-2 s by default). If the stamp is
# older than this, HWiNFO is frozen or stopped writing: do not show stale values.
_STALE_AFTER_S = 120.0
_MIN_SANE_EPOCH = 1_500_000_000


def _cstr(data: bytes, offset: int, size: int) -> str:
    if offset < 0 or offset + size > len(data):
        return ""
    raw = data[offset : offset + size].split(b"\x00", 1)[0]
    return raw.decode("utf-8", "replace").strip()


def parse_hwinfo_bytes(data: bytes) -> dict[str, tuple[float, str]]:
    if len(data) < _HEADER.size:
        raise ValueError("HWiNFO shared memory is too small")
    (
        signature,
        _version,
        _revision,
        _poll_time,
        sensor_offset,
        sensor_size,
        sensor_count,
        reading_offset,
        reading_size,
        reading_count,
    ) = _HEADER.unpack_from(data, 0)
    if signature != _SIGNATURE:
        raise ValueError("HWiNFO shared memory signature is not live")
    if not (0 < sensor_count <= 4096 and 0 < reading_count <= 16384):
        raise ValueError("HWiNFO shared memory has invalid counts")
    if sensor_size < 0x108 or reading_size < 0x13C:
        raise ValueError("HWiNFO shared memory has invalid element sizes")
    sensor_end = sensor_offset + sensor_size * sensor_count
    reading_end = reading_offset + reading_size * reading_count
    if sensor_offset < _HEADER.size or reading_offset < _HEADER.size:
        raise ValueError("HWiNFO shared memory has invalid offsets")
    if max(sensor_end, reading_end) > min(len(data), _MAX_BYTES):
        raise ValueError("HWiNFO shared memory is truncated")

    sensors: list[str] = []
    for index in range(sensor_count):
        base = sensor_offset + index * sensor_size
        name = _cstr(data, base + 0x08, 128) or _cstr(data, base + 0x88, 128)
        sensors.append(name or f"sensor{index}")

    best: dict[str, tuple[int, float, str]] = {}
    for index in range(reading_count):
        base = reading_offset + index * reading_size
        (reading_type,) = struct.unpack_from("<I", data, base)
        if reading_type != _TEMP_READING:
            continue
        (sensor_index,) = struct.unpack_from("<I", data, base + 0x04)
        if sensor_index >= len(sensors):
            continue
        label = _cstr(data, base + 0x0C, 128) or _cstr(data, base + 0x8C, 128)
        (value,) = struct.unpack_from("<d", data, base + 0x11C)
        if not math.isfinite(value) or value <= 0.0:
            continue
        parent = sensors[sensor_index]
        raw = f"{parent} {label}".strip()
        kind = raw_temperature_kind(raw)
        if kind not in _KINDS:
            continue
        score = temperature_priority(raw, kind)
        current = best.get(kind)
        if current is None or (score, value) > (current[0], current[1]):
            best[kind] = (score, float(value), raw)
    return {kind: (entry[1], f"hwinfo · {entry[2]}") for kind, entry in best.items()}


def hwinfo_poll_age(data: bytes, now: float | None = None) -> float | None:
    """Seconds since HWiNFO last polled its sensors, or None when unknown.

    The header carries the last polling time as a Unix timestamp. A zero or
    implausible stamp is treated as "unknown" so valid data is never hidden.
    """
    if len(data) < _HEADER.size:
        return None
    poll_time = int(_HEADER.unpack_from(data, 0)[3])
    current = time.time() if now is None else now
    if poll_time < _MIN_SANE_EPOCH or poll_time > current + 86_400:
        return None
    return max(current - poll_time, 0.0)


class HwinfoReader:
    def __init__(
        self,
        *,
        read_bytes: Callable[[], bytes | None] | None = None,
        disabled: bool | None = None,
    ) -> None:
        self._read_bytes = read_bytes
        self._disabled = (
            os.environ.get("PCOPTIMIZER_HWINFO_DISABLED") == "1"
            if disabled is None
            else disabled
        )
        self.last_error = ""

    def read(self) -> dict[str, tuple[float, str]] | None:
        if self._disabled:
            self.last_error = "HWiNFO reader disabled"
            return None
        try:
            data = self._read_bytes() if self._read_bytes is not None else self._map_bytes()
            if not data:
                self.last_error = (
                    "HWiNFO shared memory not available "
                    "(run HWiNFO with Sensors and enable Shared Memory Support)"
                )
                return None
            result = parse_hwinfo_bytes(data)
            age = hwinfo_poll_age(data)
            if age is not None and age > _STALE_AFTER_S:
                self.last_error = f"HWiNFO data is stale (no update for {age:.0f} s)"
                return None
            self.last_error = ""
            return result or None
        except Exception as exc:
            self.last_error = str(exc) or type(exc).__name__
            return None

    def _map_bytes(self) -> bytes | None:
        if not hasattr(ctypes, "WinDLL"):
            return None
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_mapping = kernel32.OpenFileMappingW
        open_mapping.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_wchar_p]
        open_mapping.restype = ctypes.c_void_p
        map_view = kernel32.MapViewOfFile
        map_view.argtypes = [
            ctypes.c_void_p,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_uint,
            ctypes.c_size_t,
        ]
        map_view.restype = ctypes.c_void_p
        unmap = kernel32.UnmapViewOfFile
        unmap.argtypes = [ctypes.c_void_p]
        unmap.restype = ctypes.c_bool
        close = kernel32.CloseHandle
        close.argtypes = [ctypes.c_void_p]
        close.restype = ctypes.c_bool

        handle = open_mapping(_FILE_MAP_READ, False, _MAP_NAME)
        if not handle:
            return None
        address = map_view(handle, _FILE_MAP_READ, 0, 0, 0)
        if not address:
            close(handle)
            return None
        mutex = None
        locked = False
        if hasattr(kernel32, "OpenMutexW"):
            open_mutex = kernel32.OpenMutexW
            open_mutex.argtypes = [ctypes.c_uint, ctypes.c_bool, ctypes.c_wchar_p]
            open_mutex.restype = ctypes.c_void_p
            wait = kernel32.WaitForSingleObject
            wait.argtypes = [ctypes.c_void_p, ctypes.c_uint]
            wait.restype = ctypes.c_uint
            release = kernel32.ReleaseMutex
            release.argtypes = [ctypes.c_void_p]
            release.restype = ctypes.c_bool
            mutex = open_mutex(_SYNCHRONIZE, False, _MUTEX_NAME)
            locked = bool(mutex and wait(mutex, _WAIT_TIMEOUT_MS) == 0)
        try:
            header = ctypes.string_at(address, _HEADER.size)
            values = _HEADER.unpack_from(header, 0)
            sensor_end = values[4] + values[5] * values[6]
            reading_end = values[7] + values[8] * values[9]
            size = max(_HEADER.size, sensor_end, reading_end)
            if size <= 0 or size > _MAX_BYTES:
                return None
            return ctypes.string_at(address, size)
        finally:
            if locked:
                release(mutex)
            if mutex:
                close(mutex)
            unmap(address)
            close(handle)
