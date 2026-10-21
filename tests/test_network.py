from __future__ import annotations

import time

import pytest

from app.network import CheckResult, NetworkError, NetworkService, PingResult
from app.network.service import parse_ping
from app.ui.network import NetworkPage


def _wait_until(qapp, cond, timeout: float = 12.0) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        qapp.processEvents()
        if cond():
            return True
        time.sleep(0.02)
    return False


# ---------- ping parsing (en + uk) ----------

ENGLISH = """Pinging 1.1.1.1 with 32 bytes of data:
Reply from 1.1.1.1: bytes=32 time=11ms TTL=115
Reply from 1.1.1.1: bytes=32 time=9ms TTL=115
Reply from 1.1.1.1: bytes=32 time=10ms TTL=115
Reply from 1.1.1.1: bytes=32 time=12ms TTL=115

Ping statistics for 1.1.1.1:
    Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),
Round trip times in milli-seconds:
    Minimum = 9ms, Maximum = 12ms, Average = 10ms
"""

UKRAINIAN = """Пінг 1.1.1.1 з 32 байтами даних:
Від 1.1.1.1: отримано байтів=32 час=15мс TTL=115
Від 1.1.1.1: отримано байтів=32 час=13мс TTL=115

Статистика пінгу для 1.1.1.1:
    Пакетів: надіслано = 4, отримано = 2, втрачено = 2 (50% втрата),
Мінімальний = 13мс, Максимальний = 15мс, Середній = 14мс
"""

TIMEOUT = """Pinging 10.255.255.1 with 32 bytes of data:
Request timed out.
Request timed out.
Request timed out.
Request timed out.

Ping statistics for 10.255.255.1:
    Packets: Sent = 4, Received = 0, Lost = 4 (100% loss),
"""


def test_parse_ping_english() -> None:
    result = parse_ping("1.1.1.1", ENGLISH, 4, 0)
    assert result.error is None
    assert result.received == 4
    assert result.min_ms == 9
    assert result.max_ms == 12
    assert result.avg_ms == 10
    assert result.loss_percent == 0.0


def test_parse_ping_ukrainian() -> None:
    result = parse_ping("1.1.1.1", UKRAINIAN, 4, 0)
    assert result.error is None
    assert result.received == 2
    assert result.min_ms == 13
    assert result.max_ms == 15
    assert result.avg_ms == 14
    assert result.loss_percent == 50.0


def test_parse_ping_timeout() -> None:
    result = parse_ping("10.255.255.1", TIMEOUT, 4, 1)
    assert result.received == 0
    assert result.loss_percent == 100.0
    assert result.error is not None
    assert result.avg_ms is None


# ---------- service with fakes ----------


class FakeNetwork:
    def __init__(self) -> None:
        self.commands: list[tuple[str, ...]] = []
        self.ping_output = ENGLISH
        self.ping_code = 0
        self.gateway_value: str | None = "192.168.1.1"
        self.stats: dict = {"Ethernet": True, "Wi-Fi": True, "Loopback": False}
        self.dns_ok = True
        self.proxy = 0
        self.flushed = 0
        self.fail_flush = False

    def run(self, args, timeout):
        args = tuple(str(a) for a in args)
        self.commands.append(args)
        if args and args[0] == "ping":
            return self.ping_code, self.ping_output
        return 0, ""

    def resolver(self, host: str) -> None:
        if not self.dns_ok:
            raise OSError("name or service not known")

    def if_stats(self):
        return dict(self.stats)

    def gateway(self):
        return self.gateway_value

    def reg_get(self, hive, key, name):
        assert name == "ProxyEnable"
        return self.proxy

    def flush(self):
        if self.fail_flush:
            raise NetworkError("access denied")
        self.flushed += 1

    def make_service(self) -> NetworkService:
        return NetworkService(
            run=self.run,
            resolver=self.resolver,
            if_stats=self.if_stats,
            gateway=self.gateway,
            reg_get=self.reg_get,
            flush=self.flush,
        )


@pytest.fixture()
def fake() -> FakeNetwork:
    return FakeNetwork()


def test_ping_uses_fake_runner(fake) -> None:
    result = fake.make_service().ping("1.1.1.1", 4)
    assert result.received == 4
    assert fake.commands[0] == ("ping", "-n", "4", "1.1.1.1")


def test_ping_empty_host_raises(fake) -> None:
    with pytest.raises(NetworkError):
        fake.make_service().ping("   ")


def test_ping_no_reply_reports_error(fake) -> None:
    fake.ping_output = TIMEOUT
    fake.ping_code = 1
    result = fake.make_service().ping("10.255.255.1", 4)
    assert result.error is not None
    assert result.loss_percent == 100.0


