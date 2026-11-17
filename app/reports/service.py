from __future__ import annotations

import csv
import html
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
    """Pick the export format from a file name; CSV is the fallback."""
    suffix = Path(path).suffix.lower()
    if suffix == ".json":
        return "json"
    if suffix == ".pdf":
        return "pdf"
    return "csv"


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


# ---------- printable HTML (used by the PDF exporter) ----------


_PDF_STYLE = """
<style>
  body { font-family: 'Segoe UI Variable Text', 'Segoe UI', sans-serif; color: #101318; }
  h1 { font-size: 20pt; margin: 0 0 6pt; }
  .meta { color: #55606e; font-size: 9pt; margin-bottom: 14pt; }
  table { border-collapse: collapse; width: 100%; font-size: 9pt; }
  th, td { border: 1px solid #c9d0da; padding: 5pt 6pt; text-align: left; vertical-align: top; }
  th { background: #eef2f7; }
  tr:nth-child(even) td { background: #f8fafc; }
</style>
"""


def _html_page(title: str, meta: str, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
    head = "".join(f"<th>{_esc(item)}</th>" for item in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{_esc(item)}</td>" for item in row) + "</tr>"
        for row in rows
    )
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"{_PDF_STYLE}</head><body><h1>{_esc(title)}</h1>"
        f'<div class="meta">{_esc(meta)}</div>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</body></html>"
    )


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=False)


def health_to_html(
    report: HealthReport,
    *,
    localize: Localizer | None = None,
    title: str = "PC Health report",
) -> str:
    record = health_record(report, localize=localize)
    meta = (
        f"{record['generated']} · score {record['score']} · {record['grade']} · "
        f"junk {record['junk_bytes']} bytes / {record['junk_targets']} targets"
    )
    if record["errors"]:
        meta += " · " + "; ".join(str(item) for item in record["errors"])
    rows = [
        (item["category"], item["severity"], item["title"], item["detail"],
         "yes" if item["fixable"] else "no")
        for item in record["findings"]
    ]
    return _html_page(title, meta, HEALTH_CSV_HEADER, rows)


def history_to_html(
    entries: Iterable[HistoryEntry],
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    title: str = "Benchmark history",
    now: float | None = None,
) -> str:
    record = history_record(entries, localize=localize, delta_of=delta_of, now=now)
    rows = [
        (
            item["when"], item["metric_label"], f"{item['value']:.4g}", item["unit"],
            item["detail"], "yes" if item["baseline"] else "no",
            "" if item["delta_pct"] is None else f"{item['delta_pct']:+.1f}",
        )
        for item in record["entries"]
    ]
    return _html_page(title, f"{record['exported']} · {record['count']} records", HISTORY_CSV_HEADER, rows)


# ---------- saving ----------


def write_report(path: str | Path, text: str, fmt: str | None = None) -> Path:
    """Write an export to *path*; CSV gets a UTF-8 BOM so Excel reads it."""
    target = Path(path)
    if target.parent and not target.parent.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
    fmt = fmt or format_for_path(target)
    if fmt == "pdf":
        raise ReportError("PDF reports must be written with the PDF exporter")
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
