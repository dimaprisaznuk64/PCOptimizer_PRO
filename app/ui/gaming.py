from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gaming.service import DetectedGame, GamingError, GamingService

from .tasks import Task

COLUMNS = ("Game", "Source", "Status", "Location")


class GamingPage(QWidget):
    def __init__(self, service: GamingService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or GamingService()
        self._games: list[DetectedGame] = []
        self._task: Task | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Gaming Mode")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "One-click gaming profile: high performance power plan, Game Mode and HAGS. "
            "A restore point is created first and every change can be reverted."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.mode_button = QPushButton("Enable gaming mode")
        self.mode_button.clicked.connect(self.start_toggle_mode)
        toolbar.addWidget(self.mode_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)

        self.add_button = QPushButton("Add custom game")
        self.add_button.setProperty("secondary", True)
        self.add_button.clicked.connect(self.add_custom_game)
        toolbar.addWidget(self.add_button)

        self.mode_label = QLabel("Mode: OFF")
        self.mode_label.setObjectName("pageBadge")
        toolbar.addWidget(self.mode_label)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.table)

        details = QFrame()
        details.setObjectName("card")
        details.setMinimumWidth(300)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(8)

        details_title = QLabel("DETAILS")
        details_title.setObjectName("cardTitle")
        details_layout.addWidget(details_title)

        self.detail_name = QLabel("Select a game")
        self.detail_name.setObjectName("gpuName")
        self.detail_name.setWordWrap(True)
        details_layout.addWidget(self.detail_name)

        self.detail_rows: dict[str, QLabel] = {}
        for key in ("source", "status", "location"):
            row = QLabel("")
            row.setObjectName("cardRow")
            row.setWordWrap(True)
            self.detail_rows[key] = row
            details_layout.addWidget(row)

        actions = QHBoxLayout()
        self.launch_button = QPushButton("Launch")
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self.start_launch)
        actions.addWidget(self.launch_button)

        self.remove_button = QPushButton("Remove")
        self.remove_button.setProperty("danger", True)
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.start_remove_custom)
        actions.addWidget(self.remove_button)
        details_layout.addLayout(actions)

        note = QLabel(
            "Games are detected from Steam libraries. Custom entries are stored "
            "locally and can be removed at any time."
        )
        note.setObjectName("cardSub")
        note.setWordWrap(True)
        details_layout.addWidget(note)
        details_layout.addStretch(1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> GamingService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._games and self._task is None:
            self.start_refresh()

    def start_refresh(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Detecting games…")
        self._set_busy(True)
        self._task = Task(self._service.detect, parent=self)
        self._task.done.connect(self._apply_games)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_games(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(f"Load failed: {result}")
            return
        self._games = list(result)
        self._render_table()
        installed = sum(1 for g in self._games if g.installed)
        running = sum(1 for g in self._games if g.running)
        self.status_label.setText(f"{installed} installed · {running} running")
        self._update_mode_label()
        self._on_selection_changed()

    def _update_mode_label(self) -> None:
        if self._service.active:
            self.mode_label.setText("Mode: ON")
            self.mode_button.setText("Disable gaming mode")
        else:
            self.mode_label.setText("Mode: OFF")
            self.mode_button.setText("Enable gaming mode")

    def start_toggle_mode(self) -> None:
        if self._task is not None:
            return
        if self._service.active:
            question = "Disable gaming mode and restore the previous settings?"
            runner = self._service.deactivate
            running_text = "Disabling gaming mode…"
        else:
            question = (
                "Enable gaming mode?\n\n"
                "Creates a restore point, then applies the GAMING profile "
                "(high performance power plan, Game Mode on, HAGS on)."
            )
            runner = self._service.activate
            running_text = "Enabling gaming mode…"
        answer = QMessageBox.question(
            self,
            "Gaming mode",
            question,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(running_text)
        self._set_busy(True)
        self._task = Task(runner, parent=self)
        self._task.done.connect(self._after_mode_change)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_mode_change(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        errors = getattr(result, "errors", ()) or ()
        applied = getattr(result, "applied", ()) or ()
        if errors and not applied:
            self.status_label.setText(f"FAILED — {errors[0]}")
        elif errors:
            self.status_label.setText(f"partial — {errors[0]}")
        else:
            self.status_label.setText(f"{len(applied)} change(s) applied")
        self._update_mode_label()

    def start_launch(self) -> None:
        game = self._selected_game()
        if game is None or self._task is not None:
            return
        self._set_busy(True)
        self.status_label.setText(f"Launching {game.name}…")
        self._task = Task(lambda: self._service.launch(game), parent=self)
        self._task.done.connect(self._after_launch)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_launch(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        pid = result if isinstance(result, int) else 0
        self.status_label.setText(f"Started (pid {pid})" if pid else "Started")

    def add_custom_game(self) -> None:
        if self._task is not None:
            return
        name, ok = QInputDialog.getText(self, "Add custom game", "Game name:")
        if not ok or not str(name).strip():
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, "Select game executable", "", "Executables (*.exe);;All files (*.*)"
        )
        if not path:
            return
        try:
            self._service.add_custom(str(name), path)
        except GamingError as e:
            QMessageBox.warning(self, "Add game", str(e))
            return
        self.status_label.setText(f"Added {name}")
        self.start_refresh()

    def start_remove_custom(self) -> None:
        game = self._selected_game()
        if game is None or self._task is not None or not game.custom:
            return
        answer = QMessageBox.question(
            self,
            "Remove game",
            f"Remove {game.name} from the custom list? "
            "The game itself is not touched.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self._task = Task(lambda: self._service.remove_custom(game.id), parent=self)
        self._task.done.connect(lambda _r, name=game.name: self._after_remove(name))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_remove(self, name: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Removed {name}")
        self.start_refresh()

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.mode_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        if busy:
            self.launch_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self._on_selection_changed()

    def _render_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._games))
        for row, game in enumerate(self._games):
            name_item = QTableWidgetItem(game.name)
            name_item.setData(Qt.ItemDataRole.UserRole, game.id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(game.source))
            status = "Running" if game.running else ("Installed" if game.installed else "Not installed")
            self.table.setItem(row, 2, QTableWidgetItem(status))
            location_item = QTableWidgetItem(game.location)
            location_item.setToolTip(game.location)
            self.table.setItem(row, 3, location_item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)

    def _selected_game(self) -> DetectedGame | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        if item is None:
            return None
        game_id = item.data(Qt.ItemDataRole.UserRole)
        return self._service.game_by_id(self._games, game_id)

    def _on_selection_changed(self) -> None:
        game = self._selected_game()
        if game is None:
            self.detail_name.setText("Select a game")
            for label in self.detail_rows.values():
                label.setText("")
            self.launch_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return
        self.detail_name.setText(game.name)
        self.detail_rows["source"].setText(f"Source  {game.source}")
        status = "Running" if game.running else ("Installed" if game.installed else "Not installed")
        self.detail_rows["status"].setText(f"Status  {status}")
        self.detail_rows["location"].setText(f"Location  {game.location}")
        busy = self._task is not None
        self.launch_button.setEnabled(game.installed and not busy)
        self.remove_button.setEnabled(game.custom and not busy)
