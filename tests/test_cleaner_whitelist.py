from __future__ import annotations

import json
import os
from pathlib import Path

from app.cleaner import CleanerWhitelist


def test_default_store_uses_data_root() -> None:
    root = Path(os.environ["PCOPTIMIZER_DATA"])

    whitelist = CleanerWhitelist()

    assert whitelist.store == root / "cleaner_whitelist.json"


def test_add_remove_persists_atomically(tmp_path) -> None:
    store = tmp_path / "whitelist.json"
    whitelist = CleanerWhitelist(store)

    assert whitelist.add("keep.bin") is True
    assert whitelist.add("keep.bin") is False
    assert json.loads(store.read_text(encoding="utf-8"))["patterns"] == [
        os.path.normcase(os.path.normpath("keep.bin"))
    ]
    assert not store.with_name("whitelist.json.tmp").exists()
    assert CleanerWhitelist(store).patterns == whitelist.patterns

    reloaded = CleanerWhitelist(store)
    assert reloaded.remove("keep.bin") is True
    assert reloaded.remove("keep.bin") is False
    assert reloaded.patterns == ()


def test_is_excluded_normalizes_paths_and_fnmatch(tmp_path) -> None:
    root = tmp_path / "Cache"
    nested = root / "nested"
    nested.mkdir(parents=True)
    whitelist = CleanerWhitelist(tmp_path / "whitelist.json")
    whitelist.add(str(root / "exact.bin"))
    whitelist.add(str(root / "skip_*.tmp"))
    whitelist.add("blocked.log")
    whitelist.add(str(nested))

    assert whitelist.is_excluded(root / "exact.bin")
    assert whitelist.is_excluded(str(nested).replace(os.sep, "/"))
    assert whitelist.is_excluded(root / "skip_12.tmp")
    assert whitelist.is_excluded(tmp_path / "blocked.log")
    assert whitelist.is_excluded(nested / "any.bin")
    assert not whitelist.is_excluded(root / "other.bin")


def test_corrupt_store_starts_empty(tmp_path) -> None:
    store = tmp_path / "whitelist.json"
    store.write_text("{not-json", encoding="utf-8")

    assert CleanerWhitelist(store).patterns == ()
