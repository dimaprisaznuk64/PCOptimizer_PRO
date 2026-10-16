"""PCOptimizer_PRO — diagnostics package (drive health + event log)."""

from .service import (
    DEFAULT_LEVELS,
    DEFAULT_LIMIT,
    DEFAULT_LOG,
    HEALTH_NAMES,
    LEVEL_NAMES,
    DiagnosticsError,
    DiagnosticsReport,
    DiagnosticsService,
    DiskHealth,
    EventEntry,
    parse_events,
)

__all__ = [
    "DEFAULT_LEVELS",
    "DEFAULT_LIMIT",
    "DEFAULT_LOG",
    "HEALTH_NAMES",
    "LEVEL_NAMES",
    "DiagnosticsError",
    "DiagnosticsReport",
    "DiagnosticsService",
    "DiskHealth",
    "EventEntry",
    "parse_events",
]
