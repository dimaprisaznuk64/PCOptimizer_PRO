"""Track a live session marker so the next start can report an unclean exit."""

from __future__ import annotations

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.settings.service import data_root

SESSION_NAME = "session.json"
_STALE_AFTER_S = 300.0
_HEARTBEAT_EVERY_S = 30.0


@dataclass(frozen=True, slots=True)
class UncleanExit:
    pid: int
    heartbeat: float
    version: str


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
    except ImportError:
        return True
    try:
        return bool(psutil.pid_exists(pid))
    except (OSError, ValueError):
        return True


@dataclass(frozen=True, slots=True)
class _Marker:
    pid: int
    started: float
    heartbeat: float
    version: str


class CrashTracker:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        now: Callable[[], float] | None = None,
        pid: int | None = None,
        version: str = "",
        alive: Callable[[int], bool] | None = None,
        stale_after_s: float = _STALE_AFTER_S,
        heartbeat_every_s: float = _HEARTBEAT_EVERY_S,
    ) -> None:
        self._path = (Path(root) if root is not None else data_root()) / SESSION_NAME
        self._now = now or time.time
        self._pid = os.getpid() if pid is None else pid
        self._version = version
        self._alive = alive or _pid_alive
        self._stale_after_s = stale_after_s
        self._heartbeat_every_s = heartbeat_every_s
        self._last_write = 0.0

    def _read(self) -> _Marker | None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(payload, dict):
            return None
        try:
            marker = _Marker(
                pid=int(payload["pid"]),
                started=float(payload["started"]),
                heartbeat=float(payload["heartbeat"]),
                version=str(payload.get("version", "")),
            )
        except (KeyError, TypeError, ValueError):
            return None
        if marker.pid < 0 or marker.heartbeat <= 0 or marker.started <= 0:
            return None
        return marker

    def _write(self, started: float) -> None:
        payload = {
            "pid": self._pid,
            "started": started,
            "heartbeat": self._now(),
            "version": self._version,
        }
        tmp = self._path.with_name(f"{self._path.name}.tmp")
        written = False
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(payload), encoding="utf-8")
            tmp.replace(self._path)
            written = True
        finally:
            if written:
                self._last_write = self._now()
            try:
                tmp.unlink(missing_ok=True)
            except OSError:
                pass

    def _quarantine(self) -> None:
        try:
            self._path.replace(self._path.with_name(f"{SESSION_NAME}.corrupt-{int(self._now())}"))
        except OSError:
            pass

    def start(self) -> UncleanExit | None:
        """Inspect the previous marker, then claim the marker for this session."""
        now = self._now()
        previous = self._read()
        if previous is None:
            if self._path.exists():
                self._quarantine()
        else:
            if now - previous.heartbeat >= self._stale_after_s and not self._alive(previous.pid):
                crash = UncleanExit(
                    pid=previous.pid,
                    heartbeat=previous.heartbeat,
                    version=previous.version,
                )
                self._write(previous.started)
                return crash
        self._write(now)
        return None

    def heartbeat(self, *_args: object) -> None:
        """Refresh the marker; safe to connect directly to a snapshot signal."""
        now = self._now()
        if now - self._last_write < self._heartbeat_every_s:
            return
        current = self._read()
        if current is None or current.pid != self._pid:
            return
        self._write(current.started)

    def finish(self) -> bool:
        """Remove our marker on a clean exit; never delete another session's marker."""
        current = self._read()
        if current is not None and current.pid != self._pid:
            return False
        try:
            self._path.unlink(missing_ok=True)
        except OSError:
            return False
        return True
