from __future__ import annotations

from app.sensors.win_memory import CommitCharge, read_commit_charge


def test_read_commit_charge_uses_injected_status() -> None:
    assert read_commit_charge(lambda: (100, 40)) == CommitCharge(limit=100, available=40, used=60)


def test_read_commit_charge_handles_missing_or_zero_limit() -> None:
    assert read_commit_charge(lambda: None) is None
    assert read_commit_charge(lambda: (0, 0)) is None


def test_read_commit_charge_clamps_available() -> None:
    assert read_commit_charge(lambda: (100, 150)) == CommitCharge(limit=100, available=100, used=0)
    assert read_commit_charge(lambda: (100, -5)) == CommitCharge(limit=100, available=0, used=100)
