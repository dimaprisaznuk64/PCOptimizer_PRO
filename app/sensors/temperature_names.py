from __future__ import annotations

KIND_CPU = "cpu"
KIND_BOARD = "board"
KIND_GPU = "gpu"
KIND_HOTSPOT = "hotspot"
KIND_SYSTEM = "system"

_GPU_HINTS = ("gpu", "nvidia", "geforce", "quadro", "rtx", "gtx", "radeon", "відео", "відеокарт")
_CPU_HINTS = (
    "cpu",
    "processor",
    "tctl",
    "tdie",
    "package",
    "core",
    "процесор",
    "проц",
    "цпу",
)
_BOARD_HINTS = (
    "motherboard",
    "mainboard",
    "system",
    "board",
    "chipset",
    "материн",
    "плата",
    "чіпсет",
    "vrm",
    "mos",
    "pch",
    "vcore",
    "soc",
)
_HOTSPOT_HINTS = ("hot spot", "hotspot", "junction", "гаряч", "перехід")
_BOARD_SENSOR_PARENTS = (
    "gigabyte",
    "asus",
    "asustek",
    "msi",
    "asrock",
    "biostar",
    "evga",
    "supermicro",
    "ite ",
    "nuvoton",
    "fintek",
    "renesas",
    "superio",
    "super i/o",
    "motherboard",
    "mainboard",
)
_GPU_PARENTS = ("dgpu", "gpu", "nvidia", "geforce", "radeon", "quadro", "rtx", "gtx")
_DISK_PARENTS = ("s.m.a.r.t.", "smart", "nvme", "ssd", "hdd")

_PREFER: dict[str, tuple[str, ...]] = {
    KIND_CPU: ("tctl", "tdie", "package", "cpu die", "ccd", "core", "процесор", "проц"),
    KIND_BOARD: ("motherboard", "mainboard", "материн", "pch", "vrm", "system", "chipset", "socket", "чіпсет"),
    KIND_GPU: ("gpu temperature", "gpu core", "gpu edge", "gpu", "nvidia", "geforce", "rtx", "radeon"),
    KIND_HOTSPOT: (
        "gpu hot spot",
        "gpu hotspot",
        "gpu memory junction",
        "memory junction",
        "hot spot",
        "junction",
        "cpu iod hotspot",
        "гаряч",
    ),
    KIND_SYSTEM: ("acpi", "zone", "композит", "composite", "system"),
}


def _is_board_parent(lowered: str) -> bool:
    return any(hint in lowered for hint in _BOARD_SENSOR_PARENTS)


def _is_gpu_parent(lowered: str) -> bool:
    return any(hint in lowered for hint in _GPU_PARENTS)


def _is_disk_parent(lowered: str) -> bool:
    return any(hint in lowered for hint in _DISK_PARENTS)


_CANONICAL = {KIND_CPU, KIND_BOARD, KIND_GPU, KIND_HOTSPOT, KIND_SYSTEM}


def temperature_kind(name: str, identifier: str = "") -> str:
    lowered = f"{name} {identifier}".strip().lower()
    if not lowered:
        return KIND_SYSTEM
    if lowered in _CANONICAL:
        return lowered
    if _is_disk_parent(lowered):
        return KIND_SYSTEM
    parent_board = _is_board_parent(lowered)
    parent_gpu = _is_gpu_parent(lowered)
    if parent_gpu and any(hint in lowered for hint in _HOTSPOT_HINTS):
        return KIND_HOTSPOT
    if "gpu memory" in lowered and "junction" in lowered:
        return KIND_HOTSPOT
    if parent_gpu and any(hint in lowered for hint in _GPU_HINTS):
        return KIND_GPU
    if any(hint in lowered for hint in _CPU_HINTS) and any(hint in lowered for hint in _HOTSPOT_HINTS):
        return KIND_HOTSPOT
    if parent_board:
        return KIND_BOARD
    if any(hint in lowered for hint in _GPU_HINTS):
        if any(hint in lowered for hint in _HOTSPOT_HINTS):
            return KIND_HOTSPOT
        return KIND_GPU
    if any(hint in lowered for hint in _HOTSPOT_HINTS):
        return KIND_HOTSPOT
    if "socket" in lowered:
        return KIND_BOARD
    if any(hint in lowered for hint in _CPU_HINTS):
        return KIND_CPU
    if any(hint in lowered for hint in _BOARD_HINTS):
        return KIND_BOARD
    return KIND_SYSTEM


def temperature_priority(raw: str, kind: str) -> int:
    lowered = raw.lower()
    options = _PREFER.get(kind, ())
    for index, preferred in enumerate(options):
        if preferred in lowered:
            return len(options) - index
    return 0


def canonical_temperature_name(name: str) -> str:
    kind = temperature_kind(name)
    if kind in (KIND_CPU, KIND_BOARD, KIND_GPU):
        return kind
    return name.strip()
