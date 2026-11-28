from __future__ import annotations

import fnmatch
import json
import os
import time
from collections.abc import Iterable
from pathlib import Path

from app.settings import data_root

_GLOB_CHARS = "*?["


def _normalize(value: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.normpath(str(value)))


class CleanerWhitelist:
    def __init__(self, store: str | os.PathLike[str] | None = None) -> None:
        self.store = Path(store) if store is not None else data_root() / "cleaner_whitelist.json"
        self._load_error: str | None = None
        self._patterns = tuple(self._load())

    @property
    def patterns(self) -> tuple[str, ...]:
        return self._patterns

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def add(self, pattern: str | os.PathLike[str]) -> bool:
        normalized = _normalize(pattern)
        if not normalized or normalized in self._patterns:
            return False
        self._patterns = (*self._patterns, normalized)
        self.save()
        return True

    def remove(self, pattern: str | os.PathLike[str]) -> bool:
        normalized = _normalize(pattern)
        if normalized not in self._patterns:
            return False
        self._patterns = tuple(p for p in self._patterns if p != normalized)
        self.save()
        return True

    def is_excluded(self, path: str | os.PathLike[str]) -> bool:
        candidate = _normalize(path)
        for pattern in self._patterns:
            if any(char in pattern for char in _GLOB_CHARS):
                if fnmatch.fnmatch(candidate, pattern):
                    return True
                if os.sep not in pattern and (os.altsep or "") not in pattern:
                    if fnmatch.fnmatch(os.path.basename(candidate), pattern):
                        return True
                    if fnmatch.fnmatch(candidate, f"*{os.sep}{pattern}"):
                        return True
                continue
            if candidate == pattern or candidate.startswith(pattern + os.sep):
                return True
            if not os.path.isabs(pattern):
                if fnmatch.fnmatch(os.path.basename(candidate), pattern):
                    return True
                if fnmatch.fnmatch(candidate, f"*{os.sep}{pattern}"):
                    return True
        return False

    def save(self) -> None:
        self.store.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.store.with_name(self.store.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump({"patterns": list(self._patterns)}, handle, ensure_ascii=False, indent=2)
        os.replace(tmp, self.store)
        self._load_error = None

    def _quarantine(self) -> str | None:
        stamp = time.strftime("%Y%m%d_%H%M%S")
        target = self.store.with_name(f"{self.store.name}.corrupt-{stamp}")
        try:
            self.store.replace(target)
            return str(target)
        except OSError:
            return None

    def _load(self) -> tuple[str, ...]:
        try:
            with self.store.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except FileNotFoundError:
            return ()
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            quarantined = self._quarantine()
            detail = f" moved to {quarantined}" if quarantined else " (could not quarantine)"
            self._load_error = f"whitelist file is corrupt: {exc};{detail}"
            return ()
        except OSError as exc:
            self._load_error = f"whitelist file could not be read: {exc}"
            return ()
        raw = data.get("patterns") if isinstance(data, dict) else data
        if not isinstance(raw, list):
            quarantined = self._quarantine()
            detail = f" moved to {quarantined}" if quarantined else " (could not quarantine)"
            self._load_error = f"whitelist file has an invalid format;{detail}"
            return ()
        values: Iterable[object] = raw
        return tuple(
            dict.fromkeys(
                _normalize(item)
                for item in values
                if isinstance(item, str) and item.strip()
            )
        )
