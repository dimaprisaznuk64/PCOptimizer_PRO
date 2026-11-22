from __future__ import annotations

KIND_CPU = "cpu"
KIND_BOARD = "board"
KIND_GPU = "gpu"
KIND_HOTSPOT = "hotspot"
KIND_SYSTEM = "system"

_GPU_HINTS = ("gpu", "nvidia", "geforce", "quadro", "rtx", "gtx", "radeon")
_CPU_HINTS = ("cpu", "processor", "tctl", "tdie", "package", "core")
_BOARD_HINTS = ("motherboard", "mainboard", "system", "board", "chipset")


def temperature_kind(name: str) -> str:
    lowered = name.strip().lower()
    if any(hint in lowered for hint in _GPU_HINTS):
        return KIND_GPU
    if "socket" in lowered:
        return KIND_BOARD
    if any(hint in lowered for hint in _CPU_HINTS):
        return KIND_CPU
    if any(hint in lowered for hint in _BOARD_HINTS):
        return KIND_BOARD
    return KIND_SYSTEM


def canonical_temperature_name(name: str) -> str:
    kind = temperature_kind(name)
    if kind in (KIND_CPU, KIND_BOARD, KIND_GPU):
        return kind
    return name.strip()
