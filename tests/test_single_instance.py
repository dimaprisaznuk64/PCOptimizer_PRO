from __future__ import annotations

import time
from uuid import uuid4

import pytest

from app.ui.single_instance import SingleInstanceGuard


@pytest.fixture
def pipe_name() -> str:
    return f"pco_test_{uuid4().hex}"


def _wait_for(qapp, predicate, timeout_s: float = 5.0) -> bool:
    """Pump the event loop until the predicate holds or the deadline passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if predicate():
            return True
        qapp.processEvents()
        time.sleep(0.01)
    return predicate()


def test_second_instance_is_rejected(qapp, pipe_name: str) -> None:
    primary = SingleInstanceGuard(name=pipe_name, parent=qapp)
    assert primary.acquire() is True
    try:
        secondary = SingleInstanceGuard(name=pipe_name, parent=qapp)
        assert secondary.acquire() is False
    finally:
        primary.close()


def test_two_guards_with_different_names(qapp, pipe_name: str) -> None:
    a = SingleInstanceGuard(name=f"{pipe_name}_a", parent=qapp)
    b = SingleInstanceGuard(name=f"{pipe_name}_b", parent=qapp)
    assert a.acquire() is True
    assert b.acquire() is True
    a.close()
    b.close()


def test_first_instance_emits_show_signal(qapp, pipe_name: str) -> None:
    primary = SingleInstanceGuard(name=pipe_name, parent=qapp)
    assert primary.acquire() is True
    requested: list[int] = []
    primary.show_requested.connect(lambda: requested.append(1))
    try:
        secondary = SingleInstanceGuard(name=pipe_name, parent=qapp)
        assert secondary.acquire() is False
        assert _wait_for(qapp, lambda: requested == [1])
    finally:
        primary.close()