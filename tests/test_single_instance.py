from __future__ import annotations

from PySide6.QtCore import QTimer

from app.ui.single_instance import SingleInstanceGuard


def _spin(qapp, ms: int = 400) -> None:
    QTimer.singleShot(ms, qapp.quit)
    qapp.exec()


def test_second_instance_is_rejected(qapp) -> None:
    primary = SingleInstanceGuard(name="pco_test_primary", parent=qapp)
    assert primary.acquire() is True
    try:
        secondary = SingleInstanceGuard(name="pco_test_primary", parent=qapp)
        assert secondary.acquire() is False
    finally:
        primary.close()


def test_two_guards_with_different_names(qapp) -> None:
    a = SingleInstanceGuard(name="pco_test_a", parent=qapp)
    b = SingleInstanceGuard(name="pco_test_b", parent=qapp)
    assert a.acquire() is True
    assert b.acquire() is True
    a.close()
    b.close()


def test_first_instance_emits_show_signal(qapp) -> None:
    primary = SingleInstanceGuard(name="pco_test_show", parent=qapp)
    assert primary.acquire() is True
    requested: list[int] = []
    primary.show_requested.connect(lambda: requested.append(1))
    try:
        secondary = SingleInstanceGuard(name="pco_test_show", parent=qapp)
        assert secondary.acquire() is False
        _spin(qapp)
        assert requested == [1]
    finally:
        primary.close()