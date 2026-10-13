from __future__ import annotations


def gb(n: float | int | None) -> str:
    return "—" if n is None else f"{n / 1024**3:.1f}GB"


def rate(bps: float | None) -> str:
    if bps is None:
        return "—"
    if bps >= 1024**2:
        return f"{bps / 1024**2:.1f}MB"
    return f"{bps / 1024:.1f}KB"


def temp_text(c: float | None) -> str:
    return "—" if c is None else f"{c:.0f}°C"


def uptime(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    total = max(int(seconds), 0)
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    if days:
        return f"{days}d {hours}h"
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def mb(n: int | None) -> str:
    return "—" if n is None else f"{n / 1024**2:.1f}MB"


def size(n: int) -> str:
    if n >= 1024**3:
        return f"{n / 1024**3:.2f}GB"
    if n >= 1024**2:
        return f"{n / 1024**2:.1f}MB"
    if n >= 1024:
        return f"{n / 1024:.1f}KB"
    return f"{n}B"


def zone_label(name: str) -> str:
    """Windows reports ACPI thermal zones as 'zone0', 'zone1'... — give them a readable name."""
    import re

    from app.i18n import tr

    m = re.fullmatch(r"zone(\d+)", name.strip(), re.IGNORECASE)
    return tr("therm_zone", n=m.group(1)) if m else name
