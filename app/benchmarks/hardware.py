from __future__ import annotations

import csv
import io
import json
import time
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.hardware import HardwareReport, HardwareService
from app.reports.system import redact_identifier

from .history import BenchmarkHistory
from .service import BenchmarkResult, BenchmarkService, BenchmarkType

_MISSING = "—"
_SIZE_UNITS = ("B", "KB", "MB", "GB", "TB")
DEFAULT_TYPES = (BenchmarkType.CPU, BenchmarkType.RAM, BenchmarkType.DISK)


@dataclass(frozen=True, slots=True)
class PreviousValue:
    metric: str
    value: float
    unit: str


@dataclass(frozen=True, slots=True)
class HardwareBenchmarkReport:
    generated: str
    hardware: HardwareReport
    results: tuple[BenchmarkResult, ...]
    errors: tuple[str, ...]
    previous: tuple[PreviousValue, ...] = ()


@dataclass(frozen=True, slots=True)
class BaselineRow:
    metric: str
    value: float
    unit: str
    previous: float | None
    delta_pct: float | None


def _size(value: int) -> str:
    if value <= 0:
        return _MISSING
    number = float(value)
    index = 0
    while number >= 1024 and index < len(_SIZE_UNITS) - 1:
        number /= 1024
        index += 1
    return f"{value} B" if index == 0 else f"{number:.1f} {_SIZE_UNITS[index]}"


