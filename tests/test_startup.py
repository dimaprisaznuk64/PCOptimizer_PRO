from __future__ import annotations

import time

import pytest

from app.startup import StartupError, StartupItem, StartupService
from app.startup.service import (
    DISABLED_FLAG,
    approved_enabled,
    impact_of,
)
from app.ui.startup import StartupPage

# ---------- pure helpers ----------


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (None, True),
        (b"", True),
        (DISABLED_FLAG, False),
        (bytes([0x03]) + bytes(15), False),
        (bytes([0x06]) + bytes(15), True),
    ],
)
def test_approved_enabled(data, expected) -> None:
    assert approved_enabled(data) is expected


def test_impact_large_target_is_high() -> None:
    impact, reason = impact_of("Whatever", 200 * 1024**2)
    assert impact == "High"
    assert "MB" in reason


def test_impact_known_heavyweight() -> None:
    impact, reason = impact_of("Steam", None)
    assert impact == "High"
    assert "heavyweight" in reason


def test_impact_medium_by_size_and_keyword() -> None:
    assert impact_of("x", 50 * 1024**2)[0] == "Medium"
    assert impact_of("Foo Helper", None)[0] == "Medium"


def test_impact_low() -> None:
    impact, reason = impact_of("tiny", 1024)
    assert impact == "Low"
    assert "KB" in reason
    assert impact_of("unknown", None)[0] == "Low"


# ---------- fake registry service ----------


class FakeRegistryService(StartupService):
    """StartupService backed by in-memory dict instead of winreg."""

    def __init__(self, tmp_path, values: dict | None = None) -> None:
        super().__init__(
            backup_dir=tmp_path / "backup",
            run_sources=(("HKCU", RUN_KEY, "HKCU Run"),),
        )
        self.reg: dict[tuple[str, str, str], tuple[object, int]] = dict(values or {})

    def _reg_enum_values(self, hive: str, key_path: str) -> list[tuple[str, object, int]]:
        out = []
        for (h, k, name), (data, vtype) in self.reg.items():
            if h == hive and k == key_path:
                out.append((name, data, vtype))
        if not out and not any(k == key_path for (_h, k, _n) in self.reg):
            raise FileNotFoundError(key_path)
        return out

    def _reg_query(self, hive: str, key_path: str, name: str) -> tuple[object, int]:
        try:
            return self.reg[(hive, key_path, name)]
        except KeyError:
            raise FileNotFoundError(name) from None

    def _reg_set(self, hive: str, key_path: str, name: str, value_type: int, data: object) -> None:
        self.reg[(hive, key_path, name)] = (data, value_type)

    def _reg_delete(self, hive: str, key_path: str, name: str) -> None:
        try:
            del self.reg[(hive, key_path, name)]
        except KeyError:
            raise FileNotFoundError(name) from None


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APPROVED_RUN = r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"


def test_registry_list_and_toggle(tmp_path) -> None:
    service = FakeRegistryService(tmp_path, {("HKCU", RUN_KEY, "MyApp"): (r"C:\bin\app.exe", 1)})
    items, errors = service.list_items()
    assert errors == []
    item = next(i for i in items if i.name == "MyApp")
    assert item.enabled is True
    assert item.kind == "registry"

    service.set_enabled(item, False)
    assert ( "HKCU", APPROVED_RUN, "MyApp") in service.reg
    items, _ = service.list_items()
    assert next(i for i in items if i.name == "MyApp").enabled is False

    service.set_enabled(item, True)
    assert ( "HKCU", APPROVED_RUN, "MyApp") not in service.reg
    items, _ = service.list_items()
    assert next(i for i in items if i.name == "MyApp").enabled is True


def test_registry_remove_and_undo(tmp_path) -> None:
    service = FakeRegistryService(tmp_path, {("HKCU", RUN_KEY, "Doomed"): (r"C:\bin\doomed.exe", 1)})
    items, _ = service.list_items()
    item = next(i for i in items if i.name == "Doomed")

    result = service.remove(item)
    assert "backup" in result
    assert ("HKCU", RUN_KEY, "Doomed") not in service.reg
    history = service.backup_dir / "history.jsonl"
    assert history.exists() and history.read_text(encoding="utf-8").strip()

    description = service.undo_last()
    assert "doomed" in description.lower() or "registry" in description.lower()
    assert service.reg[("HKCU", RUN_KEY, "Doomed")] == (r"C:\bin\doomed.exe", 1)
    assert not history.read_text(encoding="utf-8").strip()

    with pytest.raises(StartupError):
        service.undo_last()


# ---------- folder service ----------


def _make_folder_service(tmp_path):
    startup = tmp_path / "startup"
    startup.mkdir()
    (startup / "helper.lnk").write_bytes(b"fake")
    return (
        StartupService(
            user_startup_dir=str(startup),
            common_startup_dir=str(tmp_path / "missing"),
            backup_dir=tmp_path / "backup",
            run_sources=(),
        ),
        startup,
    )


