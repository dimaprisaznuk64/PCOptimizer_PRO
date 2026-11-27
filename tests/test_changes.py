from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from app import __version__
from app.changes import (
    GENESIS_HASH,
    ChangeJournal,
    ChangeJournalError,
    checksum_path,
    file_sha256,
    verify_checksum,
    write_checksum,
)


def test_record_builds_hash_chain_and_newest_first(tmp_path) -> None:
    journal = ChangeJournal(store=tmp_path / "system_changes.jsonl")
    first = journal.record(operation="optimizer.apply", outcome="ok", detail="BALANCED")
    second = journal.record(operation="cleaner.clean", outcome="warn", source="cleaner")

    assert first.prev_hash == GENESIS_HASH
    assert second.prev_hash == first.hash
    assert len(first.hash) == 64
    assert [entry.operation for entry in journal.entries()] == [
        "cleaner.clean",
        "optimizer.apply",
    ]
    assert journal.entries(operation="cleaner.clean")[0].source == "cleaner"
    assert journal.entries(outcome="ok")[0].app_version == __version__


def test_integrity_detects_hash_chain_break_and_tampering(tmp_path) -> None:
    store = tmp_path / "system_changes.jsonl"
    journal = ChangeJournal(store=store)
    journal.record(operation="optimizer.apply")
    journal.record(operation="startup.remove")

    assert journal.integrity().ok is True
    assert journal.integrity().entries == 2

    lines = [json.loads(line) for line in store.read_text(encoding="utf-8").splitlines()]
    lines[1]["prev_hash"] = "1" * 64
    store.write_text(
        "\n".join(json.dumps(line, sort_keys=True) for line in lines) + "\n",
        encoding="utf-8",
    )
    errors = journal.integrity().errors
    assert any("broken hash chain" in error for error in errors)

    journal.clear()
    journal.record(operation="optimizer.apply")
    raw = store.read_text(encoding="utf-8")
    store.write_text(raw.replace("optimizer.apply", "cleaner.clean"), encoding="utf-8")
    integrity = journal.integrity()
    assert not integrity.ok
    assert any("checksum mismatch" in error for error in integrity.errors)


def test_clear_removes_entries(tmp_path) -> None:
    journal = ChangeJournal(store=tmp_path / "system_changes.jsonl")
    journal.record(operation="optimizer.apply")
    journal.clear()
    assert journal.entries() == []
    assert journal.integrity().entries == 0


def test_integrity_reports_invalid_utf8_without_raising(tmp_path) -> None:
    store = tmp_path / "system_changes.jsonl"
    store.write_bytes(b'{"operation":"optimizer.apply"}\n\xff\n')
    journal = ChangeJournal(store=store)
    integrity = journal.integrity()
    assert integrity.ok is False
    assert any("UTF-8" in error for error in integrity.errors)
    with pytest.raises(ChangeJournalError):
        journal.record(operation="optimizer.apply")


def test_concurrent_records_keep_hash_chain(tmp_path) -> None:
    journal = ChangeJournal(store=tmp_path / "system_changes.jsonl")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: journal.record(operation="test.record", detail=str(i)), range(160)))

    assert len(journal.entries()) == 160
    assert journal.integrity().ok is True


def test_checksum_helpers_accept_legacy_and_reject_mismatch(tmp_path) -> None:
    target = tmp_path / "backup.json"
    target.write_text('{"profile": "GAMING"}', encoding="utf-8")

    legacy = verify_checksum(target)
    assert legacy.valid is True
    assert legacy.status == "legacy"

    digest = write_checksum(target)
    assert digest == file_sha256(target)
    assert checksum_path(target).read_text(encoding="ascii").strip() == digest
    assert verify_checksum(target).status == "ok"

    target.write_text('{"profile": "BALANCED"}', encoding="utf-8")
    mismatch = verify_checksum(target)
    assert mismatch.valid is False
    assert mismatch.status == "mismatch"


def test_checksum_rejects_invalid_sidecar(tmp_path) -> None:
    target = tmp_path / "history.jsonl"
    target.write_text("{}\n", encoding="utf-8")
    checksum_path(target).write_text("not-a-sha256\n", encoding="ascii")

    result = verify_checksum(target)
    assert result.valid is False
    assert result.status == "mismatch"
