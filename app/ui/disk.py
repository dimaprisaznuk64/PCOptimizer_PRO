from __future__ import annotations

import os
import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.disk import DEFAULT_LIMIT, DEFAULT_MIN_SIZE, DiskAnalyzer
from app.disk.service import DriveUsage, LargeFile, ScanReport

from .components import Bar
from .format import size as fmt_size
from .tasks import Task

SCAN_COLUMNS = ("Name", "Type", "Size")
LARGE_COLUMNS = ("Size", "Modified", "Path")

THRESHOLDS = (
    ("100 MB", 100 * 1024**2),
    ("500 MB", 500 * 1024**2),
    ("1 GB", 1024**3),
)


class DiskPage(QWidget):
    def __init__(self, analyzer: DiskAnalyzer | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._analyzer = analyzer or DiskAnalyzer()
        self._task: Task | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Disk")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "Space analyzer: folder sizes and the largest files on this PC. "
            "Everything here is read-only."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        default_root = os.path.expanduser("~")
        self.path_input = QLineEdit(default_root)
        self.path_input.setPlaceholderText("folder to analyze")
        path_row.addWidget(self.path_input, 1)
        self.browse_button = QPushButton("Browse")
        self.browse_button.setProperty("secondary", True)
        self.browse_button.clicked.connect(self.browse_folder)
        path_row.addWidget(self.browse_button)
        self.refresh_drives_button = QPushButton("Refresh drives")
        self.refresh_drives_button.setProperty("secondary", True)
        self.refresh_drives_button.clicked.connect(self._render_drives)
        path_row.addWidget(self.refresh_drives_button)
        layout.addLayout(path_row)

        self.drives_row = QHBoxLayout()
        self.drives_row.setSpacing(8)
        layout.addLayout(self.drives_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        scan_card = QFrame()
        scan_card.setObjectName("card")
        scan_layout = QVBoxLayout(scan_card)
        scan_layout.setContentsMargins(18, 16, 18, 16)
        scan_layout.setSpacing(8)

        scan_head = QHBoxLayout()
        scan_title = QLabel("FOLDER SCAN")
        scan_title.setObjectName("cardTitle")
        scan_head.addWidget(scan_title)
        scan_head.addStretch(1)
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.start_scan)
        scan_head.addWidget(self.scan_button)
        scan_layout.addLayout(scan_head)

        self.scan_summary = QLabel("—")
        self.scan_summary.setObjectName("cardSub")
        self.scan_summary.setWordWrap(True)
        scan_layout.addWidget(self.scan_summary)

        self.scan_table = QTableWidget(0, len(SCAN_COLUMNS))
        self.scan_table.setHorizontalHeaderLabels(SCAN_COLUMNS)
        self.scan_table.verticalHeader().setVisible(False)
        self.scan_table.setShowGrid(False)
        self.scan_table.setAlternatingRowColors(True)
        self.scan_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.scan_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.scan_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.scan_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.scan_table.itemDoubleClicked.connect(self._on_scan_double_click)
        scan_layout.addWidget(self.scan_table, 1)

        hint = QLabel("Double-click a folder to open it")
        hint.setObjectName("cardSub")
        scan_layout.addWidget(hint)
        splitter.addWidget(scan_card)

        large_card = QFrame()
        large_card.setObjectName("card")
        large_layout = QVBoxLayout(large_card)
        large_layout.setContentsMargins(18, 16, 18, 16)
        large_layout.setSpacing(8)

        large_head = QHBoxLayout()
        large_title = QLabel("LARGE FILES")
        large_title.setObjectName("cardTitle")
        large_head.addWidget(large_title)
        large_head.addStretch(1)
        self.threshold_combo = QComboBox()
        for label, value in THRESHOLDS:
            self.threshold_combo.addItem(label, value)
        self.threshold_combo.setCurrentIndex(1)
        large_head.addWidget(self.threshold_combo)
        self.large_button = QPushButton("Find")
        self.large_button.clicked.connect(self.start_large_files)
        large_head.addWidget(self.large_button)
        large_layout.addLayout(large_head)

        self.large_summary = QLabel("—")
        self.large_summary.setObjectName("cardSub")
        self.large_summary.setWordWrap(True)
        large_layout.addWidget(self.large_summary)

        self.large_table = QTableWidget(0, len(LARGE_COLUMNS))
        self.large_table.setHorizontalHeaderLabels(LARGE_COLUMNS)
        self.large_table.verticalHeader().setVisible(False)
        self.large_table.setShowGrid(False)
        self.large_table.setAlternatingRowColors(True)
        self.large_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.large_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.large_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        large_header = self.large_table.horizontalHeader()
        large_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        large_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        large_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        large_layout.addWidget(self.large_table, 1)
        splitter.addWidget(large_card)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, 1)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        layout.addWidget(self.status_label)

        self._render_drives()

    @property
    def analyzer(self) -> DiskAnalyzer:
        return self._analyzer

    # ---------- drives ----------

    def _render_drives(self) -> None:
        while self.drives_row.count():
            item = self.drives_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        try:
            drives = self._analyzer.list_drives()
        except Exception as e:
            self.status_label.setText(f"Drive list failed: {e}")
            return
        for drive in drives:
            self.drives_row.addWidget(self._drive_widget(drive))
        self.drives_row.addStretch(1)

    def _drive_widget(self, drive: DriveUsage) -> QFrame:
        frame = QFrame()
        frame.setObjectName("card")
        frame.setMinimumWidth(190)
        body = QVBoxLayout(frame)
        body.setContentsMargins(14, 10, 14, 10)
        body.setSpacing(4)

        head = QHBoxLayout()
        name = QLabel(drive.mount)
        name.setObjectName("gpuName")
        head.addWidget(name)
        head.addStretch(1)
        percent = QLabel(f"{drive.percent:.0f}%")
        percent.setObjectName("cardRow")
        head.addWidget(percent)
        body.addLayout(head)

        bar = Bar(height=8)
        bar.set_percent(drive.percent)
        body.addWidget(bar)

        details = QLabel(
            f"{fmt_size(drive.used)} used · {fmt_size(drive.free)} free of {fmt_size(drive.total)}"
        )
        details.setObjectName("cardSub")
        body.addWidget(details)
        return frame

    # ---------- folder scan ----------

    def browse_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Select folder", self.path_input.text().strip()
        )
        if chosen:
            self.path_input.setText(chosen)

    def start_scan(self, root: str | None = None) -> None:
        if self._task is not None:
            return
        target = (root or self.path_input.text()).strip()
        if not target:
            self.status_label.setText("Choose a folder first")
            return
        self.path_input.setText(target)
        self.status_label.setText(f"Scanning {target}…")
        self._set_busy(True)
        self._task = Task(lambda: self._analyzer.scan_directory(target), parent=self)
        self._task.done.connect(self._after_scan)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_scan(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, ScanReport):
            self.status_label.setText(f"Scan failed: {result}")
            return
        self.scan_table.setRowCount(len(result.entries))
        for row, entry in enumerate(result.entries):
            name_item = QTableWidgetItem(entry.name)
            name_item.setData(Qt.ItemDataRole.UserRole, entry.path)
            name_item.setData(Qt.ItemDataRole.UserRole + 1, entry.is_dir)
            name_item.setToolTip(entry.path)
            self.scan_table.setItem(row, 0, name_item)
            self.scan_table.setItem(row, 1, QTableWidgetItem("Folder" if entry.is_dir else "File"))
            size_item = QTableWidgetItem(fmt_size(entry.size))
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.scan_table.setItem(row, 2, size_item)

        message = (
            f"{result.root} · {fmt_size(result.total)} in {result.file_count:,} files "
            f"/ {result.dir_count:,} folders"
        )
        if result.errors:
            message += f" · {result.errors} inaccessible"
        self.scan_summary.setText(message)
        self.status_label.setText(f"Scan complete · {len(result.entries)} entries")

    def _on_scan_double_click(self, item: QTableWidgetItem) -> None:
        if self._task is not None:
            return
        entry_item = self.scan_table.item(item.row(), 0)
        if entry_item is None:
            return
        if not entry_item.data(Qt.ItemDataRole.UserRole + 1):
            return
        self.start_scan(str(entry_item.data(Qt.ItemDataRole.UserRole)))

    # ---------- large files ----------

    def start_large_files(self) -> None:
        if self._task is not None:
            return
        target = self.path_input.text().strip()
        if not target:
            self.status_label.setText("Choose a folder first")
            return
        min_bytes = int(self.threshold_combo.currentData() or DEFAULT_MIN_SIZE)
        self.status_label.setText(f"Searching large files under {target}…")
        self._set_busy(True)
        self._task = Task(
            lambda: self._analyzer.find_large_files(target, min_bytes, DEFAULT_LIMIT),
            parent=self,
        )
        self._task.done.connect(self._after_large_files)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_large_files(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(f"Search failed: {result}")
            return
        files = [f for f in result if isinstance(f, LargeFile)]
        self.large_table.setRowCount(len(files))
        for row, entry in enumerate(files):
            size_item = QTableWidgetItem(fmt_size(entry.size))
            size_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.large_table.setItem(row, 0, size_item)
            modified = time.strftime("%Y-%m-%d %H:%M", time.localtime(entry.modified))
            self.large_table.setItem(row, 1, QTableWidgetItem(modified))
            path_item = QTableWidgetItem(entry.path)
            path_item.setToolTip(entry.path)
            self.large_table.setItem(row, 2, path_item)
        total = sum(f.size for f in files)
        self.large_summary.setText(
            f"{len(files)} files ≥ {self.threshold_combo.currentText()} · {fmt_size(total)} total"
        )
        self.status_label.setText(f"Found {len(files)} large files")

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.scan_button.setEnabled(not busy)
        self.large_button.setEnabled(not busy)
        self.browse_button.setEnabled(not busy)
        self.refresh_drives_button.setEnabled(not busy)
        self.path_input.setEnabled(not busy)
        self.threshold_combo.setEnabled(not busy)
