from __future__ import annotations

import glob
import hashlib
import os
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.cleaner.service import CleanTarget, is_safe_root

_CACHE_FOLDERS = frozenset({"cache", "code cache", "gpucache"})
_VENDOR_PATTERNS = (
    ("Google", "Chrome", "User Data", "*", "Cache"),
    ("Google", "Chrome", "User Data", "*", "Code Cache"),
    ("Google", "Chrome", "User Data", "*", "GPUCache"),
    ("Microsoft", "Edge", "User Data", "*", "Cache"),
    ("Microsoft", "Edge", "User Data", "*", "Code Cache"),
    ("Microsoft", "Edge", "User Data", "*", "GPUCache"),
    ("Discord", "Cache"),
    ("Discord", "Code Cache"),
    ("Discord", "GPUCache"),
    ("Slack", "Cache"),
    ("Slack", "Code Cache"),
    ("Slack", "GPUCache"),
    ("Microsoft", "Teams", "Cache"),
    ("Microsoft", "Teams", "Code Cache"),
    ("Microsoft", "Teams", "GPUCache"),
    ("Epic Games", "Launcher", "Cache"),
    ("Unity", "Cache"),
    ("Unity", "GPUCache"),
    ("NVIDIA", "GPUCache"),
    ("AMD", "GPUCache"),
    ("JetBrains", "*", "Cache"),
    ("JetBrains", "*", "Code Cache"),
    ("JetBrains", "*", "GPUCache"),
)


@dataclass(frozen=True, slots=True)
class LeftoverCandidate:
    id: str
    name: str
    vendor: str
    path: str
    target: CleanTarget


def _default_roots() -> tuple[str, ...]:
    env = os.environ
    return tuple(value for value in (env.get("LOCALAPPDATA", ""), env.get("APPDATA", "")) if value)


def _vendor_label(parts: Sequence[str]) -> str:
    if len(parts) > 1 and parts[0] in {"Google", "Microsoft"} and parts[1] in {"Chrome", "Edge"}:
        return f"{parts[0]} {parts[1]}"
    return parts[0]


def _candidate_id(path: str) -> str:
    key = os.path.normcase(os.path.normpath(path)).encode("utf-8", "surrogatepass")
    return "leftover_" + hashlib.sha1(key).hexdigest()[:12]


def _is_forbidden(path: Path) -> bool:
    text = str(path).lower()
    return "program files" in text or "program files (x86)" in text


def list_leftover_candidates(roots: Sequence[str | os.PathLike[str]] | str | None = None) -> list[LeftoverCandidate]:
    if roots is None:
        root_values: Sequence[str | os.PathLike[str]] = _default_roots()
    elif isinstance(roots, (str, os.PathLike)):
        root_values = (roots,)
    else:
        root_values = roots

    found: dict[str, LeftoverCandidate] = {}
    for root_value in root_values:
        root = Path(root_value)
        if _is_forbidden(root):
            continue
        for parts in _VENDOR_PATTERNS:
            pattern = str(root.joinpath(*parts))
            for match in glob.iglob(pattern):
                path = Path(match)
                if path.name.casefold() not in _CACHE_FOLDERS:
                    continue
                if not path.is_dir() or _is_forbidden(path) or not is_safe_root(str(path)):
                    continue
                normalized = os.path.normcase(os.path.normpath(str(path)))
                if normalized in found:
                    continue
                vendor = _vendor_label(parts)
                name = f"{vendor} {path.name}"
                found[normalized] = LeftoverCandidate(
                    id=_candidate_id(str(path)),
                    name=name,
                    vendor=vendor,
                    path=str(path),
                    target=CleanTarget(
                        id=_candidate_id(str(path)),
                        name=name,
                        category="Leftovers",
                        paths=(str(path),),
                        note=f"detected {path.name} cache",
                        selected_by_default=False,
                    ),
                )
    return sorted(found.values(), key=lambda candidate: candidate.path.lower())


def detect_leftovers(
    roots: Sequence[str | os.PathLike[str]] | str | None = None,
) -> list[CleanTarget]:
    return [candidate.target for candidate in list_leftover_candidates(roots)]
