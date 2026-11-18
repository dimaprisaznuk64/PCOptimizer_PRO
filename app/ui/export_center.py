from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.reports.center import (
    FORMATS,
    ExportBundle,
    ExportCenterService,
    ExportJob,
    ExportKind,
    ExportResult,
)
from app.settings import data_root

from .components import CardPanel
from .tasks import Task
from .theme import PAGE_MARGINS, PAGE_SPACING, SPACING_SM


def _pdf_pages(path: Path) -> int | None:
    try:
        from PySide6.QtPdf import QPdfDocument
    except ImportError:
        return None
    document = QPdfDocument()
    try:
        if document.load(str(path)) != QPdfDocument.Status.Ready:
            return None
        return document.pageCount()
    except (OSError, RuntimeError):
        return None
    finally:
        document.close()


def _file_detail(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    detail = f"{size} B"
    if path.suffix.lower() == ".pdf":
        pages = _pdf_pages(path)
        if pages:
            detail += f" · {tr('export_center_pdf_pages', count=pages)}"
    return detail


class ExportCenterPage(QWidget):
    def __init__(
        self,
        service: ExportCenterService | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or ExportCenterService()
        self._task: Task | None = None
        self._jobs: list[ExportJob] = self._service.jobs()
        self._available = {job.kind: job.available for job in self._jobs}
        self._files: list[Path] = []
        self._errors: list[ExportResult] = []
        self._checks: dict[ExportKind, QCheckBox] = {}
        self._pending_kinds: list[ExportKind] = []
        self._pending_fmt = ""
        self._pending_dir = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*PAGE_MARGINS)
        layout.setSpacing(PAGE_SPACING)

        self._title = QLabel(tr("export_center_title"))
        self._title.setObjectName("pageTitle")
        layout.addWidget(self._title)
        self._desc = QLabel(tr("export_center_desc"))
        self._desc.setObjectName("pageDesc")
        self._desc.setWordWrap(True)
        layout.addWidget(self._desc)

        self._jobs_card = CardPanel(tr("export_center_jobs"))
        layout.addWidget(self._jobs_card)
        for job in self._jobs:
            check = QCheckBox(tr(job.label_key))
            check.setChecked(job.available)
            check.setEnabled(job.available)
            if not job.available:
                check.setToolTip(f"{tr(job.label_key)} — {tr('export_center_unavailable')}")
            self._jobs_card.body.addWidget(check)
            self._checks[job.kind] = check

        self._options_card = CardPanel(tr("export_center_options"))
        layout.addWidget(self._options_card)

        dir_row = QHBoxLayout()
        dir_row.setSpacing(SPACING_SM)
        self._dir_label = QLabel(tr("export_center_directory"))
        dir_row.addWidget(self._dir_label)
        self._dir_edit = QLineEdit(str(data_root() / "exports"))
        self._dir_edit.setReadOnly(True)
        dir_row.addWidget(self._dir_edit, 1)
        self._browse_button = QPushButton(tr("export_center_browse"))
        self._browse_button.clicked.connect(self._choose_directory)
        dir_row.addWidget(self._browse_button)
        self._options_card.body.addLayout(dir_row)

        format_row = QHBoxLayout()
        format_row.setSpacing(SPACING_SM)
        self._format_label = QLabel(tr("export_center_format"))
        format_row.addWidget(self._format_label)
        self.format_combo = QComboBox()
        for index, fmt in enumerate(FORMATS):
            self.format_combo.addItem(tr(f"export_fmt_{fmt}"), fmt)
            self.format_combo.setItemData(index, fmt)
        format_row.addWidget(self.format_combo)
        format_row.addStretch(1)
        self.export_button = QPushButton(tr("export_center_export"))
        self.export_button.setProperty("primary", True)
        self.export_button.clicked.connect(self.start_export)
        format_row.addWidget(self.export_button)
        self._options_card.body.addLayout(format_row)

        self.status_label = QLabel(tr("export_center_ready"))
        self.status_label.setObjectName("cardSub")
        self._options_card.body.addWidget(self.status_label)

        self._preview_card = CardPanel(tr("export_center_preview"))
        layout.addWidget(self._preview_card, 1)
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setObjectName("plain")
        self._preview_card.body.addWidget(self.preview, 1)

        self._render_preview()

    def _ask_directory(self) -> str:
        return QFileDialog.getExistingDirectory(
            self, tr("export_center_dir_title"), self._dir_edit.text()
        )

    def _choose_directory(self) -> None:
        chosen = self._ask_directory()
        if chosen:
            self._dir_edit.setText(chosen)
            self._render_preview()

    def _selected_kinds(self) -> list[ExportKind]:
        return [
            kind
            for kind, check in self._checks.items()
            if check.isEnabled() and check.isChecked()
        ]

    def _set_busy(self, busy: bool) -> None:
        self.export_button.setEnabled(not busy)
        self.format_combo.setEnabled(not busy)
        self._dir_edit.setEnabled(not busy)
        self._browse_button.setEnabled(not busy)
        for kind, check in self._checks.items():
            check.setEnabled(not busy and self._available.get(kind, False))

    def start_export(self) -> None:
        if self._task is not None:
            return
        selected = self._selected_kinds()
        if not selected:
            self.status_label.setText(tr("export_center_none_selected"))
            return
        fmt = str(self.format_combo.currentData() or FORMATS[0])
        unsupported = [
            tr(job.label_key)
            for job in self._jobs
            if job.kind in selected and fmt not in job.formats
        ]
        if unsupported:
            self.status_label.setText(
                tr("export_center_unsupported", kinds=", ".join(unsupported), fmt=fmt.upper())
            )
            return
        self._files = []
        self._errors = []
        self._pending_kinds = selected
        self._pending_fmt = fmt
        self._pending_dir = self._dir_edit.text()
        self.status_label.setText(tr("export_center_running"))
        self._render_preview()
        self._set_busy(True)
        self._task = Task(self._run_export, parent=self, com=True)
        self._task.done.connect(self._on_done)
        self._task.failed.connect(self._on_failed)
        self._task.finished.connect(self._on_finished)
        self._task.start()

    def _run_export(self) -> ExportBundle:
        return self._service.export_selected(
            self._pending_kinds, self._pending_dir, self._pending_fmt
        )

    def _status_text(self) -> str:
        if self._errors:
            details = "; ".join(
                f"{getattr(item.kind, 'value', item.kind)}: {item.error}"
                for item in self._errors
            )
            return (
                f"{tr('export_center_partial')}: "
                f"{len(self._files)}/{len(self._files) + len(self._errors)} · {details}"
            )
        if self._files:
            return tr("export_center_done", count=len(self._files))
        return tr("export_center_ready")

    def _on_done(self, result: object) -> None:
        if isinstance(result, ExportBundle):
            self._files = list(result.written)
            self._errors = list(result.errors)
        elif isinstance(result, (list, tuple)):
            self._files = [path for path in result if isinstance(path, Path)]
            self._errors = []
        self.status_label.setText(self._status_text())
        self._render_preview()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f"{tr('export_center_failed')}: {message}")

    def _on_finished(self) -> None:
        self._task = None
        self._set_busy(False)

    def _render_preview(self) -> None:
        lines = [tr("export_center_preview_header")]
        for job in self._jobs:
            check = self._checks.get(job.kind)
            mark = "x" if check is not None and check.isChecked() else " "
            suffix = "" if job.available else f" — {tr('export_center_unavailable')}"
            lines.append(f"[{mark}] {tr(job.label_key)}{suffix}")
        lines.append("")
        lines.append(
            f"{tr('export_center_target')}: "
            f"{self._dir_edit.text()} · {str(self.format_combo.currentData() or FORMATS[0]).upper()}"
        )
        if self._files:
            lines.append(tr("export_center_written"))
            lines.extend(f"  {path.name} — {_file_detail(path)}" for path in self._files)
        else:
            lines.append(tr("export_center_preview_hint"))
        for item in self._errors:
            kind = getattr(item.kind, "value", item.kind)
            lines.append(f"  ! {kind}: {item.error}")
        self.preview.setPlainText("\n".join(lines))

    def retranslate(self) -> None:
        self._title.setText(tr("export_center_title"))
        self._desc.setText(tr("export_center_desc"))
        self._jobs_card.set_title(tr("export_center_jobs"))
        self._options_card.set_title(tr("export_center_options"))
        self._preview_card.set_title(tr("export_center_preview"))
        self._dir_label.setText(tr("export_center_directory"))
        self._browse_button.setText(tr("export_center_browse"))
        self._format_label.setText(tr("export_center_format"))
        for index, fmt in enumerate(FORMATS):
            self.format_combo.setItemText(index, tr(f"export_fmt_{fmt}"))
        self.export_button.setText(tr("export_center_export"))
        for job in self._jobs:
            check = self._checks.get(job.kind)
            if check is not None:
                check.setText(tr(job.label_key))
                if not job.available:
                    check.setToolTip(f"{tr(job.label_key)} — {tr('export_center_unavailable')}")
        if self._task is None:
            self.status_label.setText(self._status_text())
        self._render_preview()


__all__ = ["ExportCenterPage"]
