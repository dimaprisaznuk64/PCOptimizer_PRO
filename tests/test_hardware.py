from __future__ import annotations

import time
from types import SimpleNamespace

from app.hardware import HardwareReport, HardwareService
from app.ui.hardware import HardwarePage
from app.ui.main_window import MainWindow
from app.ui.sidebar import NAV_ITEMS


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _rows() -> dict[str, list]:
    return {
        "Win32_ComputerSystem": [SimpleNamespace(Manufacturer="LENOVO", Model="82RF", TotalPhysicalMemory=34359738368)],
        "Win32_OperatingSystem": [
            SimpleNamespace(Caption="Microsoft Windows 11 Pro", Version="10.0.22631", OSArchitecture="64-bit")
        ],
        "Win32_Processor": [
            SimpleNamespace(
                Name="12th Gen Intel(R) Core(TM) i7-12700H",
                Manufacturer="GenuineIntel",
                NumberOfCores=14,
                NumberOfLogicalProcessors=20,
                MaxClockSpeed=4700,
                CurrentClockSpeed=2800,
                SocketDesignation="U3E1",
                L2CacheSize=11776,
                L3CacheSize=24576,
            )
        ],
        "Win32_PhysicalMemory": [
            SimpleNamespace(
                DeviceLocator="Controller0-ChannelA",
                Capacity=17179869184,
                ConfiguredClockSpeed=4800,
                Manufacturer="Samsung",
                PartNumber="M471A2G43CB2-CWE",
                SMBIOSMemoryType=26,
            ),
            SimpleNamespace(
                DeviceLocator="Controller0-ChannelB",
                Capacity=17179869184,
                ConfiguredClockSpeed=4800,
                Manufacturer="Samsung",
                PartNumber="M471A2G43CB2-CWE",
                SMBIOSMemoryType=26,
            ),
        ],
        "Win32_PhysicalMemoryArray": [SimpleNamespace(MemoryDevices=2)],
        "Win32_VideoController": [
            SimpleNamespace(
                Name="Intel(R) Iris Xe Graphics",
                AdapterRAM=1073741824,
                DriverVersion="31.0.101.4502",
                DriverDate="20231012000000.000000+000",
                AdapterCompatibility="Intel Corporation",
            ),
            SimpleNamespace(
                Name="NVIDIA GeForce RTX 3050 Ti Laptop GPU",
                AdapterRAM=4294967295,
                DriverVersion="31.0.15.3623",
                DriverDate="20230920000000.000000+000",
                AdapterCompatibility="NVIDIA",
            ),
        ],
        "Win32_BaseBoard": [
            SimpleNamespace(
                Manufacturer="LENOVO", Product="LNVNB161216", Version="SDK0T76463 WIN", SerialNumber="PF3TEST"
            )
        ],
        "Win32_BIOS": [
            SimpleNamespace(Manufacturer="LENOVO", SMBIOSBIOSVersion="G9CN40WW", ReleaseDate="20220315000000.000000+000")
        ],
        "Win32_DiskDrive": [
            SimpleNamespace(
                Index=0,
                Model="Samsung SSD 980 PRO 1TB",
                Size=1000204886016,
                InterfaceType="SCSI",
                SerialNumber="S6B0NL0T",
            )
        ],
        "MSFT_PhysicalDisk": [SimpleNamespace(DeviceId="0", MediaType=4)],
    }


def _service(mapping=None, fail=(), gpu_memory=None) -> HardwareService:
    mapping = _rows() if mapping is None else mapping

    def query(cls_name: str, namespace: str = "root\\cimv2"):
        if cls_name in fail:
            raise RuntimeError(f"boom:{cls_name}")
        return mapping.get(cls_name, [])

    return HardwareService(
        query=query,
        gpu_memory=gpu_memory or (lambda: [("NVIDIA GeForce RTX 3050 Ti Laptop GPU", 4294967296)]),
        hostname=lambda: "TEST-PC",
    )


# ---------- service ----------


def test_report_reads_system_and_cpu() -> None:
    report = _service().report()
    assert report.system.manufacturer == "LENOVO"
    assert report.system.model == "82RF"
    assert report.system.os_name == "Microsoft Windows 11 Pro"
    assert report.system.os_version == "10.0.22631"
    assert report.system.architecture == "64-bit"
    assert report.system.hostname == "TEST-PC"
    assert report.cpu is not None
    assert report.cpu.name.startswith("12th Gen Intel")
    assert report.cpu.physical_cores == 14
    assert report.cpu.logical_cores == 20
    assert report.cpu.max_clock_mhz == 4700
    assert report.cpu.socket == "U3E1"
    assert report.cpu.l3_kb == 24576
    assert report.errors == ()


def test_report_memory_modules_and_slots() -> None:
    memory = _service().report().memory
    assert memory.total_bytes == 2 * 17179869184
    assert memory.slots_used == 2
    assert memory.slots_total == 2
    assert memory.speed_mhz == 4800
    assert len(memory.modules) == 2
    assert memory.modules[0].memory_type == "DDR4"
    assert memory.modules[0].manufacturer == "Samsung"


