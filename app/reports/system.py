from __future__ import annotations

import html
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass

REDACTED = "[redacted]"
UNAVAILABLE = "Unavailable"
NO_DATA = "No data"

SECTION_KEYS = (
    "system",
    "hardware",
    "health",
    "optimizer",
    "restore",
    "benchmarks",
    "history",
    "diagnostics",
)

SECTION_TITLES = {
    "system": "System",
    "hardware": "Hardware",
    "health": "Health",
    "optimizer": "Optimizer",
    "restore": "Restore points",
    "benchmarks": "Benchmarks",
    "history": "Performance history",
    "diagnostics": "Diagnostics",
}

SECTION_HEADINGS = tuple(SECTION_TITLES[key] for key in SECTION_KEYS)

Provider = Callable[[], object] | object

_IDENTIFIER_KEYS = (
    "hostname",
    "host",
    "serial",
    "machineguid",
    "productid",
    "uuid",
    "macaddress",
    "computername",
    "computer",
    "username",
    "usersid",
)

_SECRET_KEYS = (
    "password",
    "passwd",
    "secret",
    "token",
    "apikey",
    "authorization",
    "credential",
    "privatekey",
    "accesstoken",
    "refreshtoken",
    "cookie",
    "session",
    "bearer",
)

_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
_SECRET_TEXT_RE = re.compile(
    r"(?i)\b(password|passwd|secret|token|api[_-]?key|authorization|bearer)\b\s*[:=]\s*[^\s,;]+"
)

_STYLE = """
<style>
  body { font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; color: #101318; }
  h1 { font-size: 20pt; margin: 0 0 6pt; }
  h2 { font-size: 13pt; margin: 18pt 0 6pt; color: #163a57; }
  .meta { color: #55606e; font-size: 9pt; margin-bottom: 12pt; }
  table { border-collapse: collapse; width: 100%; font-size: 9pt; }
  th, td { border: 1px solid #c9d0da; padding: 5pt 6pt; text-align: left; vertical-align: top; }
  th { background: #eef2f7; width: 28%; }
  tr:nth-child(even) td { background: #f8fafc; }
</style>
"""


@dataclass(frozen=True, slots=True)
class SystemReportConfig:
    include_identifiers: bool = False
    output: str = "html"


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value).strip()


def _scrub(text: str) -> str:
    without_bearer = _BEARER_RE.sub(f"Bearer {REDACTED}", text)
    return _SECRET_TEXT_RE.sub(lambda match: f"{match.group(1)}={REDACTED}", without_bearer)


def redact_identifier(value: object, *, include_identifiers: bool = False) -> str:
    text = _scrub(_text(value))
    if not text:
        return ""
    return text if include_identifiers else REDACTED


def _key_token(key: object) -> str:
    return re.sub(r"[^a-z0-9]", "", _text(key).lower())


def _is_secret_key(key: object) -> bool:
    token = _key_token(key)
    return any(part in token for part in _SECRET_KEYS)


def _is_identifier_key(key: object) -> bool:
    token = _key_token(key)
    return any(token == part or token.endswith(part) for part in _IDENTIFIER_KEYS)


def _sanitize(value: object, *, include_identifiers: bool, depth: int = 0) -> object:
    if depth > 8:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if is_dataclass(value) and not isinstance(value, type):
        return _sanitize(asdict(value), include_identifiers=include_identifiers, depth=depth + 1)
    if isinstance(value, Mapping):
        result: dict[str, object] = {}
        for key, item in value.items():
            name = _text(key)
            if _is_secret_key(name):
                result[name] = REDACTED
            elif _is_identifier_key(name):
                result[name] = redact_identifier(item, include_identifiers=include_identifiers)
            else:
                result[name] = _sanitize(item, include_identifiers=include_identifiers, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set, frozenset)):
        items = sorted(value, key=_text) if isinstance(value, (set, frozenset)) else value
        return [_sanitize(item, include_identifiers=include_identifiers, depth=depth + 1) for item in items]
    return _scrub(_text(value))


