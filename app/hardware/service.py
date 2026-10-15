"""Hardware inventory: CPU, memory modules, motherboard, BIOS, GPUs and disks.

Everything is read-only. Data comes from WMI (``root\\cimv2`` and the storage
namespace) and, for the VRAM of NVIDIA cards, from NVML. The whole module is
built around an injectable ``query`` callable so it can be unit-tested without
touching the real machine.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

CIMV2 = "root\\cimv2"
STORAGE = "root\\microsoft\\windows\\storage"

_MEMORY_TYPES = {
    20: "DDR",
    21: "DDR2",
    22: "DDR2 FB-DIMM",
    24: "DDR3",
    26: "DDR4",
    27: "LPDDR",
    28: "LPDDR2",
    29: "LPDDR3",
    30: "LPDDR4",
    34: "DDR5",
    35: "LPDDR5",
}

_MEDIA_TYPES = {3: "HDD", 4: "SSD", 5: "SCM"}


class HardwareError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class SystemInfo:
    manufacturer: str = ""
    model: str = ""
    os_name: str = ""
    os_version: str = ""
    architecture: str = ""
    hostname: str = ""


@dataclass(frozen=True, slots=True)
class CpuInfo:
    name: str = ""
    manufacturer: str = ""
    physical_cores: int = 0
    logical_cores: int = 0
    max_clock_mhz: int = 0
    current_clock_mhz: int = 0
    socket: str = ""
    l2_kb: int = 0
    l3_kb: int = 0


@dataclass(frozen=True, slots=True)
class GpuInfo:
    name: str = ""
    vendor: str = ""
    vram_bytes: int = 0
    driver_version: str = ""
    driver_date: str = ""


@dataclass(frozen=True, slots=True)
class MemoryModule:
    slot: str = ""
    capacity_bytes: int = 0
    speed_mhz: int = 0
    manufacturer: str = ""
    part_number: str = ""
    memory_type: str = ""


@dataclass(frozen=True, slots=True)
class MemoryInfo:
    total_bytes: int = 0
    modules: tuple[MemoryModule, ...] = ()
    slots_used: int = 0
    slots_total: int = 0
    speed_mhz: int = 0


@dataclass(frozen=True, slots=True)
class BoardInfo:
    manufacturer: str = ""
    product: str = ""
    version: str = ""
    serial: str = ""


@dataclass(frozen=True, slots=True)
class BiosInfo:
    vendor: str = ""
    version: str = ""
    date: str = ""


@dataclass(frozen=True, slots=True)
class DiskInfo:
    model: str = ""
    size_bytes: int = 0
    interface: str = ""
    media: str = ""
    serial: str = ""


@dataclass(frozen=True, slots=True)
class HardwareReport:
    system: SystemInfo = field(default_factory=SystemInfo)
    cpu: CpuInfo | None = None
    gpus: tuple[GpuInfo, ...] = ()
    memory: MemoryInfo = field(default_factory=MemoryInfo)
    board: BoardInfo = field(default_factory=BoardInfo)
    bios: BiosInfo = field(default_factory=BiosInfo)
    disks: tuple[DiskInfo, ...] = ()
    errors: tuple[str, ...] = ()


def _get(obj: Any, name: str, default: Any = None) -> Any:
    value = getattr(obj, name, default)
    return default if value is None else value


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _wmi_date(value: Any) -> str:
    """Win32 CIM datetime (``20220315000000.000000+000``) → ``2022-03-15``."""
    text = _text(value)
    if len(text) >= 8 and text[:8].isdigit():
        return f"{text[0:4]}-{text[4:6]}-{text[6:8]}"
    return text


def _memory_type(code: Any) -> str:
    return _MEMORY_TYPES.get(_to_int(code, -1), "")


def _default_query(cls_name: str, namespace: str = CIMV2) -> Sequence[Any]:
    import wmi

    return list(getattr(wmi.WMI(namespace=namespace), cls_name)())


def _default_gpu_memory() -> list[tuple[str, int]]:
    """Per-GPU total VRAM (bytes) from NVML, best-effort (NVIDIA only)."""
    try:
        import pynvml
    except ImportError:
        return []
    try:
        pynvml.nvmlInit()
    except Exception:
        return []
    out: list[tuple[str, int]] = []
    try:
        for index in range(pynvml.nvmlDeviceGetCount()):
            handle = pynvml.nvmlDeviceGetHandleByIndex(index)
            name = pynvml.nvmlDeviceGetName(handle)
            if isinstance(name, bytes):
                name = name.decode("utf-8", "replace")
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            out.append((str(name), int(info.total)))
    except Exception:
        pass
    finally:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass
    return out


class HardwareService:
    def __init__(
        self,
        *,
        query: Callable[[str, str], Sequence[Any]] | None = None,
        gpu_memory: Callable[[], list[tuple[str, int]]] | None = None,
        hostname: Callable[[], str] | None = None,
    ) -> None:
        self._query = query or _default_query
        self._gpu_memory = gpu_memory or _default_gpu_memory
        self._hostname = hostname or self._default_hostname

    # ---------- public ----------

    def report(self) -> HardwareReport:
        errors: list[str] = []
        return HardwareReport(
            system=self._system(errors),
            cpu=self._cpu(errors),
            gpus=self._gpus(errors),
            memory=self._memory(errors),
            board=self._board(errors),
            bios=self._bios(errors),
            disks=self._disks(errors),
            errors=tuple(errors),
        )

    # ---------- sections ----------

    def _system(self, errors: list[str]) -> SystemInfo:
        system = SystemInfo(hostname=self._hostname())
        cs = self._try(errors, "System", "Win32_ComputerSystem")
        if cs:
            first = cs[0]
            system = SystemInfo(
                manufacturer=_text(_get(first, "Manufacturer")),
                model=_text(_get(first, "Model")),
                os_name=system.os_name,
                os_version=system.os_version,
                architecture=system.architecture,
                hostname=system.hostname,
            )
        op = self._try(errors, "OS", "Win32_OperatingSystem")
        if op:
            first = op[0]
            system = SystemInfo(
                manufacturer=system.manufacturer,
                model=system.model,
                os_name=_text(_get(first, "Caption")),
                os_version=_text(_get(first, "Version")),
                architecture=_text(_get(first, "OSArchitecture")),
                hostname=system.hostname,
            )
        return system

    def _cpu(self, errors: list[str]) -> CpuInfo | None:
        rows = self._try(errors, "CPU", "Win32_Processor")
        if not rows:
            return None
        first = rows[0]
        return CpuInfo(
            name=_text(_get(first, "Name")),
            manufacturer=_text(_get(first, "Manufacturer")),
            physical_cores=_to_int(_get(first, "NumberOfCores")),
            logical_cores=_to_int(_get(first, "NumberOfLogicalProcessors")),
            max_clock_mhz=_to_int(_get(first, "MaxClockSpeed")),
            current_clock_mhz=_to_int(_get(first, "CurrentClockSpeed")),
            socket=_text(_get(first, "SocketDesignation")),
            l2_kb=_to_int(_get(first, "L2CacheSize")),
            l3_kb=_to_int(_get(first, "L3CacheSize")),
        )

    def _memory(self, errors: list[str]) -> MemoryInfo:
        modules: list[MemoryModule] = []
        for row in self._try(errors, "Memory", "Win32_PhysicalMemory"):
            speed = _to_int(_get(row, "ConfiguredClockSpeed")) or _to_int(_get(row, "Speed"))
            modules.append(
                MemoryModule(
                    slot=_text(_get(row, "DeviceLocator")),
                    capacity_bytes=_to_int(_get(row, "Capacity")),
                    speed_mhz=speed,
                    manufacturer=_text(_get(row, "Manufacturer")),
                    part_number=_text(_get(row, "PartNumber")),
                    memory_type=_memory_type(
                        _to_int(_get(row, "SMBIOSMemoryType")) or _get(row, "MemoryType")
                    ),
                )
            )
        modules.sort(key=lambda m: m.slot.lower())
        total = sum(m.capacity_bytes for m in modules)
        if total == 0:
            cs = self._try(errors, "System", "Win32_ComputerSystem")
            if cs:
                total = _to_int(_get(cs[0], "TotalPhysicalMemory"))
        slots_total = 0
        for array in self._try(errors, "MemoryArray", "Win32_PhysicalMemoryArray"):
            slots_total += _to_int(_get(array, "MemoryDevices"))
        speeds = [m.speed_mhz for m in modules if m.speed_mhz]
        return MemoryInfo(
            total_bytes=total,
            modules=tuple(modules),
            slots_used=len(modules),
            slots_total=slots_total,
            speed_mhz=max(speeds) if speeds else 0,
        )

    def _gpus(self, errors: list[str]) -> tuple[GpuInfo, ...]:
        rows = self._try(errors, "GPU", "Win32_VideoController")
        probe = list(self._gpu_memory() or [])
        gpus: list[GpuInfo] = []
        for row in rows:
            name = _text(_get(row, "Name"))
            # WMI AdapterRAM is a 32-bit field that overflows to a negative value
            # on many GPUs (e.g. -1048576) — treat anything ≤ 0 as "unknown".
            vram = max(_to_int(_get(row, "AdapterRAM")), 0)
            for probe_name, probe_bytes in probe:
                low_probe = probe_name.lower()
                low_name = name.lower()
                if low_probe and low_name and (low_probe in low_name or low_name in low_probe):
                    vram = max(vram, probe_bytes)
                    break
            gpus.append(
                GpuInfo(
                    name=name,
                    vendor=_text(_get(row, "AdapterCompatibility")),
                    vram_bytes=vram,
                    driver_version=_text(_get(row, "DriverVersion")),
                    driver_date=_wmi_date(_get(row, "DriverDate")),
                )
            )
        return tuple(gpus)

    def _board(self, errors: list[str]) -> BoardInfo:
        rows = self._try(errors, "Board", "Win32_BaseBoard")
        if not rows:
            return BoardInfo()
        first = rows[0]
        return BoardInfo(
            manufacturer=_text(_get(first, "Manufacturer")),
            product=_text(_get(first, "Product")),
            version=_text(_get(first, "Version")),
            serial=_text(_get(first, "SerialNumber")),
        )

    def _bios(self, errors: list[str]) -> BiosInfo:
        rows = self._try(errors, "BIOS", "Win32_BIOS")
        if not rows:
            return BiosInfo()
        first = rows[0]
        return BiosInfo(
            vendor=_text(_get(first, "Manufacturer")),
            version=_text(_get(first, "SMBIOSBIOSVersion")) or _text(_get(first, "Version")),
            date=_wmi_date(_get(first, "ReleaseDate")),
        )

    def _disks(self, errors: list[str]) -> tuple[DiskInfo, ...]:
        rows = self._try(errors, "Disks", "Win32_DiskDrive")
        media = self._disk_media(errors)
        disks: list[DiskInfo] = []
        for row in rows:
            index = _to_int(_get(row, "Index"), -1)
            disks.append(
                DiskInfo(
                    model=_text(_get(row, "Model")),
                    size_bytes=_to_int(_get(row, "Size")),
                    interface=_text(_get(row, "InterfaceType")),
                    media=media.get(str(index), ""),
                    serial=_text(_get(row, "SerialNumber")),
                )
            )
        return tuple(disks)

    def _disk_media(self, errors: list[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for row in self._try(errors, "DiskMedia", "MSFT_PhysicalDisk", STORAGE):
            device_id = _text(_get(row, "DeviceId"))
            media = _MEDIA_TYPES.get(_to_int(_get(row, "MediaType"), -1))
            if device_id and media:
                result[device_id] = media
        return result

    # ---------- helpers ----------

    def _try(self, errors: list[str], label: str, cls_name: str, namespace: str = CIMV2) -> Sequence[Any]:
        try:
            return self._query(cls_name, namespace)
        except Exception as e:
            errors.append(f"{label}: {e}")
            return []

    @staticmethod
    def _default_hostname() -> str:
        import platform

        return platform.node()