def test_diagnostics_all_ok(fake) -> None:
    checks = fake.make_service().diagnostics()
    by_name = {c.name: c for c in checks}
    assert {"Adapters", "Gateway", "DNS", "Internet", "Proxy"} <= set(by_name)
    assert all(c.ok for c in checks)
    assert by_name["Gateway"].detail == "192.168.1.1"


def test_diagnostics_no_adapters(fake) -> None:
    fake.stats = {}
    checks = fake.make_service().diagnostics()
    adapters = next(c for c in checks if c.name == "Adapters")
    assert adapters.ok is False


def test_diagnostics_no_gateway(fake) -> None:
    fake.gateway_value = None
    checks = fake.make_service().diagnostics()
    gw = next(c for c in checks if c.name == "Gateway")
    assert gw.ok is False


def test_diagnostics_dns_failure(fake) -> None:
    fake.dns_ok = False
    checks = fake.make_service().diagnostics()
    dns = next(c for c in checks if c.name == "DNS")
    assert dns.ok is False
    assert "failed" in dns.detail


def test_diagnostics_internet_fail(fake) -> None:
    fake.ping_output = TIMEOUT
    fake.ping_code = 1
    checks = fake.make_service().diagnostics()
    net = next(c for c in checks if c.name == "Internet")
    assert net.ok is False


def test_diagnostics_proxy_info(fake) -> None:
    fake.proxy = 1
    checks = fake.make_service().diagnostics()
    proxy = next(c for c in checks if c.name == "Proxy")
    assert proxy.ok is True
    assert "enabled" in proxy.detail


def test_flush_dns_success(fake) -> None:
    service = fake.make_service()
    message = service.flush_dns()
    assert fake.flushed == 1
    assert "flushed" in message.lower()


def test_flush_dns_failure(fake) -> None:
    fake.fail_flush = True
    with pytest.raises(NetworkError):
        fake.make_service().flush_dns()


# ---------- UI ----------


class FakeNetworkService(NetworkService):
    def __init__(self) -> None:
        super().__init__(
            run=lambda args, timeout: (0, ENGLISH),
            resolver=lambda host: None,
            if_stats=lambda: {"Ethernet": True},
            gateway=lambda: "192.168.1.1",
            reg_get=lambda h, k, n: 0,
            flush=lambda: None,
        )
        self.ping_calls = 0
        self.diag_calls = 0
        self.flush_calls = 0

    def ping(self, host: str = "", count: int = 4) -> PingResult:
        self.ping_calls += 1
        return parse_ping(host or "1.1.1.1", ENGLISH, 4, 0)

    def diagnostics(self) -> list[CheckResult]:
        self.diag_calls += 1
        return [
            CheckResult("Adapters", True, "1 up: Ethernet"),
            CheckResult("Gateway", True, "192.168.1.1"),
            CheckResult("Internet", True, "1.1.1.1 avg 10ms"),
        ]

    def flush_dns(self) -> str:
        self.flush_calls += 1
        return "DNS cache flushed"


def test_network_page_ping(qapp) -> None:
    service = FakeNetworkService()
    page = NetworkPage(service=service)
    page.start_ping()
    assert _wait_until(qapp, lambda: page.ping_table.rowCount() == 1)
    assert service.ping_calls == 1
    assert "avg 10ms" in page.avg_label.text()
    assert "0%" in page.loss_label.text()
    assert page.ping_table.item(0, 1).text() == "1.1.1.1"


def test_network_page_diagnostics(qapp) -> None:
    service = FakeNetworkService()
    page = NetworkPage(service=service)
    page.start_diagnostics()
    assert _wait_until(qapp, lambda: page.diag_table.rowCount() == 3)
    assert "3 checks passed" in page.status_label.text()
    statuses = {page.diag_table.item(r, 1).text() for r in range(3)}
    assert statuses == {"OK"}


def test_network_page_flush(qapp) -> None:
    service = FakeNetworkService()
    page = NetworkPage(service=service)
    page.start_flush()
    assert _wait_until(qapp, lambda: "flushed" in page.status_label.text().lower())
    assert service.flush_calls == 1


def test_network_page_busy_disables_buttons(qapp) -> None:
    service = FakeNetworkService()
    page = NetworkPage(service=service)
    page.start_ping()
    assert not page.ping_button.isEnabled()
    assert not page.diag_button.isEnabled()
    assert not page.flush_button.isEnabled()
    assert _wait_until(qapp, lambda: page.ping_table.rowCount() == 1)
    assert page.ping_button.isEnabled()
