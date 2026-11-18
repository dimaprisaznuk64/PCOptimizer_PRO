from __future__ import annotations

import csv
import io
import json
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from app.history.service import PerformanceHistory

from .service import (
    ReportError,
    diagnostic_to_csv,
    diagnostic_to_json,
    format_for_path,
    health_to_csv,
    health_to_json,
    history_to_csv,
    history_to_json,
    timestamp_name,
    write_report,
)
from .system import SystemReportConfig, build_system_report

PERFORMANCE_HISTORY_MINUTES = 7 * 24 * 60

CSV = "csv"
JSON = "json"
HTML = "html"
PDF = "pdf"

FORMATS: tuple[str, ...] = (CSV, JSON, HTML, PDF)


class ExportKind(StrEnum):
    HEALTH = "health"
    BENCHMARKS = "benchmarks"
    DIAGNOSTICS = "diagnostics"
    PERFORMANCE_HISTORY = "performance_history"
    SYSTEM_REPORT = "system_report"


@dataclass(frozen=True, slots=True)
class ExportJob:
    kind: ExportKind
    label_key: str
    available: bool
    formats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ExportResult:
    kind: ExportKind | str
    path: Path | None = None
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass(frozen=True, slots=True)
class ExportBundle:
    results: tuple[ExportResult, ...]

    @property
    def written(self) -> tuple[Path, ...]:
        return tuple(result.path for result in self.results if result.path is not None)

    @property
    def errors(self) -> tuple[ExportResult, ...]:
        return tuple(result for result in self.results if result.error is not None)

    @property
    def ok(self) -> bool:
        return not self.errors

    @property
    def partial(self) -> bool:
        return bool(self.written and self.errors)


JOB_SPECS: dict[ExportKind, tuple[str, tuple[str, ...], str]] = {
    ExportKind.HEALTH: ("export_kind_health", (CSV, JSON, PDF), "health_report"),
    ExportKind.BENCHMARKS: ("export_kind_benchmarks", (CSV, JSON, PDF), "benchmark_history"),
    ExportKind.DIAGNOSTICS: ("export_kind_diagnostics", (CSV, JSON, PDF), "diagnostics_report"),
    ExportKind.PERFORMANCE_HISTORY: (
        "export_kind_performance_history",
        (CSV, JSON),
        "performance_history",
    ),
    ExportKind.SYSTEM_REPORT: ("export_kind_system_report", (HTML, PDF), "system_report"),
}

Exporter = Callable[[Path, object | None, str], Path]


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def _number(value: object) -> str:
    return "" if value is None else f"{float(value):.1f}"


def _unique_path(directory: Path, name: str, used: set[str]) -> Path:
    candidate = name
    index = 2
    while candidate in used or (directory / candidate).exists():
        stem, suffix = Path(name).stem, Path(name).suffix
        candidate = f"{stem}_{index}{suffix}"
        index += 1
    used.add(candidate)
    return directory / candidate


def _query_history(history: PerformanceHistory | None, now: Callable[[], float]) -> list:
    source = history if history is not None else PerformanceHistory(now=now)
    return source.query(minutes=PERFORMANCE_HISTORY_MINUTES)


def _write_performance_history(
    samples: Sequence[object], path: Path, fmt: str, generated: str
) -> Path:
    if fmt == JSON:
        text = json.dumps(
            {
                "exported": generated,
                "count": len(samples),
                "samples": [sample.to_dict() for sample in samples],
            },
            ensure_ascii=False,
            indent=2,
        )
    elif fmt == CSV:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            (
                "Time",
                "CPU %",
                "RAM %",
                "GPU %",
                "VRAM %",
                "System temp C",
                "GPU temp C",
                "GPU hotspot C",
                "GPU power W",
                "Commit %",
                "Top processes",
            )
        )
        for sample in samples:
            writer.writerow(
                (
                    _iso(float(sample.ts)),
                    _number(sample.cpu),
                    _number(sample.ram),
                    _number(sample.gpu),
                    _number(sample.gpu_mem),
                    _number(getattr(sample, "temp_cpu", None)),
                    _number(sample.temp_gpu),
                    _number(sample.gpu_hotspot),
                    _number(sample.gpu_power),
                    _number(sample.commit_percent),
                    "; ".join(f"{name} {mb:.0f}MB" for name, mb in sample.top_processes),
                )
            )
        text = buf.getvalue()
    else:
        raise ReportError(f"unsupported performance history format: {fmt}")
    return write_report(path, text, fmt)


def _system_sections(now: Callable[[], float]) -> dict[str, object]:
    def system() -> dict[str, object]:
        from app import __version__
        from app.settings import data_root

        return {
            "application": "PCOptimizer PRO",
            "version": __version__,
            "platform": "Windows",
            "data_root": str(data_root()),
        }

    def hardware() -> object:
        from app.hardware import HardwareService

        return HardwareService().report()

    def health() -> object:
        from app.health import HealthService

        return HealthService().scan()

    def optimizer() -> object:
        from app.optimizer import OptimizerService

        return OptimizerService().state()

    def restore() -> object:
        from app.restore import RestorePointService

        return RestorePointService().list_points()

    def benchmarks() -> object:
        from app.benchmarks import BenchmarkHistory

        return BenchmarkHistory().entries(limit=50)

    def history() -> object:
        return _query_history(None, now)

    def diagnostics() -> object:
        from app.diagnostics import DiagnosticsService

        return DiagnosticsService().report()

    return {
        "system": system,
        "hardware": hardware,
        "health": health,
        "optimizer": optimizer,
        "restore": restore,
        "benchmarks": benchmarks,
        "history": history,
        "diagnostics": diagnostics,
    }


