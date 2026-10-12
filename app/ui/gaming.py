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
from app.i18n import tr

from .activity import ActivityLog
from .activity import record as log_action
from .components import attach_empty_hint
from .tasks import Task

COLUMN_KEYS = ("game_col_game", "game_col_source", "game_col_status", "game_col_location")


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

        title = QLabel(tr("game_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("game_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)

        self.mode_button = QPushButton(tr("game_enable_btn"))
        self.mode_button.setProperty("primary", True)
        self.mode_button.clicked.connect(self.start_toggle_mode)
        toolbar.addWidget(self.mode_button)

        self.refresh_button = QPushButton(tr("game_refresh"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)

        self.add_button = QPushButton(tr("game_add"))
        self.add_button.setProperty("secondary", True)
        self.add_button.clicked.connect(self.add_custom_game)
        toolbar.addWidget(self.add_button)

        self.mode_label = QLabel(tr("game_mode_off"))
        self.mode_label.setObjectName("pageBadge")
        toolbar.addWidget(self.mode_label)

        self.status_label = QLabel(tr("game_idle"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.table = QTableWidget(0, len(COLUMN_KEYS))
        attach_empty_hint(self.table, "empty_games")
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLUMN_KEYS])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
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

        details_title = QLabel(tr("game_details"))
        details_title.setObjectName("cardTitle")
        details_layout.addWidget(details_title)

        self._details_title = details_title

        self.detail_name = QLabel(tr("game_select_hint"))
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
        self.launch_button = QPushButton(tr("game_launch"))
        self.launch_button.setEnabled(False)
        self.launch_button.clicked.connect(self.start_launch)
        actions.addWidget(self.launch_button)

        self.remove_button = QPushButton(tr("game_remove"))
        self.remove_button.setProperty("danger", True)
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.start_remove_custom)
        actions.addWidget(self.remove_button)
        details_layout.addLayout(actions)

        self.note = QLabel(tr("game_note"))
        self.note.setObjectName("cardSub")
        self.note.setWordWrap(True)
        details_layout.addWidget(self.note)
        details_layout.addStretch(1)
        splitter.addWidget(details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("game_title"))
        self._desc.setText(tr("game_desc"))
        self.refresh_button.setText(tr("game_refresh"))
        self.add_button.setText(tr("game_add"))
        self.launch_button.setText(tr("game_launch"))
        self.remove_button.setText(tr("game_remove"))
        self._details_title.setText(tr("game_details"))
        self.note.setText(tr("game_note"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLUMN_KEYS])
        self._on_selection_changed()

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
        self.status_label.setText(tr("game_detecting"))
        self._set_busy(True)
        self._task = Task(self._service.detect, parent=self)
        self._task.done.connect(self._apply_games)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_games(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(tr("game_load_failed", msg=result))
            return
        self._games = list(result)
        self._render_table()
        installed = sum(1 for g in self._games if g.installed)
        running = sum(1 for g in self._games if g.running)
        self.status_label.setText(tr("game_summary", installed=installed, running=running))
        self._update_mode_label()
        self._on_selection_changed()

    def _update_mode_label(self) -> None:
        if self._service.active:
            self.mode_label.setText(tr("game_mode_on"))
            self.mode_button.setText(tr("game_disable_btn"))
        else:
            self.mode_label.setText(tr("game_mode_off"))
            self.mode_button.setText(tr("game_enable_btn"))

    def start_toggle_mode(self) -> None:
        if self._task is not None:
            return
        if self._service.active:
            question = tr("game_confirm_disable")
            runner = self._service.deactivate
            running_text = tr("game_disabling")
        else:
            question = tr("game_confirm_enable")
            runner = self._service.activate
            running_text = tr("game_enabling")
        answer = QMessageBox.question(
            self,
            tr("game_mode_title"),
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
            self.status_label.setText(tr("game_apply_failed", msg=errors[0]))
        elif errors:
            self.status_label.setText(tr("game_partial", msg=errors[0]))
        else:
            self.status_label.setText(tr("game_changes", count=len(applied)))
        ActivityLog.instance().gaming_active = self._service.active
        log_action(tr("act_game"), tr("game_mode_on") if self._service.active else tr("game_mode_off"), "warn" if errors else "ok")
        self._update_mode_label()

    def start_launch(self) -> None:
        game = self._selected_game()
        if game is None or self._task is not None:
            return
        self._set_busy(True)
        self.status_label.setText(tr("game_launching", name=game.name))
        self._task = Task(lambda: self._service.launch(game), parent=self)
        self._task.done.connect(self._after_launch)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_launch(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        pid = result if isinstance(result, int) else 0
        self.status_label.setText(tr("game_started_pid", pid=pid) if pid else tr("game_started"))

    def add_custom_game(self) -> None:
        if self._task is not None:
            return
        name, ok = QInputDialog.getText(self, tr("game_add_title"), tr("game_add_label"))
        if not ok or not str(name).strip():
            return
        path, _filter = QFileDialog.getOpenFileName(
            self, tr("game_add_select"), "", tr("game_add_filter")
        )
        if not path:
            return
        try:
            self._service.add_custom(str(name), path)
        except GamingError as e:
            QMessageBox.warning(self, tr("game_add_warn"), str(e))
            return
        self.status_label.setText(tr("game_added", name=name))
        self.start_refresh()

    def start_remove_custom(self) -> None:
        game = self._selected_game()
        if game is None or self._task is not None or not game.custom:
            return
        answer = QMessageBox.question(
            self,
            tr("game_remove_title"),
            tr("game_remove_msg", name=game.name),
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
        self.status_label.setText(tr("game_removed_n", name=name))
        self.start_refresh()

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("game_failed", msg=message))

    def _set_busy(self, busy: bool) -> None:
        self.mode_button.setEnabled(not busy)
        self.refresh_button.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        if busy:
            self.launch_button.setEnabled(False)
            self.remove_button.setEnabled(False)
        else:
            self._on_selection_changed()

    def _render_status(self, game: DetectedGame) -> str:
        if game.running:
            return tr("game_status_running")
        if game.installed:
            return tr("game_status_installed")
        return tr("game_status_not_installed")

    def _render_table(self) -> None:
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self._games))
        for row, game in enumerate(self._games):
            name_item = QTableWidgetItem(game.name)
            name_item.setData(Qt.ItemDataRole.UserRole, game.id)
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, QTableWidgetItem(game.source))
            self.table.setItem(row, 2, QTableWidgetItem(self._render_status(game)))
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
            self.detail_name.setText(tr("game_select_hint"))
            for label in self.detail_rows.values():
                label.setText("")
            self.launch_button.setEnabled(False)
            self.remove_button.setEnabled(False)
            return
        self.detail_name.setText(game.name)
        self.detail_rows["source"].setText(tr("game_detail_source", value=game.source))
        self.detail_rows["status"].setText(tr("game_detail_status", value=self._render_status(game)))
        self.detail_rows["location"].setText(tr("game_detail_location", value=game.location))
        busy = self._task is not None
        self.launch_button.setEnabled(game.installed and not busy)
        self.remove_button.setEnabled(game.custom and not busy)