def test_folder_items_and_remove_undo(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.startup.service._resolve_lnk", lambda p: p)
    service, startup = _make_folder_service(tmp_path)

    items = service._folder_items(str(startup), "Startup folder")
    assert len(items) == 1
    item = items[0]
    assert item.kind == "folder"
    assert item.name == "helper.lnk"

    result = service.remove(item)
    assert "backup" in result
    assert not (startup / "helper.lnk").exists()

    service.undo_last()
    assert (startup / "helper.lnk").exists()


def test_folder_toggle_uses_approved(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.startup.service._resolve_lnk", lambda p: p)
    service, startup = _make_folder_service(tmp_path)
    item = service._folder_items(str(startup), "Startup folder")[0]

    from app.startup.service import APPROVED_FOLDER

    calls: list[tuple] = []
    monkeypatch.setattr(
        service, "_approved_set",
        lambda h, k, n, d: calls.append(("set", h, k, n, bytes(d))),
    )
    monkeypatch.setattr(
        service, "_approved_delete",
        lambda h, k, n: calls.append(("del", h, k, n)),
    )

    service.set_enabled(item, False)
    assert calls[-1] == ("set", "HKCU", APPROVED_FOLDER, "helper.lnk", DISABLED_FLAG)
    service.set_enabled(item, True)
    assert calls[-1] == ("del", "HKCU", APPROVED_FOLDER, "helper.lnk")


def test_remove_task_raises(tmp_path) -> None:
    item = StartupItem(
        id="task:\\x", name="X", source="Task Scheduler", kind="task",
        command="", location="\\X", enabled=True, impact="Low", impact_reason="",
        task_path="\\X",
    )
    with pytest.raises(StartupError):
        StartupService(backup_dir=tmp_path / "b", run_sources=()).remove(item)

# ---------- live smoke ----------


def test_live_list_items_no_mutation() -> None:
    service = StartupService()
    items, errors = service.list_items()
    assert isinstance(items, list) and isinstance(errors, list)
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids))
    for item in items:
        assert item.impact in ("High", "Medium", "Low")
        assert item.kind in ("registry", "folder", "task")


# ---------- UI ----------


def _wait_until(qapp, cond, timeout: float = 8.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


def _item(name="Discord", enabled=True, kind="registry", impact="High") -> StartupItem:
    return StartupItem(
        id=f"id:{name}", name=name, source="HKCU Run", kind=kind,
        command=r"C:\bin\app.exe", location="HKCU\\Run", enabled=enabled,
        impact=impact, impact_reason="known heavyweight app",
        hive="HKCU", key_path=RUN_KEY, approved_name=name,
    )


class CannedService(StartupService):
    def __init__(self, items: list[StartupItem]) -> None:
        import tempfile

        super().__init__(backup_dir=tempfile.mkdtemp(), run_sources=())
        self.items = items
        self.calls: list[str] = []

    def list_items(self):
        return list(self.items), []

    def set_enabled(self, item, enabled):
        self.calls.append(f"set_enabled:{item.name}:{enabled}")

    def remove(self, item):
        self.calls.append(f"remove:{item.name}")
        return f"removed {item.name}"


class InteractivePage(StartupPage):
    def __init__(self, service):
        super().__init__(service=service)
        self.confirm = True

    def _ask_confirm(self, question, item):
        return self.confirm


def _select_by_name(page, name: str) -> int:
    for row in range(page.table.rowCount()):
        if page.table.item(row, 0).text() == name:
            page.table.selectRow(row)
            return row
    raise AssertionError(f"{name} not in table")


def test_startup_page_loads_and_shows_details(qapp) -> None:
    service = CannedService([_item(), _item("Zoom", impact="Medium")])
    page = InteractivePage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 2)
    assert page.status_label.text().startswith("2 startup")

    _select_by_name(page, "Discord")
    assert page.detail_name.text() == "Discord"
    assert "High" in page.detail_rows["impact"].text()


def test_startup_page_toggle_calls_service(qapp) -> None:
    item = _item()
    service = CannedService([item])
    page = InteractivePage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)

    _select_by_name(page, "Discord")
    assert page.toggle_button.isEnabled()
    page.start_toggle()
    assert _wait_until(qapp, lambda: any(c.startswith("set_enabled:") for c in service.calls))
    assert service.calls[0] == "set_enabled:Discord:False"
    assert _wait_until(qapp, lambda: page._task is None and page.table.rowCount() == 1)


def test_startup_page_remove_calls_service(qapp) -> None:
    service = CannedService([_item()])
    page = InteractivePage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)

    _select_by_name(page, "Discord")
    assert page.remove_button.isEnabled()
    page.start_remove()
    assert _wait_until(qapp, lambda: "remove:Discord" in service.calls)
    assert _wait_until(qapp, lambda: page._task is None)


def test_startup_page_refuses_remove_for_task(qapp) -> None:
    service = CannedService([_item(kind="task")])
    page = InteractivePage(service)
    page.start_refresh()
    assert _wait_until(qapp, lambda: page.table.rowCount() == 1)

    _select_by_name(page, "Discord")
    assert not page.remove_button.isEnabled()
    assert page.toggle_button.isEnabled()
