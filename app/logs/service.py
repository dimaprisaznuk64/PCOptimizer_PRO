from __future__ import annotations

import logging
from collections import deque
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.settings import APP_NAME, default_path as default_settings_path

LOGGER_NAME = "pcoptimizer"
DEFAULT_MAX_BYTES = 1_000_000
DEFAULT_BACKUP_COUNT = 3
LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def default_dir() -> Path:
    return default_settings_path().parent / "logs"


def get_logger(name: str | None = None) -> logging.Logger:
    if not name:
        return logging.getLogger(LOGGER_NAME)
    if name.startswith(LOGGER_NAME):
        return logging.getLogger(name)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def log_file(directory: Path | str | None = None) -> Path:
    base = Path(directory) if directory is not None else default_dir()
    return base / f"{APP_NAME}.log"


def setup_logging(
    level: str = "INFO",
    directory: Path | str | None = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    backup_count: int = DEFAULT_BACKUP_COUNT,
    console: bool = False,
) -> Path:
    if not isinstance(level, str) or level.upper() not in LEVELS:
        level = "INFO"
    target = log_file(directory)
    target.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, level.upper()))
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass

    formatter = logging.Formatter(_FORMAT)
    file_handler = RotatingFileHandler(
        target, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    if console:
        stream = logging.StreamHandler()
        stream.setFormatter(formatter)
        logger.addHandler(stream)
    logger.propagate = False
    return target


def read_tail(path: Path | str | None = None, limit: int = 500) -> list[str]:
    target = Path(path) if path is not None else log_file()
    limit = max(int(limit), 1)
    try:
        with target.open("r", encoding="utf-8", errors="replace") as fh:
            lines = deque(fh, maxlen=limit)
    except OSError:
        return []
    return [line.rstrip("\n") for line in lines if line.strip()]


def clear_logs(directory: Path | str | None = None) -> bool:
    target = log_file(directory)
    for suffix in (".1", ".2", ".3"):
        try:
            Path(f"{target}{suffix}").unlink()
        except OSError:
            pass
    try:
        with target.open("r+", encoding="utf-8", errors="replace") as fh:
            fh.truncate(0)
    except OSError:
        return not target.exists()
    return True
