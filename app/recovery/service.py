from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.changes import ChangeJournal
from app.settings.service import data_root

_STALE_S = 3600.0


@dataclass(frozen=True, slots=True)
class RecoveryIssue:
    kind: str
    path: str
    detail: str
    cleanable: bool = False
    size: int = 0


@dataclass(frozen=True, slots=True)
class RecoveryReport:
    issues: tuple[RecoveryIssue, ...]

    @property
    def cleanable(self) -> int:
        return sum(1 for issue in self.issues if issue.cleanable)

    @property
    def ok(self) -> bool:
        return not self.issues


class RecoveryService:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        journal: ChangeJournal | None = None,
        now: Callable[[], float] | None = None,
        stale_after_s: float = _STALE_S,
    ) -> None:
        self._root = Path(root) if root is not None else data_root()
        self._journal = journal
        self._now = now or time.time
        self._stale_after_s = stale_after_s

    def scan(self) -> RecoveryReport:
        issues: list[RecoveryIssue] = []
        now = self._now()
        try:
            paths = sorted(self._root.rglob("*"))
        except OSError as exc:
            issues.append(RecoveryIssue("scan", str(self._root), str(exc)))
            paths = []
        for path in paths:
            try:
                if path.is_symlink() or not path.is_file():
                    continue
                stat = path.stat()
            except OSError:
                continue
            name = path.name
            if ".corrupt-" in name:
                issues.append(
                    RecoveryIssue("quarantine", str(path), name, size=int(stat.st_size))
                )
            elif name.endswith((".tmp", ".part")) and now - stat.st_mtime >= self._stale_after_s:
                issues.append(
                    RecoveryIssue("temp", str(path), name, cleanable=True, size=int(stat.st_size))
                )
        if self._journal is not None:
            check = self._journal.integrity()
            if not check.ok:
                issues.append(
                    RecoveryIssue(
                        "journal", str(self._journal.store), "; ".join(check.errors[:3])
                    )
                )
        return RecoveryReport(tuple(issues))

    def clean_stale(self, report: RecoveryReport | None = None) -> tuple[int, tuple[str, ...]]:
        current = report or self.scan()
        removed = 0
        errors: list[str] = []
        for issue in current.issues:
            if not issue.cleanable:
                continue
            path = Path(issue.path)
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            except OSError as exc:
                errors.append(f"{issue.path}: {exc}")
                continue
            if self._now() - stat.st_mtime < self._stale_after_s:
                continue
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except OSError as exc:
                errors.append(f"{issue.path}: {exc}")
        return removed, tuple(errors)