def test_report_gpus_use_nvml_vram() -> None:
    gpus = _service().report().gpus
    assert [g.name for g in gpus] == ["Intel(R) Iris Xe Graphics", "NVIDIA GeForce RTX 3050 Ti Laptop GPU"]
    assert gpus[0].vram_bytes == 1073741824
    assert gpus[1].vram_bytes == 4294967296  # NVML wins over the WMI AdapterRAM cap
    assert gpus[1].vendor == "NVIDIA"


def test_report_board_bios_and_disks() -> None:
    report = _service().report()
    assert report.board.product == "LNVNB161216"
    assert report.bios.version == "G9CN40WW"
    assert report.bios.date == "2022-03-15"
    assert len(report.disks) == 1
    assert report.disks[0].model == "Samsung SSD 980 PRO 1TB"
    assert report.disks[0].media == "SSD"
    assert report.disks[0].interface == "SCSI"


def test_missing_cpu_returns_none() -> None:
    mapping = _rows()
    mapping["Win32_Processor"] = []
    report = _service(mapping).report()
    assert report.cpu is None


def test_memory_type_falls_back_to_legacy_field() -> None:
    mapping = _rows()
    mapping["Win32_PhysicalMemory"] = [
        SimpleNamespace(
            DeviceLocator="DIMM0",
            Capacity=8589934592,
            Speed=1600,
            Manufacturer="Kingston",
            PartNumber="KHX1600",
            SMBIOSMemoryType=0,
            MemoryType=24,
        )
    ]
    memory = _service(mapping).report().memory
    assert memory.modules[0].memory_type == "DDR3"
    assert memory.speed_mhz == 1600


def test_missing_storage_media_stays_empty() -> None:
    mapping = _rows()
    mapping["MSFT_PhysicalDisk"] = []
    assert _service(mapping).report().disks[0].media == ""


def test_query_errors_are_collected_not_fatal() -> None:
    report = _service(fail={"Win32_BIOS"}).report()
    assert any("BIOS" in e for e in report.errors)
    assert report.bios.version == ""
    assert report.cpu is not None
    assert len(report.disks) == 1


# ---------- UI ----------


class FakeHardwareService:
    def __init__(self, report: HardwareReport | None = None, fail: bool = False) -> None:
        self._report = report or _service().report()
        self._fail = fail
        self.calls = 0

    def report(self) -> HardwareReport:
        self.calls += 1
        if self._fail:
            raise RuntimeError("no wmi")
        return self._report


def test_page_registered_in_nav(qapp) -> None:
    assert "hardware" in {key for key, _ in NAV_ITEMS}
    window = MainWindow()
    assert isinstance(window.page("hardware"), HardwarePage)
    window.close()


def test_page_renders_report(qapp) -> None:
    service = FakeHardwareService()
    page = HardwarePage(service=service)
    page.start_load()
    assert _wait_until(qapp, lambda: page.modules_table.rowCount() == 2)
    assert service.calls == 1
    assert page.cpu_card._rows["Cores"].text().endswith("14")
    assert page.system_card._rows["Model"].text().endswith("82RF")
    assert page.modules_table.item(0, 3).text() == "DDR4"
    assert page.disks_table.rowCount() == 1
    assert page.disks_table.item(0, 3).text() == "SSD"
    assert page.gpu_card._rows  # at least one GPU row
    assert "loaded" in page.status_label.text().lower()
    assert page.refresh_button.isEnabled()


def test_page_busy_disables_refresh(qapp) -> None:
    page = HardwarePage(service=FakeHardwareService())
    page.start_load()
    assert not page.refresh_button.isEnabled()
    assert _wait_until(qapp, lambda: page.modules_table.rowCount() == 2)
    assert page.refresh_button.isEnabled()


def test_page_reports_failure(qapp) -> None:
    page = HardwarePage(service=FakeHardwareService(fail=True))
    page.start_load()
    assert _wait_until(qapp, lambda: "Failed" in page.status_label.text())
    assert page.modules_table.rowCount() == 0
    assert page.refresh_button.isEnabled()


def test_page_marks_warnings(qapp) -> None:
    report = _service(fail={"Win32_BIOS"}).report()
    page = HardwarePage(service=FakeHardwareService(report=report))
    page.start_load()
    assert _wait_until(qapp, lambda: "warning" in page.status_label.text().lower())


def test_retranslate_rerenders_labels(qapp) -> None:
    from PySide6.QtWidgets import QLabel

    from app.i18n import I18nService, tr

    page = HardwarePage(service=FakeHardwareService())
    page.start_load()
    assert _wait_until(qapp, lambda: page.modules_table.rowCount() == 2)
    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert tr("hw_cores") in page.cpu_card._rows
        assert tr("hw_total_memory") in page.memory_card._rows
        assert len(page.cpu_card.findChildren(QLabel, "cardRow")) == len(page.cpu_card._rows)
    finally:
        I18nService.instance().set_language("EN", emit=False)
