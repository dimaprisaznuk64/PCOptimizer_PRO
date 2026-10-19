"""PCOptimizer_PRO — diagnostics package (drive health + event log + updates)."""

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
    PendingUpdate,
    parse_events,
    parse_updates,
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
    "PendingUpdate",
    "parse_events",
    "parse_updates",
]
