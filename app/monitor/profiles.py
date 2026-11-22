"""Monitoring frequency profiles shared by sensors, history and background polls."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MonitorProfile:
    key: str
    sample_interval_ms: int
    history_interval_s: float
    process_refresh_ms: int
    game_presence_s: float


PROFILES: dict[str, MonitorProfile] = {
    "ECO": MonitorProfile("ECO", 2000, 60.0, 10_000, 10.0),
    "BALANCED": MonitorProfile("BALANCED", 1000, 30.0, 5_000, 5.0),
    "PERFORMANCE": MonitorProfile("PERFORMANCE", 500, 10.0, 2_000, 2.0),
}

DEFAULT_PROFILE = "BALANCED"
PROFILE_KEYS = tuple(PROFILES)


def profile_for(key: object) -> MonitorProfile:
    """Resolve a saved profile key, falling back to the balanced defaults."""
    if isinstance(key, str):
        profile = PROFILES.get(key.strip().upper())
        if profile is not None:
            return profile
    return PROFILES[DEFAULT_PROFILE]
