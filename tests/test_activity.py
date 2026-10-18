from __future__ import annotations

from app.ui.activity import ActivityLog


def test_health_result_survives_restart(qapp) -> None:
    ActivityLog.instance().health = (87, "good")
    ActivityLog._instance = None  # simulate a fresh app start
    assert ActivityLog.instance().health == (87, "good")


def test_health_is_none_without_previous_scan(qapp) -> None:
    assert ActivityLog.instance().health is None
