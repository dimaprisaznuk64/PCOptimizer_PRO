from __future__ import annotations

import os
import time
from dataclasses import dataclass

import psutil

PROTECTED_NAMES = frozenset(
    {
        "system",
        "system idle process",
        "registry",
        "memcompression",
        "smss.exe",
        "csrss.exe",
        "wininit.exe",
        "winlogon.exe",
        "services.exe",
        "lsass.exe",
        "lsaiso.exe",
        "svchost.exe",
        "fontdrvhost.exe",
        "dwm.exe",
        "sihost.exe",
        "taskhostw.exe",
        "ctfmon.exe",
        "explorer.exe",
    }
)


class ProcessServiceError(Exception):
    pass


class ProtectedProcessError(ProcessServiceError):
    pass


class ProcessNotFound(ProcessServiceError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessInfo:
    pid: int
    ppid: int | None
    name: str
    username: str | None
    status: str
    cpu_percent: float
    memory_percent: float
    memory_bytes: int
    create_time: float | None
    num_threads: int | None
    exe: str | None
    cmdline: str | None
    protected_reason: str | None

    @property
    def uptime_seconds(self) -> float | None:
        return None if self.create_time is None else max(time.time() - self.create_time, 0.0)


def protection_reason(pid: int, name: str, own_pid: int | None = None) -> str | None:
    own_pid = os.getpid() if own_pid is None else own_pid
    if pid in (0, 3, 4):
        return "Windows system process"
    if pid == own_pid:
        return "PCOptimizer PRO itself"
    if name.lower() in PROTECTED_NAMES:
        return "critical Windows process"
    return None


class ProcessService:
    def __init__(self) -> None:
        self._own_pid = os.getpid()

    def list(self) -> list[ProcessInfo]:
        attrs = [
            "pid",
            "name",
            "username",
            "cpu_percent",
            "memory_percent",
            "memory_info",
            "create_time",
            "exe",
        ]

        results: list[ProcessInfo] = []
        for proc in psutil.process_iter(attrs, ad_value=None):
            try:
                info = proc.info
                pid = info["pid"]
                if pid is None:
                    continue
                name = info["name"] or ""
                memory_info = info.get("memory_info")
                results.append(
                    ProcessInfo(
                        pid=pid,
                        ppid=None,
                        name=name or f"pid-{pid}",
                        username=info.get("username"),
                        status="",
                        cpu_percent=float(info.get("cpu_percent") or 0.0),
                        memory_percent=float(info.get("memory_percent") or 0.0),
                        memory_bytes=int(getattr(memory_info, "rss", 0) or 0),
                        create_time=info.get("create_time"),
                        num_threads=None,
                        exe=info.get("exe"),
                        cmdline=None,
                        protected_reason=protection_reason(pid, name, self._own_pid),
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        results.sort(key=lambda p: (-p.cpu_percent, -p.memory_bytes, p.name.lower()))
        return results

    def details(self, pid: int) -> ProcessInfo:
        try:
            proc = psutil.Process(pid)
            info = proc.as_dict(
                attrs=[
                    "pid",
                    "ppid",
                    "name",
                    "username",
                    "status",
                    "cpu_percent",
                    "memory_percent",
                    "memory_info",
                    "create_time",
                    "num_threads",
                    "exe",
                    "cmdline",
                ],
                ad_value=None,
            )
        except psutil.NoSuchProcess as e:
            raise ProcessNotFound(f"process {pid} no longer exists") from e
        except psutil.AccessDenied as e:
            raise ProcessServiceError(f"access denied for process {pid}") from e

        name = info["name"] or ""
        memory_info = info.get("memory_info")
        cmdline = info.get("cmdline")
        return ProcessInfo(
            pid=pid,
            ppid=info.get("ppid"),
            name=name or f"pid-{pid}",
            username=info.get("username"),
            status=info.get("status") or "?",
            cpu_percent=float(info.get("cpu_percent") or 0.0),
            memory_percent=float(info.get("memory_percent") or 0.0),
            memory_bytes=int(getattr(memory_info, "rss", 0) or 0),
            create_time=info.get("create_time"),
            num_threads=info.get("num_threads"),
            exe=info.get("exe"),
            cmdline=" ".join(cmdline) if cmdline else None,
            protected_reason=protection_reason(pid, name, self._own_pid),
        )

    def terminate(self, pid: int, force: bool = False) -> bool:
        reason = protection_reason(pid, "", self._own_pid)
        if reason:
            raise ProtectedProcessError(reason)
        try:
            proc = psutil.Process(pid)
            name = proc.name()
        except psutil.NoSuchProcess as e:
            raise ProcessNotFound(f"process {pid} no longer exists") from e

        reason = protection_reason(pid, name, self._own_pid)
        if reason:
            raise ProtectedProcessError(reason)

        try:
            if force:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=3)
        except psutil.TimeoutOccurred:
            return False
        except psutil.AccessDenied as e:
            raise ProcessServiceError(
                f"access denied terminating {name} ({pid}) — administrator rights required"
            ) from e
        except psutil.NoSuchProcess:
            pass
        return not proc.is_running()
