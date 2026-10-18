from __future__ import annotations

from app.ui.activity import ActivityLog, outcome_level


def test_health_result_survives_restart(qapp) -> None:
    ActivityLog.instance().health = (87, "good")
    ActivityLog._instance = None  # simulate a fresh app start
    assert ActivityLog.instance().health == (87, "good")


def test_health_is_none_without_previous_scan(qapp) -> None:
    assert ActivityLog.instance().health is None


def test_outcome_level_mapping() -> None:
    assert outcome_level(has_errors=False, achieved=True) == "ok"
    assert outcome_level(has_errors=False, achieved=False) == "ok"
    assert outcome_level(has_errors=True, achieved=True) == "warn"
    assert outcome_level(has_errors=True, achieved=False) == "error"


def test_entries_filter_by_error_level(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Clean done", "1.2 GB")
    log.record("Apply failed", "powercfg denied", level="error")
    assert [e.title for e in log.entries(level="error")] == ["Apply failed"]
    assert [e.title for e in log.entries(level="ok")] == ["Clean done"]
    log.clear()


def test_entries_survive_restart_via_jsonl(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Optimizer applied", "BALANCED profile")
    log.record("Clean partial", "3 files locked", level="warn")
    ActivityLog._instance = None  # simulate restart
    fresh = ActivityLog.instance()
    titles = [e.title for e in fresh.entries(limit=10)]
    assert "Optimizer applied" in titles
    assert "Clean partial" in titles
    fresh.clear()


def test_clear_removes_history_file(qapp) -> None:
    log = ActivityLog.instance()
    log.record("Something", "detail")
    path = log._history_path()
    assert path.exists()
    log.clear()
    assert not path.exists()


def test_corrupt_lines_are_skipped(qapp) -> None:
    from app.settings.service import data_root

    log = ActivityLog.instance()
    log.clear()
    path = data_root() / "activity.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{"ts": 1.0, "level": "ok", "title": "Good"}\nnot json\n{"broken": true}\n', encoding="utf-8")
    ActivityLog._instance = None
    fresh = ActivityLog.instance()
    assert [e.title for e in fresh.entries(limit=5)] == ["Good"]
    fresh.clear()


def test_notify_menu_marks_error_with_cross(qapp) -> None:
    from PySide6.QtWidgets import QMenu

    from app.ui.topbar import TopBar

    log = ActivityLog.instance()
    log.clear()
    log.record("Disk clean failed", "access denied", level="error")
    menu = QMenu()
    TopBar._fill_notify_menu(menu)
    texts = [a.text() for a in menu.actions()]
    assert any("✕" in t for t in texts), texts
    menu.deleteLater()
    log.clear()
