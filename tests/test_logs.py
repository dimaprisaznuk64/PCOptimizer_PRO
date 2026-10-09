from __future__ import annotations

import logging
from pathlib import Path

from app.logs import (
    LOGGER_NAME,
    clear_logs,
    get_logger,
    log_file,
    read_tail,
    setup_logging,
)


def test_setup_writes_log_file(tmp_path) -> None:
    target = setup_logging("INFO", directory=tmp_path, console=False)
    assert target == log_file(tmp_path)
    assert target.exists()
    get_logger("test").info("hello from test")
    lines = read_tail(target)
    assert any("hello from test" in line for line in lines)
    assert any("INFO" in line for line in lines)


def test_setup_is_idempotent(tmp_path) -> None:
    setup_logging("INFO", directory=tmp_path, console=False)
    setup_logging("DEBUG", directory=tmp_path, console=False)
    logger = logging.getLogger(LOGGER_NAME)
    assert len(logger.handlers) == 1
    get_logger().warning("single handler")
    lines = read_tail(log_file(tmp_path))
    assert sum(1 for line in lines if "single handler" in line) == 1


def test_level_filtering(tmp_path) -> None:
    setup_logging("WARNING", directory=tmp_path, console=False)
    log = get_logger("filter")
    log.debug("hidden debug")
    log.info("hidden info")
    log.error("shown error")
    text = "\n".join(read_tail(log_file(tmp_path)))
    assert "hidden debug" not in text
    assert "hidden info" not in text
    assert "shown error" in text


def test_invalid_level_falls_back_to_info(tmp_path) -> None:
    target = setup_logging("LOUD", directory=tmp_path, console=False)
    logger = logging.getLogger(LOGGER_NAME)
    assert logger.level == logging.INFO
    assert target.exists()


def test_read_tail_missing_file(tmp_path) -> None:
    assert read_tail(tmp_path / "nope.log") == []


def test_read_tail_limit(tmp_path) -> None:
    setup_logging("INFO", directory=tmp_path, console=False)
    log = get_logger("tail")
    for i in range(20):
        log.info("line %s", i)
    lines = read_tail(log_file(tmp_path), limit=5)
    assert len(lines) == 5
    assert "line 19" in lines[-1]


def test_read_tail_deduplicates_blank_lines(tmp_path) -> None:
    target = tmp_path / "manual.log"
    target.write_text("a\n\n\nb\n", encoding="utf-8")
    assert read_tail(target) == ["a", "b"]


def test_clear_logs(tmp_path) -> None:
    setup_logging("INFO", directory=tmp_path, console=False)
    get_logger().info("something")
    target = log_file(tmp_path)
    Path(f"{target}.1").write_text("old", encoding="utf-8")
    assert clear_logs(tmp_path) is True
    assert read_tail(target) == []
    assert not Path(f"{target}.1").exists()


def test_logger_namespacing() -> None:
    assert get_logger().name == LOGGER_NAME
    assert get_logger("child").name == f"{LOGGER_NAME}.child"
    assert get_logger(f"{LOGGER_NAME}.child").name == f"{LOGGER_NAME}.child"
