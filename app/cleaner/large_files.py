from __future__ import annotations

import hashlib
import os
from pathlib import Path

from app.disk.service import DEFAULT_LIMIT, DEFAULT_MIN_SIZE, DiskAnalyzer, LargeFile

from .service import CleanTarget


def scan_large_files(
    folder: str | os.PathLike[str],
    min_bytes: int = DEFAULT_MIN_SIZE,
    limit: int = DEFAULT_LIMIT,
    *,
    analyzer: DiskAnalyzer | None = None,
    errors: list[str] | None = None,
) -> list[LargeFile]:
    scanner = analyzer or DiskAnalyzer()
    return scanner.find_large_files(str(folder), min_bytes, limit, errors=errors)


def make_large_files_target(
    folder: str | os.PathLike[str],
    min_bytes: int = DEFAULT_MIN_SIZE,
    limit: int = DEFAULT_LIMIT,
) -> CleanTarget:
    text = str(folder)
    key = os.path.normcase(os.path.normpath(os.path.abspath(text)))
    key += f"|{min_bytes}|{limit}"
    digest = hashlib.sha1(key.encode("utf-8", "surrogatepass")).hexdigest()[:12]
    name = Path(text).name or text
    return CleanTarget(
        id=f"large_files_{digest}",
        name=f"Large files: {name}",
        category="Tools",
        kind="preview",
        paths=(text,),
        note=f"preview only · >= {min_bytes} bytes · top {limit}",
        selected_by_default=False,
    )
