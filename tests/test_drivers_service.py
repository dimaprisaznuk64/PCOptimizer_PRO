from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.drivers import DRIVER_SCRIPT, DriverInfo, DriverService, parse_drivers
from app.drivers import service as drivers_service
from app.i18n import I18nService, tr
from app.ui.drivers import COLUMN_KEYS, DriversPage
from app.winpaths import POWERSHELL_PATH, PS_UTF8_PREFIX


def _wait_for(qapp, predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def _rows() -> list[dict[str, str | None]]:
    return [
        {
            "Name": "NVIDIA Windows Kernel Mode Driver",
            "DeviceClass": "Display",
            "Manufacturer": "NVIDIA",
            "DriverVersion": "32.0.15.6094",
            "DriverDate": "20240701000000.000000+000",
            "ProviderName": "NVIDIA Corporation",
            "Status": "OK",
        },
        {
            "Name": "Realtek Audio",
            "DeviceClass": "MEDIA",
            "Manufacturer": "Realtek",
            "DriverVersion": None,
            "DriverDate": None,
            "ProviderName": None,
            "Status": None,
        },
    ]


def test_driver_info_is_frozen_and_slotted() -> None:
    info = DriverInfo(device="nvlddmkm.sys")
    assert info.__slots__ == (
        "device",
        "device_class",
        "vendor",
        "driver_version",
        "driver_date",
        "provider",
        "status",
    )
    with pytest.raises(AttributeError):
        info.device = "other"


def test_parse_drivers_array() -> None:
    parsed = parse_drivers(json.dumps(_rows()))
    assert len(parsed) == 2
    assert parsed[0] == DriverInfo(
        device="NVIDIA Windows Kernel Mode Driver",
        device_class="Display",
        vendor="NVIDIA",
        driver_version="32.0.15.6094",
        driver_date="20240701000000.000000+000",
        provider="NVIDIA Corporation",
        status="OK",
    )
    assert parsed[1].device == "Realtek Audio"
    assert parsed[1].driver_version == ""


def test_parse_drivers_single_object_and_bom() -> None:
    payload = "\ufeff" + json.dumps(_rows()[0])
    parsed = parse_drivers(payload)
    assert len(parsed) == 1
    assert parsed[0].device == "NVIDIA Windows Kernel Mode Driver"


@pytest.mark.parametrize(
    "payload",
    ["", "   \n", "null", "[]", "{}", "not json at all", '"text"', '[1, "x", {}]'],
)
def test_parse_drivers_empty_and_garbage(payload: str) -> None:
    assert parse_drivers(payload) == ()


def test_list_drivers_uses_readonly_powershell_script() -> None:
    captured: dict[str, object] = {}

    def run(args, timeout):
        captured["args"] = list(args)
        captured["timeout"] = timeout
        return 0, json.dumps(_rows())

    drivers, errors = DriverService(run=run).list_drivers()
    assert errors == ()
    assert len(drivers) == 2
    assert captured["args"] == [
        POWERSHELL_PATH,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        PS_UTF8_PREFIX + DRIVER_SCRIPT,
    ]
    assert captured["timeout"] == 40.0


def test_driver_script_only_uses_readonly_verbs() -> None:
    assert DRIVER_SCRIPT.count("Get-CimInstance") == 1
    assert "Win32_PnPSignedDriver" in DRIVER_SCRIPT
    assert "Select-Object" in DRIVER_SCRIPT
    assert "ConvertTo-Json -Compress" in DRIVER_SCRIPT
    lowered = DRIVER_SCRIPT.lower()
    for verb in (
        "set-",
        "new-",
        "remove-",
        "install-",
        "uninstall-",
        "update-",
        "enable-",
        "disable-",
        "clear-",
        "write-",
        "start-",
        "stop-",
        "rename-",
        "move-",
        "copy-",
    ):
        assert verb not in lowered


def test_driver_service_has_no_mutating_api() -> None:
    public = {name for name in dir(DriverService) if not name.startswith("_")}
    assert public == {"list_drivers"}
    source = Path(drivers_service.__file__).read_text(encoding="utf-8").lower()
    for token in (
        "install",
        "uninstall",
        "download",
        "winreg",
        "set_item",
        "delete_value",
        "remove_item",
        "new_item",
        "write_value",
    ):
        assert token not in source


def test_list_drivers_reports_failure_and_exception() -> None:
    drivers, errors = DriverService(run=lambda args, timeout: (1, "")).list_drivers()
    assert drivers == ()
    assert len(errors) == 1
    assert "exit 1" in errors[0]

    def boom(args, timeout):
        raise OSError("boom")

    drivers, errors = DriverService(run=boom).list_drivers()
    assert drivers == ()
    assert len(errors) == 1
    assert "boom" in errors[0]


def test_default_run_uses_create_no_window_and_decodes_oem_output(monkeypatch) -> None:
    calls: dict[str, object] = {}
    payload = json.dumps([{"Name": "Драйвер"}], ensure_ascii=False).encode("cp866")

    def fake_run(args, **kwargs):
        calls.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=payload, stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    drivers, errors = DriverService().list_drivers()
    assert errors == ()
    assert drivers[0].device == "Драйвер"
    assert calls["capture_output"] is True
    assert calls["timeout"] == 40.0
    assert calls["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _page_service(fail: bool = False) -> DriverService:
    def run(args, timeout):
        if fail:
            return 1, "missing powershell"
        return 0, json.dumps(_rows())

    return DriverService(run=run)


def test_drivers_page_renders_loaded_drivers(qapp) -> None:
    page = DriversPage(service=_page_service())
    page.start_load()
    assert _wait_for(qapp, lambda: page.table.rowCount() == 2)
    assert page.table.item(0, 0).text() == "NVIDIA Windows Kernel Mode Driver"
    assert page.table.item(1, 3).text() == ""
    assert page.refresh_button.isEnabled()
    assert "2" in page.status_label.text()


def test_drivers_page_reports_failure(qapp) -> None:
    page = DriversPage(service=_page_service(fail=True))
    page.start_load()
    assert _wait_for(qapp, lambda: "exit 1" in page.status_label.text())
    assert page.table.rowCount() == 0
    assert page.refresh_button.isEnabled()


def test_drivers_page_retranslate_updates_headers(qapp) -> None:
    page = DriversPage(service=_page_service())
    I18nService.instance().set_language("UA", emit=False)
    try:
        page.retranslate()
        assert page.table.horizontalHeaderItem(0).text() == tr("drv_col_device")
        assert page.table.horizontalHeaderItem(6).text() == tr("drv_col_status")
    finally:
        I18nService.instance().set_language("EN", emit=False)


def test_drivers_page_column_keys_are_localized() -> None:
    assert len(COLUMN_KEYS) == 7
    assert all(tr(key) != key for key in COLUMN_KEYS)
