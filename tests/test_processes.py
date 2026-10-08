from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

from app.processes import (
    ProcessNotFound,
    ProcessService,
    ProtectedProcessError,
    protection_reason,
)
from app.processes.service import ProcessInfo
from app.ui.processes import ProcessPage


def test_list_includes_own_process() -> None:
    processes = ProcessService().list()
    assert processes
    pids = {p.pid for p in processes}
    assert os.getpid() in pids
    assert all(p.pid >= 0 and p.name for p in processes)


def test_details_of_own_process() -> None:
    info = ProcessService().details(os.getpid())
    assert info.pid == os.getpid()
    assert info.username
    assert info.exe
    assert info.protected_reason == "PCOptimizer PRO itself"
    assert info.uptime_seconds is not None


def test_protection_reason_rules() -> None:
    own = os.getpid()
    assert protection_reason(4, "", own)
    assert protection_reason(0, "", own)
    assert protection_reason(1234, "csrss.exe", own)
    assert protection_reason(1234, "System", own)
    assert protection_reason(own, "python.exe", own)
    assert protection_reason(1234, "chrome.exe", own) is None


def test_terminate_own_process_is_blocked() -> None:
    with pytest.raises(ProtectedProcessError):
        ProcessService().terminate(os.getpid())


def test_terminate_system_process_is_blocked() -> None:
    with pytest.raises(ProtectedProcessError):
        ProcessService().terminate(4)


def test_terminate_missing_pid_raises() -> None:
    with pytest.raises(ProcessNotFound):
        ProcessService().terminate(999_999)


def test_terminate_real_subprocess() -> None:
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert ProcessService().terminate(child.pid) is True
        child.wait(timeout=5)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def _info(pid: int, name: str, protected: str | None = None, **overrides) -> ProcessInfo:
    values = dict(
        pid=pid,
        ppid=1,
        name=name,
        username="DIMAS\\user",
        status="running",
        cpu_percent=1.5,
        memory_percent=0.5,
        memory_bytes=10 * 1024**2,
        create_time=time.time() - 60,
        num_threads=4,
        exe="C:\\app\\app.exe",
        cmdline="C:\\app\\app.exe --flag",
        protected_reason=protected,
    )
    values.update(overrides)
    return ProcessInfo(**values)


class StubService:
    def __init__(self, rows: list[ProcessInfo]) -> None:
        self.rows = rows
        self.terminated: list[int] = []

    def list(self) -> list[ProcessInfo]:
        return list(self.rows)

    def details(self, pid: int) -> ProcessInfo:
        return next(r for r in self.rows if r.pid == pid)

    def terminate(self, pid: int, force: bool = False) -> bool:
        info = self.details(pid)
        if info.protected_reason:
            raise ProtectedProcessError(info.protected_reason)
        self.terminated.append(pid)
        return True


class InteractivePage(ProcessPage):
    def __init__(self, service) -> None:
        super().__init__(service=service)
        self.warns: list[tuple[str, str]] = []

    def _ask_confirm(self, info: ProcessInfo) -> bool:
        return True

    def _warn(self, title: str, message: str) -> None:
        self.warns.append((title, message))


def _stub_page(qapp) -> tuple[InteractivePage, StubService]:
    service = StubService(
        [
            _info(500, "app.exe"),
            _info(4, "System", protected="Windows system process"),
            _info(600, "helper.exe"),
        ]
    )
    return InteractivePage(service), service


def test_page_refresh_populates_table(qapp) -> None:
    page, _service = _stub_page(qapp)
    page.refresh()
    assert page.table.rowCount() == 3
    assert page.count_label.text().startswith("3 processes")


def test_page_filter_narrows_rows(qapp) -> None:
    page, _service = _stub_page(qapp)
    page.refresh()
    page.filter.setText("app")
    assert page.table.rowCount() == 1
    page.filter.setText("no-such-thing")
    assert page.table.rowCount() == 0
    page.filter.setText("")
    assert page.table.rowCount() == 3


def test_page_selection_shows_details(qapp) -> None:
    page, _service = _stub_page(qapp)
    page.refresh()
    page._select_pid(500)
    assert "app.exe" in page.detail_name.text()
    assert "PID  500" == page.detail_rows["pid"].text()
    assert page.end_button.isEnabled()
    assert page.protected_badge.isHidden()


def test_page_protected_badge_and_blocked_end(qapp) -> None:
    page, service = _stub_page(qapp)
    page.refresh()
    page._select_pid(4)
    assert "PROTECTED" in page.protected_badge.text()
    page.end_selected()
    assert service.terminated == []
    assert page.warns


def test_page_end_process_flow(qapp) -> None:
    page, service = _stub_page(qapp)
    page.refresh()
    page._select_pid(600)
    page.end_selected()
    assert service.terminated == [600]
    assert "Ended helper.exe" in page.status_label.text()


def test_real_service_page_lists_processes(qapp) -> None:
    page = ProcessPage()
    page.refresh()
    assert page.table.rowCount() > 0
    assert "processes" in page.count_label.text()
