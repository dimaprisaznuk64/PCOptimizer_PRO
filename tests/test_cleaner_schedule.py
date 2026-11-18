from __future__ import annotations

import json
import os
from pathlib import Path

from app.cleaner import CleanerSchedule, CleanerScheduler

_DAY = 86400


def test_default_store_and_cadence() -> None:
    root = Path(os.environ["PCOPTIMIZER_DATA"])

    scheduler = CleanerScheduler(now=lambda: 1000.0)

    assert scheduler.store == root / "cleaner_schedule.json"
    assert scheduler.enabled is False
    assert scheduler.cadence == "weekly"
    assert scheduler.cadence_days == 7
    assert scheduler.target_ids == ()
    assert scheduler.last_run == 0.0


def test_save_load_roundtrip_atomically(tmp_path) -> None:
    store = tmp_path / "schedule.json"
    scheduler = CleanerScheduler(store=store, now=lambda: 1000.0)
    scheduler.set_enabled(True)
    scheduler.set_cadence("daily")
    scheduler.set_target_ids(["user_temp", "pip_cache", "user_temp"])
    scheduler.mark_run()

    data = json.loads(store.read_text(encoding="utf-8"))
    assert data["enabled"] is True
    assert data["cadence_days"] == 1
    assert data["target_ids"] == ["user_temp", "pip_cache"]
    assert data["last_run"] == 1000.0
    assert not store.with_name("schedule.json.tmp").exists()

    reloaded = CleanerScheduler(store=store, now=lambda: 1000.0)
    assert reloaded.schedule == scheduler.schedule
    assert reloaded.last_run == 1000.0


def test_is_due_respects_enabled_cadence_and_last_run(tmp_path) -> None:
    store = tmp_path / "schedule.json"
    scheduler = CleanerScheduler(store=store, now=lambda: 10 * _DAY)
    schedule = CleanerSchedule(enabled=True, cadence="weekly", target_ids=("user_temp",), last_run=0.0)

    assert scheduler.is_due(schedule, now=8 * _DAY) is True
    assert scheduler.is_due(schedule, now=7 * _DAY - 1) is False
    assert scheduler.is_due(CleanerSchedule(), now=100 * _DAY) is False
    assert scheduler.is_due(replace_no_targets(schedule), now=100 * _DAY) is False


def replace_no_targets(schedule: CleanerSchedule) -> CleanerSchedule:
    return CleanerSchedule(
        enabled=schedule.enabled,
        cadence=schedule.cadence,
        target_ids=(),
        last_run=schedule.last_run,
    )


def test_setters_and_mark_run_update_schedule(tmp_path) -> None:
    clock = [0.0]
    scheduler = CleanerScheduler(store=tmp_path / "schedule.json", now=lambda: clock[0])

    assert scheduler.set_enabled(True).enabled is True
    assert scheduler.set_cadence("monthly").cadence_days == 30
    assert scheduler.set_target_ids(("a", "b")).target_ids == ("a", "b")
    clock[0] = 5000.0
    assert scheduler.mark_run().last_run == 5000.0
    assert scheduler.is_due(now=5000.0) is False
    assert scheduler.is_due(now=5000.0 + 30 * _DAY) is True


def test_corrupt_store_falls_back_to_default(tmp_path) -> None:
    store = tmp_path / "schedule.json"
    store.write_text("{bad", encoding="utf-8")

    scheduler = CleanerScheduler(store=store, now=lambda: 1000.0)

    assert scheduler.schedule == CleanerSchedule()