def _require_format(kind: ExportKind, fmt: str) -> None:
    if fmt not in JOB_SPECS[kind][1]:
        raise ReportError(f"unsupported format for {kind.value}: {fmt}")


def default_exporters(
    *, now: Callable[[], float] | None = None, history: PerformanceHistory | None = None
) -> dict[ExportKind, Exporter]:
    clock = now or time.time

    def health(path: Path, data: object | None, fmt: str) -> Path:
        _require_format(ExportKind.HEALTH, fmt)
        if data is None:
            from app.health import HealthService

            data = HealthService().scan()
        report = data
        if fmt == PDF:
            from .pdf import export_health_pdf

            return export_health_pdf(report, path)
        return write_report(path, health_to_json(report) if fmt == JSON else health_to_csv(report), fmt)

    def benchmarks(path: Path, data: object | None, fmt: str) -> Path:
        _require_format(ExportKind.BENCHMARKS, fmt)
        if data is None:
            from app.benchmarks import BenchmarkHistory

            data = BenchmarkHistory().entries()
        entries = data
        if fmt == PDF:
            from .pdf import export_history_pdf

            return export_history_pdf(entries, path)
        return write_report(
            path, history_to_json(entries) if fmt == JSON else history_to_csv(entries), fmt
        )

    def diagnostics(path: Path, data: object | None, fmt: str) -> Path:
        _require_format(ExportKind.DIAGNOSTICS, fmt)
        if data is None:
            from app.diagnostics import DiagnosticsService

            data = DiagnosticsService().report()
        report = data
        if fmt == PDF:
            from .pdf import export_diagnostics_pdf

            return export_diagnostics_pdf(report, path)
        return write_report(
            path,
            diagnostic_to_json(report) if fmt == JSON else diagnostic_to_csv(report),
            fmt,
        )

    def performance_history(path: Path, data: object | None, fmt: str) -> Path:
        _require_format(ExportKind.PERFORMANCE_HISTORY, fmt)
        samples = data if data is not None else _query_history(history, clock)
        return _write_performance_history(samples, path, fmt, _iso(clock()))

    def system_report(path: Path, data: object | None, fmt: str) -> Path:
        _require_format(ExportKind.SYSTEM_REPORT, fmt)
        if isinstance(data, str):
            rendered = data
        else:
            sections = data if isinstance(data, Mapping) else _system_sections(clock)
            rendered = build_system_report(
                **sections,
                config=SystemReportConfig(output=HTML),
                generated=_iso(clock()),
            )
        if fmt == PDF:
            from .pdf import render_pdf

            return render_pdf(rendered, path)
        return write_report(path, rendered, HTML)

    return {
        ExportKind.HEALTH: health,
        ExportKind.BENCHMARKS: benchmarks,
        ExportKind.DIAGNOSTICS: diagnostics,
        ExportKind.PERFORMANCE_HISTORY: performance_history,
        ExportKind.SYSTEM_REPORT: system_report,
    }


class ExportCenterService:
    def __init__(
        self,
        *,
        exporters: Mapping[ExportKind, Exporter] | None = None,
        now: Callable[[], float] | None = None,
        history: PerformanceHistory | None = None,
        availability: Mapping[ExportKind, bool] | None = None,
    ) -> None:
        self._now = now or time.time
        self._history = history
        self._exporters: dict[ExportKind, Exporter] = (
            dict(exporters)
            if exporters is not None
            else default_exporters(now=self._now, history=history)
        )
        self._availability = dict(availability) if availability else {}

    def jobs(self) -> list[ExportJob]:
        return [
            ExportJob(kind, label_key, self._is_available(kind), formats)
            for kind, (label_key, formats, _prefix) in JOB_SPECS.items()
        ]

    def _is_available(self, kind: ExportKind) -> bool:
        return bool(self._availability.get(kind, kind in self._exporters))

    def default_filename(self, kind: ExportKind | str, fmt: str) -> str:
        resolved = ExportKind(kind)
        prefix = JOB_SPECS[resolved][2]
        return timestamp_name(prefix, fmt, now=self._now())

    def export(
        self,
        kind: ExportKind | str,
        path: str | Path,
        data: object | None = None,
        fmt: str | None = None,
    ) -> Path:
        resolved = ExportKind(kind)
        exporter = self._exporters.get(resolved)
        if exporter is None:
            raise ReportError(f"no exporter for {resolved.value}")
        chosen = (fmt or format_for_path(path)).lower()
        try:
            return exporter(Path(path), data, chosen)
        except ReportError:
            raise
        except (OSError, ValueError) as e:
            raise ReportError(str(e)) from e

    def export_selected(
        self, kinds: Iterable[ExportKind | str], directory: str | Path, fmt: str
    ) -> ExportBundle:
        target = Path(directory)
        try:
            target.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise ReportError(str(e)) from e
        used: set[str] = set()
        results: list[ExportResult] = []
        for kind in kinds:
            try:
                resolved = ExportKind(kind)
                path = _unique_path(target, self.default_filename(resolved, fmt), used)
                written = self.export(resolved, path, fmt=fmt)
            except (ReportError, ValueError, OSError) as e:
                results.append(ExportResult(kind, error=str(e) or type(e).__name__))
                continue
            results.append(ExportResult(resolved, written))
        return ExportBundle(tuple(results))


__all__ = [
    "CSV",
    "FORMATS",
    "HTML",
    "JSON",
    "PDF",
    "PERFORMANCE_HISTORY_MINUTES",
    "ExportBundle",
    "ExportCenterService",
    "ExportJob",
    "ExportKind",
    "ExportResult",
    "JOB_SPECS",
    "default_exporters",
]