def _label(key: str) -> str:
    text = key.replace("_", " ").replace(".", " ").strip()
    text = re.sub(r"(?<!^)(?=[A-Z])", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:1].upper() + text[1:] if text else "Value"


def _display(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.4g}"
    return _scrub(_text(value))


def _flatten(value: object, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(value, Mapping):
        map_rows: list[tuple[str, str]] = []
        for key, item in value.items():
            label = _label(_text(key))
            path = f"{prefix} {label}" if prefix else label
            map_rows.extend(_flatten(item, path))
        return map_rows
    if isinstance(value, (list, tuple)):
        list_rows: list[tuple[str, str]] = []
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            if isinstance(item, (Mapping, list, tuple)):
                list_rows.extend(_flatten(item, path))
            else:
                list_rows.append((path, _display(item)))
        return list_rows
    return [(prefix or "Value", _display(value))]


def _rows_from_sanitized(value: object) -> list[tuple[str, str]]:
    if value is None:
        return [("Status", UNAVAILABLE)]
    if isinstance(value, (Mapping, list, tuple, set, frozenset)) and not value:
        return [("Status", NO_DATA)]
    if isinstance(value, str) and not value.strip():
        return [("Status", NO_DATA)]
    return _flatten(value)


def _resolve(provider: object) -> object:
    if callable(provider):
        try:
            return provider()
        except Exception as e:
            return {"error": f"Unavailable: {e}"}
    return provider


def _render_html(generated: str, sections: Sequence[tuple[str, Sequence[tuple[str, str]]]]) -> str:
    parts = [
        '<!doctype html><html><head><meta charset="utf-8">',
        _STYLE,
        "</head><body><h1>System report</h1>",
        f'<div class="meta">Generated: {html.escape(generated)}</div>',
    ]
    for title, rows in sections:
        parts.append(f"<h2>{html.escape(title)}</h2>")
        parts.append('<table><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>')
        for field, value in rows:
            parts.append(
                f"<tr><td>{html.escape(field)}</td><td>{html.escape(value)}</td></tr>"
            )
        parts.append("</tbody></table>")
    parts.append("</body></html>")
    return "".join(parts)


def _render_text(generated: str, sections: Sequence[tuple[str, Sequence[tuple[str, str]]]]) -> str:
    lines = ["SYSTEM REPORT", f"Generated: {generated}", ""]
    for title, rows in sections:
        lines.extend((title, "-" * len(title)))
        lines.extend(f"{field}: {value}" for field, value in rows if value)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_system_report(
    sections: Mapping[str, object],
    *,
    config: SystemReportConfig | None = None,
    generated: str = "",
) -> str:
    cfg = config or SystemReportConfig()
    prepared: list[tuple[str, Sequence[tuple[str, str]]]] = []
    for key in SECTION_KEYS:
        value = _resolve(sections.get(key))
        sanitized = _sanitize(value, include_identifiers=cfg.include_identifiers)
        prepared.append((SECTION_TITLES[key], _rows_from_sanitized(sanitized)))
    stamp = _text(generated) or "Not provided"
    output = cfg.output.lower()
    if output == "text":
        return _render_text(stamp, prepared)
    if output == "html":
        return _render_html(stamp, prepared)
    raise ValueError(f"unsupported report output: {cfg.output}")


def build_system_report(
    *,
    system: Provider = None,
    hardware: Provider = None,
    health: Provider = None,
    optimizer: Provider = None,
    restore: Provider = None,
    benchmarks: Provider = None,
    history: Provider = None,
    diagnostics: Provider = None,
    config: SystemReportConfig | None = None,
    generated: str = "",
) -> str:
    sections = {
        "system": system,
        "hardware": hardware,
        "health": health,
        "optimizer": optimizer,
        "restore": restore,
        "benchmarks": benchmarks,
        "history": history,
        "diagnostics": diagnostics,
    }
    return render_system_report(sections, config=config, generated=generated)


__all__ = [
    "NO_DATA",
    "REDACTED",
    "SECTION_HEADINGS",
    "SECTION_KEYS",
    "SECTION_TITLES",
    "UNAVAILABLE",
    "SystemReportConfig",
    "build_system_report",
    "redact_identifier",
    "render_system_report",
]
