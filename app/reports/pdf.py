from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QMarginsF
from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument
from PySide6.QtPrintSupport import QPrinter

from app.benchmarks.history import HistoryEntry
from app.health import HealthReport

from .service import ReportError, diagnostic_to_html, health_to_html, history_to_html

if TYPE_CHECKING:
    from app.diagnostics.service import DiagnosticsReport

Localizer = Callable[[object], tuple[str, str, str]]
DeltaFn = Callable[[HistoryEntry], float | None]
LabelFn = Callable[[str], str]

_MARGIN_MM = 12


def render_pdf(html: str, path: str | Path) -> Path:
    """Render an HTML report to *path* with Qt's built-in PDF printer."""
    target = Path(path)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(target))
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))
        printer.setPageMargins(
            QMarginsF(_MARGIN_MM, _MARGIN_MM, _MARGIN_MM, _MARGIN_MM),
            QPageLayout.Unit.Millimeter,
        )
        document = QTextDocument()
        document.setHtml(html)
        document.print_(printer)
    except (OSError, RuntimeError) as e:
        raise ReportError(str(e)) from e
    if not target.exists() or target.stat().st_size == 0:
        raise ReportError("PDF exporter produced no output")
    return target


def export_health_pdf(
    report: HealthReport,
    path: str | Path,
    *,
    localize: Localizer | None = None,
    title: str = "PC Health report",
) -> Path:
    return render_pdf(health_to_html(report, localize=localize, title=title), path)


def export_history_pdf(
    entries: Iterable[HistoryEntry],
    path: str | Path,
    *,
    localize: LabelFn | None = None,
    delta_of: DeltaFn | None = None,
    title: str = "Benchmark history",
) -> Path:
    return render_pdf(
        history_to_html(entries, localize=localize, delta_of=delta_of, title=title), path
    )


def export_diagnostics_pdf(
    report: DiagnosticsReport,
    path: str | Path,
    *,
    title: str = "Diagnostics report",
) -> Path:
    return render_pdf(diagnostic_to_html(report, title=title), path)
