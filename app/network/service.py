from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass
from typing import Callable, Sequence

DEFAULT_PING_HOST = "1.1.1.1"
DNS_PROBE_HOST = "www.microsoft.com"

_TIME_RE = re.compile(r"(?:time|час)\s*[=<]\s*(\d+)", re.IGNORECASE)
_LOSS_RE = re.compile(r"\(\s*(\d+)\s*%", re.IGNORECASE)
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


class NetworkError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class PingResult:
    host: str
    sent: int
    received: int
    min_ms: int | None
    avg_ms: int | None
    max_ms: int | None
    loss_percent: float
    error: str | None = None


@dataclass(frozen=True, slots=True)
class CheckResult:
    name: str
    ok: bool
    detail: str


def parse_ping(host: str, output: str, count: int, returncode: int) -> PingResult:
    times = [int(m) for m in _TIME_RE.findall(output)]
    received = len(times)
    loss_match = _LOSS_RE.search(output)
    if loss_match and received == 0:
        loss = float(loss_match.group(1))
    elif count > 0:
        loss = round(100.0 * (count - received) / count, 1)
    else:
        loss = 0.0
    error: str | None = None
    if received == 0:
        error = "no reply"
        if returncode != 0:
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if lines:
                error = lines[0][:120]
    return PingResult(
        host=host,
        sent=count,
        received=received,
        min_ms=min(times) if times else None,
        avg_ms=round(sum(times) / len(times)) if times else None,
        max_ms=max(times) if times else None,
        loss_percent=loss,
        error=error,
    )


class NetworkService:
    def __init__(
        self,
        *,
        run: Callable[[Sequence[str], float], tuple[int, str]] | None = None,
        resolver: Callable[[str], None] | None = None,
        if_stats: Callable[[], dict] | None = None,
        gateway: Callable[[], str | None] | None = None,
        reg_get: Callable[[str, str, str], int] | None = None,
        flush: Callable[[], None] | None = None,
    ) -> None:
        self._run = run or self._default_run
        self._resolver = resolver or self._default_resolver
        self._if_stats = if_stats or self._default_if_stats
        self._gateway = gateway or self._default_gateway
        self._reg_get = reg_get or self._default_reg_get
        self._flush = flush or self._default_flush

    # ---------- ping ----------

    def ping(self, host: str = DEFAULT_PING_HOST, count: int = 4) -> PingResult:
        host = host.strip()
        if not host:
            raise NetworkError("host is required")
        timeout = max(10.0, count * 3.0 + 5.0)
        code, out = self._run(("ping", "-n", str(count), host), timeout)
        return parse_ping(host, out, count, code)

    # ---------- diagnostics ----------

    def diagnostics(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        try:
            stats = self._if_stats()
            up = [name for name, isup in stats.items() if isup]
            if up:
                results.append(CheckResult("Adapters", True, f"{len(up)} up: {', '.join(up[:3])}"))
            else:
                results.append(CheckResult("Adapters", False, "no active adapters"))
        except Exception as e:
            results.append(CheckResult("Adapters", False, str(e)))

        try:
            gw = self._gateway()
            if gw:
                results.append(CheckResult("Gateway", True, gw))
            else:
                results.append(CheckResult("Gateway", False, "no default gateway found"))
        except Exception as e:
            results.append(CheckResult("Gateway", False, str(e)))

        try:
            started = time.perf_counter()
            self._resolver(DNS_PROBE_HOST)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            results.append(CheckResult("DNS", True, f"{DNS_PROBE_HOST} resolved in {elapsed_ms}ms"))
        except Exception as e:
            results.append(CheckResult("DNS", False, f"resolution failed: {e}"))

        result = self.ping(DEFAULT_PING_HOST, 2)
        if result.error is None and result.received > 0:
            results.append(
                CheckResult("Internet", True, f"{DEFAULT_PING_HOST} avg {result.avg_ms}ms")
            )
        else:
            results.append(CheckResult("Internet", False, result.error or "no reply"))

        try:
            proxy = bool(self._reg_get(
                "HKCU",
                r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                "ProxyEnable",
            ))
            results.append(
                CheckResult(
                    "Proxy",
                    True,
                    "system proxy enabled — check settings if browsing fails"
                    if proxy
                    else "no system proxy",
                )
            )
        except Exception as e:
            results.append(CheckResult("Proxy", False, str(e)))

        return results

    def flush_dns(self) -> str:
        try:
            self._flush()
        except Exception as e:
            raise NetworkError(f"flush failed: {e}") from e
        return "DNS cache flushed"

    # ---------- defaults ----------

    @staticmethod
    def _default_run(args: Sequence[str], timeout: float) -> tuple[int, str]:
        import subprocess

        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            proc = subprocess.run(
                list(args),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                creationflags=creationflags,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            return 1, str(e)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

    @staticmethod
    def _default_resolver(host: str) -> None:
        socket.getaddrinfo(host, 443)

    @staticmethod
    def _default_if_stats() -> dict:
        import psutil

        return {name: bool(s.isup) for name, s in psutil.net_if_stats().items()}

    @staticmethod
    def _default_gateway() -> str | None:
        script = (
            "Get-NetRoute -DestinationPrefix '0.0.0.0/0' "
            "| Select-Object -First 1 -ExpandProperty NextHop"
        )
        code, out = NetworkService._default_run(
            (
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command", script,
            ),
            20.0,
        )
        if code != 0:
            return None
        match = _IPV4_RE.search(out)
        return match.group(0) if match else None

    @staticmethod
    def _default_reg_get(hive: str, key: str, name: str) -> int:
        import winreg

        root = winreg.HKEY_CURRENT_USER if hive == "HKCU" else winreg.HKEY_LOCAL_MACHINE
        with winreg.OpenKey(root, key, 0, winreg.KEY_READ) as handle:
            data, _vtype = winreg.QueryValueEx(handle, name)
        return int(data)

    @staticmethod
    def _default_flush() -> None:
        code, out = NetworkService._default_run(("ipconfig", "/flushdns"), 15.0)
        if code != 0:
            raise NetworkError(out.strip() or f"exit {code}")