class HardwareBenchmarkService:
    def __init__(
        self,
        *,
        hardware: HardwareService | None = None,
        benchmark: BenchmarkService | None = None,
        history: BenchmarkHistory | None = None,
        now: Callable[[], float] | None = None,
        disk_dir: str | Path | None = None,
    ) -> None:
        self._hardware = hardware or HardwareService()
        self._benchmark = benchmark or BenchmarkService()
        self._history = history or BenchmarkHistory()
        self._now = now or time.time
        self._disk_dir = Path(disk_dir) if disk_dir else None

    @property
    def hardware(self) -> HardwareService:
        return self._hardware

    @property
    def benchmark(self) -> BenchmarkService:
        return self._benchmark

    @property
    def history(self) -> BenchmarkHistory:
        return self._history

    def run(self, types: Iterable[BenchmarkType] = DEFAULT_TYPES) -> HardwareBenchmarkReport:
        errors: list[str] = []
        try:
            hardware = self._hardware.report()
            errors.extend(hardware.errors)
        except Exception as e:
            hardware = HardwareReport()
            errors.append(f"hardware: {e}")

        results: list[BenchmarkResult] = []
        for btype in tuple(types):
            try:
                part = self._benchmark.run(btype, disk_dir=self._disk_dir)
            except Exception as e:
                errors.append(f"{getattr(btype, 'name', str(btype))}: {e}")
                continue
            results.extend(part)

        previous: dict[str, PreviousValue] = {}
        if self._history is not None:
            for result in results:
                try:
                    entry = self._history.latest_of(result.metric)
                except Exception as e:
                    errors.append(f"history previous: {e}")
                    continue
                if entry is not None:
                    previous[result.metric] = PreviousValue(
                        result.metric, float(entry.value), entry.unit
                    )

        if results:
            try:
                self._history.record(results)
            except Exception as e:
                errors.append(f"history: {e}")

        return HardwareBenchmarkReport(
            generated=datetime.fromtimestamp(self._now()).isoformat(timespec="seconds"),
            hardware=hardware,
            results=tuple(results),
            errors=tuple(errors),
            previous=tuple(previous.values()),
        )

    def summary_rows(self, report: HardwareBenchmarkReport) -> list[tuple[str, str]]:
        hardware = report.hardware
        system = " ".join(
            part for part in (hardware.system.manufacturer, hardware.system.model, hardware.system.os_name) if part
        ) or _MISSING
        cpu = hardware.cpu
        cpu_text = (
            f"{cpu.name} · {cpu.physical_cores}/{cpu.logical_cores}"
            if cpu and (cpu.name or cpu.physical_cores)
            else _MISSING
        )
        memory = hardware.memory
        memory_text = (
            f"{_size(memory.total_bytes)} · {memory.slots_used}/{memory.slots_total} slots"
            if memory.slots_total
            else _size(memory.total_bytes)
        )
        gpus = ", ".join(gpu.name for gpu in hardware.gpus if gpu.name) or _MISSING
        disks = ", ".join(disk.model for disk in hardware.disks if disk.model) or _MISSING
        rows = [
            ("hwb_row_system", system),
            ("hwb_row_cpu", cpu_text),
            ("hwb_row_memory", memory_text),
            ("hwb_row_gpu", gpus),
            ("hwb_row_storage", disks),
            ("hwb_row_benchmarks", str(len(report.results))),
        ]
        if report.errors:
            rows.append(("hwb_row_errors", "; ".join(report.errors)))
        return rows

    def baseline_rows(self, report: HardwareBenchmarkReport) -> tuple[BaselineRow, ...]:
        previous = {item.metric: item.value for item in report.previous}
        rows: list[BaselineRow] = []
        for result in report.results:
            rows.append(
                BaselineRow(
                    metric=result.metric,
                    value=result.value,
                    unit=result.unit,
                    previous=previous.get(result.metric),
                    delta_pct=self._history.delta_pct(result.metric, result.value),
                )
            )
        return tuple(rows)

    def _export_hardware(self, report: HardwareBenchmarkReport, *, include_identifiers: bool) -> dict:
        hardware = asdict(report.hardware)
        system = hardware.get("system")
        if isinstance(system, dict) and "hostname" in system:
            system["hostname"] = redact_identifier(
                system["hostname"], include_identifiers=include_identifiers
            )
        board = hardware.get("board")
        if isinstance(board, dict) and "serial" in board:
            board["serial"] = redact_identifier(board["serial"], include_identifiers=include_identifiers)
        disks = hardware.get("disks")
        if isinstance(disks, (list, tuple)):
            for disk in disks:
                if isinstance(disk, dict) and "serial" in disk:
                    disk["serial"] = redact_identifier(
                        disk["serial"], include_identifiers=include_identifiers
                    )
        return hardware

    def export_record(
        self, report: HardwareBenchmarkReport, *, include_identifiers: bool = False
    ) -> dict:
        return {
            "generated": report.generated,
            "hardware": self._export_hardware(report, include_identifiers=include_identifiers),
            "results": [
                {
                    "type": result.type.name if hasattr(result.type, "name") else str(result.type),
                    "metric": result.metric,
                    "value": result.value,
                    "unit": result.unit,
                    "duration_ms": result.duration_ms,
                    "runs": result.runs,
                    "detail": result.detail,
                }
                for result in report.results
            ],
            "baseline": [asdict(row) for row in self.baseline_rows(report)],
            "errors": list(report.errors),
        }

    def export_text(self, report: HardwareBenchmarkReport, fmt: str, *, include_identifiers: bool = False) -> str:
        if fmt.lower() == "json":
            return json.dumps(
                self.export_record(report, include_identifiers=include_identifiers),
                ensure_ascii=False,
                indent=2,
            )
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(("Metric", "Value", "Unit", "Previous", "Delta %", "Type", "Duration ms", "Runs", "Detail"))
        for result, row in zip(report.results, self.baseline_rows(report), strict=True):
            writer.writerow(
                (
                    result.metric,
                    result.value,
                    result.unit,
                    "" if row.previous is None else row.previous,
                    "" if row.delta_pct is None else f"{row.delta_pct:+.1f}",
                    result.type.name if hasattr(result.type, "name") else str(result.type),
                    result.duration_ms,
                    result.runs,
                    result.detail,
                )
            )
        for error in report.errors:
            writer.writerow(("error", error))
        return buf.getvalue()


__all__ = [
    "BaselineRow",
    "DEFAULT_TYPES",
    "HardwareBenchmarkReport",
    "HardwareBenchmarkService",
    "PreviousValue",
]
