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
