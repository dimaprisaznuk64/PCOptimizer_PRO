from __future__ import annotations

from pathlib import Path

import pytest

from app.cleaner import CleanTarget, detect_leftovers, list_leftover_candidates
from app.cleaner.leftovers import _CACHE_FOLDERS

_ALLOWED = {name.casefold() for name in _CACHE_FOLDERS}


@pytest.fixture()
def leftover_roots(tmp_path):
    local = tmp_path / "local"
    appdata = tmp_path / "roaming"
    cache_dirs = (
        local / "Discord" / "Cache",
        local / "Discord" / "Code Cache",
        local / "NVIDIA" / "GPUCache",
        appdata / "Slack" / "Cache",
        local / "Program Files" / "Fake" / "Cache",
    )
    for path in cache_dirs:
        path.mkdir(parents=True)
    (local / "Discord" / "save.dat").write_text("keep me", encoding="utf-8")
    (local / "Discord" / "Cache" / "index.bin").write_bytes(b"x" * 32)
    return local, appdata


def test_list_leftover_candidates_only_curated_cache_dirs(leftover_roots) -> None:
    local, appdata = leftover_roots

    candidates = list_leftover_candidates([local, appdata])

    paths = [candidate.path for candidate in candidates]
    assert len(paths) == len(set(paths))
    assert all(Path(path).name.casefold() in _ALLOWED for path in paths)
    assert all("program files" not in path.lower() for path in paths)
    assert all(not path.endswith("save.dat") for path in paths)
    expected = {
        str(local / "Discord" / "Cache"),
        str(local / "Discord" / "Code Cache"),
        str(local / "NVIDIA" / "GPUCache"),
        str(appdata / "Slack" / "Cache"),
    }
    assert set(paths) == expected


def test_detect_leftovers_returns_clean_targets(leftover_roots) -> None:
    local, appdata = leftover_roots

    targets = detect_leftovers([local, appdata])

    assert targets
    assert all(isinstance(target, CleanTarget) for target in targets)
    assert all(target.category == "Leftovers" for target in targets)
    assert all(target.kind == "files" for target in targets)
    assert all(target.selected_by_default is False for target in targets)
    candidate_paths = {candidate.path for candidate in list_leftover_candidates([local, appdata])}
    assert all(target.paths[0] in candidate_paths for target in targets)


def test_default_roots_come_from_environment(leftover_roots, monkeypatch) -> None:
    local, appdata = leftover_roots
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    monkeypatch.setenv("APPDATA", str(appdata))

    detected = detect_leftovers()

    assert {target.paths[0] for target in detected} == {
        str(local / "Discord" / "Cache"),
        str(local / "Discord" / "Code Cache"),
        str(local / "NVIDIA" / "GPUCache"),
        str(appdata / "Slack" / "Cache"),
    }


def test_list_leftover_candidates_is_read_only(leftover_roots) -> None:
    local, appdata = leftover_roots
    cache_file = local / "Discord" / "Cache" / "index.bin"
    save_file = local / "Discord" / "save.dat"

    list_leftover_candidates([local, appdata])

    assert cache_file.exists()
    assert save_file.exists()
