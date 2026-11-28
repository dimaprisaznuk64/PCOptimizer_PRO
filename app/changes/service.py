"""Tamper-evident journal for system changes and backup integrity helpers."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import threading
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from app import __version__
from app.settings.service import data_root

SCHEMA_VERSION = 1
GENESIS_HASH = "0" * 64
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_OUTCOMES = frozenset({"ok", "warn", "error"})
_LOG = logging.getLogger(__name__)


class ChangeJournalError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ChangeEntry:
    id: str
    ts: float
    operation: str
    outcome: str
    detail: str = ""
    source: str = ""
    target: str = ""
    backup: str = ""
    backup_sha256: str = ""
    restore_point: str = ""
    app_version: str = ""
    schema: int = SCHEMA_VERSION
    prev_hash: str = GENESIS_HASH
    hash: str = ""

    def _payload(self) -> dict[str, object]:
        return {
            "id": self.id,
            "ts": self.ts,
            "operation": self.operation,
            "outcome": self.outcome,
            "detail": self.detail,
            "source": self.source,
            "target": self.target,
            "backup": self.backup,
            "backup_sha256": self.backup_sha256,
            "restore_point": self.restore_point,
            "app_version": self.app_version,
            "schema": self.schema,
            "prev_hash": self.prev_hash,
        }

    def digest(self) -> str:
        raw = json.dumps(
            self._payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_json(self) -> str:
        data = self._payload()
        data["hash"] = self.hash
        return json.dumps(data, ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> ChangeEntry | None:
        try:
            data = json.loads(line)
            if not isinstance(data, dict):
                return None
            entry = cls(
                id=str(data["id"]),
                ts=float(data["ts"]),
                operation=str(data["operation"]),
                outcome=str(data["outcome"]),
                detail=str(data.get("detail", "")),
                source=str(data.get("source", "")),
                target=str(data.get("target", "")),
                backup=str(data.get("backup", "")),
                backup_sha256=str(data.get("backup_sha256", "")),
                restore_point=str(data.get("restore_point", "")),
                app_version=str(data.get("app_version", "")),
                schema=int(data.get("schema", SCHEMA_VERSION)),
                prev_hash=str(data.get("prev_hash", GENESIS_HASH)),
                hash=str(data.get("hash", "")),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None
        return entry


@dataclass(frozen=True, slots=True)
class JournalIntegrity:
    ok: bool
    entries: int
    errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ChecksumResult:
    valid: bool
    status: str
    detail: str = ""


def is_sha256(value: str) -> bool:
    return bool(_SHA256_RE.fullmatch(value or ""))


def file_sha256(path: str | Path) -> str | None:
    digest = hashlib.sha256()
    try:
        with Path(path).open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError:
        return None
    return digest.hexdigest()


def checksum_path(path: str | Path) -> Path:
    target = Path(path)
    return target.with_name(f"{target.name}.sha256")


def read_checksum(path: str | Path) -> str | None:
    try:
        value = checksum_path(path).read_text(encoding="ascii").strip().casefold()
    except (OSError, UnicodeDecodeError):
        return None
    return value if is_sha256(value) else None


def write_checksum(path: str | Path, digest: str | None = None) -> str:
    target = Path(path)
    computed = digest or file_sha256(target)
    if computed is None or not is_sha256(computed):
        raise OSError(f"cannot checksum {target}")
    side = checksum_path(target)
    side.parent.mkdir(parents=True, exist_ok=True)
    tmp = side.with_name(f".{side.name}.{os.getpid()}.tmp")
    try:
        with tmp.open("w", encoding="ascii") as fh:
            fh.write(f"{computed.casefold()}\n")
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(side)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise
    return computed


def verify_checksum(path: str | Path) -> ChecksumResult:
    target = Path(path)
    if not target.exists():
        return ChecksumResult(False, "missing", str(target))
    expected = read_checksum(target)
    if expected is None:
        if checksum_path(target).exists():
            return ChecksumResult(False, "mismatch", "invalid checksum sidecar")
        # Pre-upgrade backups have no sidecar. Accept them so existing installs
        # keep their undo capability; the next write upgrades them.
        return ChecksumResult(True, "legacy", str(target))
    actual = file_sha256(target)
    if actual is None:
        return ChecksumResult(False, "unreadable", str(target))
    if not hmac.compare_digest(expected, actual.casefold()):
        return ChecksumResult(False, "mismatch", str(target))
    return ChecksumResult(True, "ok", str(target))


class ChangeJournal:
    """Append-only, hash-chained record of operations that change the system."""

    _instance: ChangeJournal | None = None

    def __init__(self, store: str | Path | None = None) -> None:
        self.store = Path(store) if store else data_root() / "system_changes.jsonl"
        self._lock = threading.RLock()

    @classmethod
    def instance(cls) -> ChangeJournal:
        if cls._instance is None:
            cls._instance = ChangeJournal()
        return cls._instance

    def record(
        self,
        *,
        operation: str,
        outcome: str = "ok",
        detail: str = "",
        source: str = "",
        target: str = "",
        backup: str = "",
        backup_sha256: str = "",
        restore_point: str = "",
    ) -> ChangeEntry:
        if outcome not in _OUTCOMES:
            raise ValueError(f"unknown outcome {outcome}")
        with self._lock:
            entries, errors = self._load()
            if errors:
                raise ChangeJournalError("cannot append to a journal with integrity errors")
            prev = entries[-1].hash if entries else GENESIS_HASH
            entry = ChangeEntry(
                id=uuid.uuid4().hex,
                ts=time.time(),
                operation=operation,
                outcome=outcome,
                detail=detail,
                source=source,
                target=target,
                backup=backup,
                backup_sha256=backup_sha256,
                restore_point=restore_point,
                app_version=__version__,
                prev_hash=prev,
            )
            entry = replace(entry, hash=entry.digest())
            self.store.parent.mkdir(parents=True, exist_ok=True)
            with self.store.open("a", encoding="utf-8") as fh:
                fh.write(entry.to_json() + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            return entry

    def try_record(
        self,
        *,
        operation: str,
        outcome: str = "ok",
        detail: str = "",
        source: str = "",
        target: str = "",
        backup: str = "",
        backup_sha256: str = "",
        restore_point: str = "",
    ) -> bool:
        """Record a change without turning an already-applied action into a failure.

        A corrupt journal is still visible through ``integrity()`` in Operations;
        refusing to write must not make a completed system change look undone.
        """
        try:
            self.record(
                operation=operation,
                outcome=outcome,
                detail=detail,
                source=source,
                target=target,
                backup=backup,
                backup_sha256=backup_sha256,
                restore_point=restore_point,
            )
        except (ChangeJournalError, OSError) as exc:
            _LOG.warning("system change journal write failed (%s): %s", operation, exc)
            return False
        return True

    def entries(
        self,
        *,
        limit: int | None = None,
        operation: str | None = None,
        outcome: str | None = None,
    ) -> list[ChangeEntry]:
        with self._lock:
            entries, _errors = self._load()
        result = list(reversed(entries))
        if operation is not None:
            result = [e for e in result if e.operation == operation]
        if outcome is not None:
            result = [e for e in result if e.outcome == outcome]
        return result if limit is None else result[:limit]

    def integrity(self) -> JournalIntegrity:
        with self._lock:
            entries, errors = self._load()
        return JournalIntegrity(ok=not errors, entries=len(entries), errors=errors)

    def clear(self) -> None:
        """Testing helper — the UI never exposes this for the audit trail."""
        with self._lock:
            try:
                self.store.unlink(missing_ok=True)
            except OSError:
                pass

    def _load(self) -> tuple[list[ChangeEntry], tuple[str, ...]]:
        try:
            lines = self.store.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return [], ()
        except UnicodeDecodeError as exc:
            return [], (f"journal is not valid UTF-8: {exc}",)
        except OSError as exc:
            return [], (f"cannot read journal: {exc}",)
        entries: list[ChangeEntry] = []
        errors: list[str] = []
        prev = GENESIS_HASH
        for number, line in enumerate(lines, 1):
            if not line.strip():
                continue
            entry = ChangeEntry.from_json(line)
            if entry is None:
                errors.append(f"line {number}: corrupt entry")
                continue
            if entry.prev_hash != prev:
                errors.append(f"line {number}: broken hash chain")
            expected = entry.digest()
            if not is_sha256(entry.hash) or not hmac.compare_digest(entry.hash, expected):
                errors.append(f"line {number}: checksum mismatch")
            prev = entry.hash
            entries.append(entry)
        return entries, tuple(errors)
