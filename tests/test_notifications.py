from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.i18n import I18nService, tr
from app.ui.activity import ActivityLog, Entry
from app.ui.main_window import MainWindow
from app.ui.notifications import FILTER_ALERTS, FILTER_UNREAD, NotificationCenter, filter_entries


def test_unread_state_survives_restart(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("First", "ok detail")
    log.record("Second", "warn detail", level="warn")
    assert log.unread_count() == 2
    first_ts = log.entries(limit=10)[-1].ts
    log.mark_read(first_ts)
    assert log.is_read(first_ts) is True
    assert log.unread_count() == 1

    ActivityLog._instance = None
    fresh = ActivityLog.instance()
    assert fresh.unread_count() == 1
    assert fresh.is_read(first_ts) is True
    fresh.clear()
    assert not fresh._read_path().exists()


def test_mark_all_read_and_clear(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("A")
    log.record("B", level="error")
    log.mark_all_read()
    assert log.unread_count() == 0
    log.record("C")
    assert log.unread_count() == 1
    log.clear()
    assert log.unread_count() == 0
    assert log.entries(limit=10) == []


def test_filter_entries_modes() -> None:
    entries = [
        Entry(1.0, "ok", "read ok", ""),
        Entry(2.0, "warn", "unread warn", ""),
        Entry(3.0, "error", "read error", ""),
    ]
    def is_read(ts: float) -> bool:
        return ts != 2.0

    assert [e.title for e in filter_entries(entries, "all", is_read)] == [e.title for e in entries]
    assert [e.title for e in filter_entries(entries, FILTER_UNREAD, is_read)] == ["unread warn"]
    assert [e.title for e in filter_entries(entries, FILTER_ALERTS, is_read)] == ["unread warn", "read error"]


def test_center_lists_entries_and_filters(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("Cleaned cache", "1 GB")
    log.record("Apply failed", "denied", level="error")
    center = NotificationCenter(log=log)
    center.open()
    assert center.isVisible()
    assert center.result_list.count() == 2
    assert tr("notif_center_unread", count=2) in center.count.text()

    center.filter_combo.setCurrentIndex(1)
    assert center.result_list.count() == 2
    item = center.result_list.item(0)
    assert item is not None and item.font().bold()
    center.result_list.itemClicked.emit(item)
    assert center.result_list.count() == 1
    assert tr("notif_center_unread", count=1) in center.count.text()

    center.filter_combo.setCurrentIndex(2)
    assert center.result_list.count() == 1
    assert "Apply failed" in center.result_list.item(0).text()
    center.hide()
    log.clear()


def test_center_buttons_and_empty_state(qapp) -> None:
    log = ActivityLog.instance()
    log.clear()
    log.record("One")
    center = NotificationCenter(log=log)
    center.mark_all_button.click()
    assert tr("notif_center_unread", count=0) in center.count.text()
    center.filter_combo.setCurrentIndex(1)
    assert center.result_list.count() == 1
    assert center.result_list.item(0).flags() == Qt.ItemFlag.NoItemFlags

    log.record("Two")
    center.clear_button.click()
    assert log.entries(limit=10) == []
    assert center.result_list.count() == 1
    center.deleteLater()


def test_bell_opens_center_and_tracks_unread(qapp) -> None:
    window = MainWindow()
    log = ActivityLog.instance()
    log.clear()
    log.record("Optimizer applied", "BALANCED")
    qapp.processEvents()
    assert tr("notif_center_unread", count=1) in window.topbar.notify_button.toolTip()

    QTest.mouseClick(window.topbar.notify_button, Qt.MouseButton.LeftButton)
    assert window._notifications.isVisible()
    window._notifications.hide()
    window.topbar.notify_button.click()
    assert window._notifications.isVisible()
    window.close()


def test_center_follows_live_language_switch(qapp) -> None:
    window = MainWindow()
    I18nService.instance().set_language("UA")
    assert "Центр сповіщень" in window._notifications.title.text()
    assert "Непрочитаних" in window._notifications.count.text()
    assert window._notifications.filter_combo.itemText(0) == "Усі"
    window.close()
