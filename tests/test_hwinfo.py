from __future__ import annotations

import struct

import pytest

from app.sensors.hwinfo import HwinfoReader, parse_hwinfo_bytes

_HEADER_SIZE = struct.calcsize("<IIIqIIIIII")
_SENSOR_SIZE = 0x108
_READING_SIZE = 0x13C
_SIGNATURE = int.from_bytes(b"HWiS", "little")


def _reading(data: bytearray, index: int, *, kind: int, label: str, value: float) -> None:
    base = _HEADER_SIZE + _SENSOR_SIZE + index * _READING_SIZE
    struct.pack_into("<I", data, base, kind)
    struct.pack_into("<I", data, base + 0x04, 0)
    raw = label.encode("utf-8")
    data[base + 0x0C : base + 0x0C + len(raw)] = raw
    struct.pack_into("<d", data, base + 0x11C, value)


def _payload() -> bytes:
    reading_offset = _HEADER_SIZE + _SENSOR_SIZE
    data = bytearray(reading_offset + 3 * _READING_SIZE)
    struct.pack_into(
        "<IIIqIIIIII",
        data,
        0,
        _SIGNATURE,
        1,
        0,
        250,
        _HEADER_SIZE,
        _SENSOR_SIZE,
        1,
        reading_offset,
        _READING_SIZE,
        3,
    )
    name = b"AMD Ryzen 5 5600"
    data[_HEADER_SIZE + 8 : _HEADER_SIZE + 8 + len(name)] = name
    _reading(data, 0, kind=1, label="Core (Tctl/Tdie)", value=72.5)
    _reading(data, 1, kind=1, label="Motherboard", value=44.0)
    _reading(data, 2, kind=2, label="Fan", value=1200.0)
    return bytes(data)


def test_parse_hwinfo_bytes_reads_cpu_and_board_without_fake_gpu() -> None:
    result = parse_hwinfo_bytes(_payload())
    assert result["cpu"][0] == 72.5
    assert result["board"][0] == 44.0
    assert "hwinfo" in result["cpu"][1]
    assert "gpu" not in result


def test_parse_hwinfo_bytes_rejects_inactive_memory() -> None:
    data = bytearray(_payload())
    struct.pack_into("<I", data, 0, 0)
    with pytest.raises(ValueError, match="signature"):
        parse_hwinfo_bytes(bytes(data))


def test_hwinfo_reader_uses_injected_bytes() -> None:
    reader = HwinfoReader(read_bytes=_payload)
    result = reader.read()
    assert result is not None
    assert result["cpu"][0] == 72.5
    assert reader.last_error == ""


def test_hwinfo_reader_reports_missing_memory() -> None:
    reader = HwinfoReader(read_bytes=lambda: None)
    assert reader.read() is None
    assert "shared memory not available" in reader.last_error
