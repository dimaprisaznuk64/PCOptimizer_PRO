from __future__ import annotations

import csv
import io
import json
import time
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from pathlib import Path

from app.benchmarks.history import HistoryEntry
from app.health import HealthReport


class ReportError(Exception):
    pass


Localizer = Callable[[object], tuple[str, str, str]]
DeltaFn = Callable[[HistoryEntry], float | None]
LabelFn = Callable[[str], str]

HEALTH_CSV_HEADER = ("Category", "Severity", "Issue", "Detail", "Fixable")
HISTORY_CSV_HEADER = ("Time", "Metric", "Value", "Unit", "Detail", "Baseline", "Delta %")


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def format_for_path(path: str | Path) -> str:
    """Pick the export format from a file name; JSON only for ``.json``."""
    return "json" if Path(path).suffix.lower() == ".json" else "csv"


def timestamp_name(prefix: str, fmt: str, *, now: float | None = None) -> str:
    """A default file name such as ``health_report_20260101_120000.csv``."""
    stamp = time.strftime("%Y%m%d_%H%M%S", time.localtime(now if now is not None else time.time()))
    return f"{prefix}_{stamp}.{fmt}"


# ---------- health ----------


def health_record(report: HealthReport, *, localize: Localizer | None = None) -> dict:
    findings = []
    for finding in report.findings:
        category, title, detail = localize(finding) if localize else (
            finding.category, finding.title, finding.detail
        )
        findings.append({
            "category": category,
            "severity": finding.severity,
            "title": title,
            "detail": detail,
            "fixable": finding.fixable,
        })
    return {
        "generated": _iso(report.generated),
        "score": report.score,
        "grade": report.grade,
        "junk_bytes": report.junk_bytes,
        "junk_targets": report.junk_targets,
        "errors": list(report.errors),
        "findings": findings,
    }


def health_to_json(report: HealthReport, *, localize: Localizer | None = None) -> str:
    return json.dumps(health_record(report, localize=localize), ensure_ascii=False, indent=2)


def health_to_csv(
    report: HealthReport,
    *,
    localize: Localizer | None = None,
    header: Sequence[str] | None = None,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header or HEALTH_CSV_HEADER)
    for finding in report.findings:
        category, title, detail = localize(finding) if localize else (
            finding.category, finding.title, finding.detail
        )
        writer.writerow([category, finding.severity, title, detail, "yes" if finding.fixable else "no"])
    return buf.getvalue()


# ---------- benchmarks ----------


def history_record(
    entries: Iterable[HistoryEntry],
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    now: float | None = None,
) -> dict:
    items = []
    for entry in entries:
        delta = None if entry.baseline or delta_of is None else delta_of(entry)
        items.append({
            "when": entry.when,
            "metric": entry.metric,
            "metric_label": localize(entry.metric) if localize else entry.metric,
            "value": entry.value,
            "unit": entry.unit,
            "detail": entry.detail,
            "baseline": entry.baseline,
            "delta_pct": delta,
        })
    return {
        "exported": _iso(now if now is not None else time.time()),
        "count": len(items),
        "entries": items,
    }


def history_to_json(
    entries: Iterable[HistoryEntry],
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    now: float | None = None,
) -> str:
    record = history_record(entries, localize=localize, delta_of=delta_of, now=now)
    return json.dumps(record, ensure_ascii=False, indent=2)


def history_to_csv(
    entries: Iterable[HistoryEntry],
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    header: Sequence[str] | None = None,
) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header or HISTORY_CSV_HEADER)
    for entry in entries:
        delta = None if entry.baseline or delta_of is None else delta_of(entry)
        writer.writerow([
            entry.when.replace("T", " "),
            localize(entry.metric) if localize else entry.metric,
            f"{entry.value:.4g}",
            entry.unit,
            entry.detail,
            "yes" if entry.baseline else "no",
            "" if delta is None else f"{delta:+.1f}",
        ])
    return buf.getvalue()


# ---------- saving ----------


def write_report(path: str | Path, text: str, fmt: str | None = None) -> Path:
    """Write an export to *path*; CSV gets a UTF-8 BOM so Excel reads it."""
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt or format_for_path(target)
    encoding = "utf-8-sig" if fmt == "csv" else "utf-8"
    try:
        target.write_text(text, encoding=encoding)
    except OSError as e:
        raise ReportError(str(e)) from e
    return target


def export_health(
    report: HealthReport,
    path: str | Path,
    *,
    localize: Localizer | None = None,
    header: Sequence[str] | None = None,
) -> Path:
    fmt = format_for_path(path)
    text = (
        health_to_json(report, localize=localize)
        if fmt == "json"
        else health_to_csv(report, localize=localize, header=header)
    )
    return write_report(path, text, fmt)


def export_history(
    entries: Iterable[HistoryEntry],
    path: str | Path,
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    header: Sequence[str] | None = None,
    now: float | None = None,
) -> Path:
    items = list(entries)
    fmt = format_for_path(path)
    text = (
        history_to_json(items, localize=localize, delta_of=delta_of, now=now)
        if fmt == "json"
        else history_to_csv(items, localize=localize, delta_of=delta_of, header=header)
    )
    return write_report(path, text, fmt)
