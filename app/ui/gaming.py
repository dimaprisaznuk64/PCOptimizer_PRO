from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gaming.service import GAMING_PROFILES, DetectedGame, GamingError, GamingService
from app.gaming.telemetry import GameSession, GamingTelemetryService
from app.i18n import tr

from .activity import ActivityLog, outcome_level
from .activity import record as log_action
from .components import CardTitleLabel, attach_empty_hint
from .tasks import Task
from .theme import CARD_PADDING

COLUMN_KEYS = ("game_col_game", "game_col_source", "game_col_status", "game_col_location")
SESSION_COLUMN_KEYS = (
    "game_telemetry_hist_col_time",
    "game_telemetry_hist_col_game",
    "game_telemetry_hist_col_profile",
    "game_telemetry_hist_col_fps",
    "game_telemetry_hist_col_low",
)


class GamingPage(QWidget):
    def __init__(
        self,
        service: GamingService | None = None,
        parent: QWidget | None = None,
        *,
        telemetry: GamingTelemetryService | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or GamingService()
        self._telemetry = telemetry or GamingTelemetryService()
        self._games: list[DetectedGame] = []
        self._task: Task | None = None
        self._snapshot = None
        self._session_history_loaded = False
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.setInterval(500)
        self._telemetry_timer.timeout.connect(self._poll_telemetry)

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
        details.setMinimumWidth(0)
        details.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        details_layout.setSpacing(8)

        details_title = CardTitleLabel(tr("game_details"))
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

        profile_row = QHBoxLayout()
        profile_label = QLabel(tr("game_profile_label"))
        profile_label.setObjectName("cardSub")
        profile_row.addWidget(profile_label)
        self.profile_combo = QComboBox()
        for profile in GAMING_PROFILES:
            self.profile_combo.addItem(tr(f"opt_profile_{profile.lower()}"), profile)
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        profile_row.addWidget(self.profile_combo, 1)
        details_layout.addLayout(profile_row)

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

        telemetry_card = QFrame()
        telemetry_card.setObjectName("card")
        telemetry_layout = QVBoxLayout(telemetry_card)
        telemetry_layout.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        telemetry_layout.setSpacing(8)
        telemetry_title = CardTitleLabel(tr("game_telemetry_title"))
        telemetry_layout.addWidget(telemetry_title)
        self._telemetry_title = telemetry_title

        telemetry_toolbar = QHBoxLayout()
        self.session_start_button = QPushButton(tr("game_telemetry_start"))
        self.session_start_button.setProperty("primary", True)
        self.session_start_button.clicked.connect(self.start_telemetry_session)
        telemetry_toolbar.addWidget(self.session_start_button)
        self.session_stop_button = QPushButton(tr("game_telemetry_stop"))
        self.session_stop_button.setProperty("secondary", True)
        self.session_stop_button.setEnabled(False)
        self.session_stop_button.clicked.connect(self.stop_telemetry_session)
        telemetry_toolbar.addWidget(self.session_stop_button)
        self.telemetry_source_label = QLabel("")
        self.telemetry_source_label.setObjectName("cardSub")
        telemetry_toolbar.addWidget(self.telemetry_source_label, 1)
        telemetry_layout.addLayout(telemetry_toolbar)

        self.telemetry_values = QLabel(tr("game_telemetry_idle"))
        self.telemetry_values.setObjectName("cardRow")
        self.telemetry_values.setWordWrap(True)
        telemetry_layout.addWidget(self.telemetry_values)
        self.telemetry_resources = QLabel("")
        self.telemetry_resources.setObjectName("cardSub")
        telemetry_layout.addWidget(self.telemetry_resources)
        self.telemetry_temp = QLabel("")
        self.telemetry_temp.setObjectName("cardSub")
        telemetry_layout.addWidget(self.telemetry_temp)
        self.telemetry_before = QLabel("")
        self.telemetry_before.setObjectName("cardSub")
        telemetry_layout.addWidget(self.telemetry_before)

        history_title = CardTitleLabel(tr("game_telemetry_history_title"))
        telemetry_layout.addWidget(history_title)
        self._session_history_title = history_title
        self.session_history = QTableWidget(0, len(SESSION_COLUMN_KEYS))
        self.session_history.setHorizontalHeaderLabels([tr(k) for k in SESSION_COLUMN_KEYS])
        self.session_history.verticalHeader().setVisible(False)
        self.session_history.setShowGrid(False)
        self.session_history.setAlternatingRowColors(True)
        self.session_history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.session_history.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        attach_empty_hint(self.session_history, "game_telemetry_history_empty")
        session_header = self.session_history.horizontalHeader()
        for col in range(len(SESSION_COLUMN_KEYS)):
            session_header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        session_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        telemetry_layout.addWidget(self.session_history)
        layout.addWidget(telemetry_card, 0)

        self._render_telemetry(None)

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
        current_profile = self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in GAMING_PROFILES:
            self.profile_combo.addItem(tr(f"opt_profile_{profile.lower()}"), profile)
        index = self.profile_combo.findData(current_profile)
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.profile_combo.blockSignals(False)
        self.session_start_button.setText(tr("game_telemetry_start"))
        self.session_stop_button.setText(tr("game_telemetry_stop"))
        self._telemetry_title.setText(tr("game_telemetry_title"))
        self._session_history_title.setText(tr("game_telemetry_history_title"))
        self.table.setHorizontalHeaderLabels([tr(k) for k in COLUMN_KEYS])
        self.session_history.setHorizontalHeaderLabels([tr(k) for k in SESSION_COLUMN_KEYS])
        self._on_selection_changed()
        self._render_telemetry(self._telemetry.session)

    @property
    def service(self) -> GamingService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._games and self._task is None:
            self.start_refresh()
        if not self._session_history_loaded:
            self._refresh_session_history()
            self._session_history_loaded = True

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

    def apply_snapshot(self, snapshot) -> None:
        self._snapshot = snapshot

    def start_telemetry_session(self) -> None:
        game = self._selected_game()
        if game is None or self._telemetry.active:
            return
        session = self._telemetry.start_session(game.id, game.name, game.profile, self._snapshot)
        self._telemetry_timer.start()
        self.session_start_button.setEnabled(False)
        self.session_stop_button.setEnabled(True)
        self.status_label.setText(tr("game_telemetry_started", name=game.name))
        self._render_telemetry(session)

    def stop_telemetry_session(self) -> None:
        if not self._telemetry.active:
            return
        session = self._telemetry.finish_session()
        self._telemetry_timer.stop()
        self.session_start_button.setEnabled(True)
        self.session_stop_button.setEnabled(False)
        self._refresh_session_history()
        if session is not None:
            self.status_label.setText(tr("game_telemetry_saved", count=session.frames_count))
        self._render_telemetry(None)

    def _poll_telemetry(self) -> None:
        session = self._telemetry.poll(self._snapshot)
        if session is not None:
            self._render_telemetry(session)

    @staticmethod
    def _value(value: float | None, suffix: str = "") -> str:
        return f"{value:.0f}{suffix}" if value is not None else "—"

    def _render_telemetry(self, session: GameSession | None) -> None:
        if not self._telemetry.available:
            self.telemetry_source_label.setText(tr("game_telemetry_no_source"))
        else:
            self.telemetry_source_label.setText(
                tr("game_telemetry_source", source=self._telemetry.source_name)
            )
        if session is None:
            self.telemetry_values.setText(tr("game_telemetry_idle"))
            self.telemetry_resources.setText("")
            self.telemetry_temp.setText("")
            self.telemetry_before.setText("")
            return
        stats = session.stats
        parts = [tr("game_telemetry_fps", avg=stats.fps_avg)]
        if stats.frametime_avg:
            parts.append(tr("game_telemetry_frame", ms=stats.frametime_avg))
        if stats.low_1 is not None:
            parts.append(tr("game_telemetry_low1", fps=stats.low_1))
        if stats.low_01 is not None:
            parts.append(tr("game_telemetry_low01", fps=stats.low_01))
        parts.append(tr("game_telemetry_frames", count=stats.samples))
        self.telemetry_values.setText(" · ".join(parts))
        after = session.after
        if any(v is not None for v in (after.cpu_percent, after.ram_percent, after.gpu_percent)):
            self.telemetry_resources.setText(
                tr(
                    "game_telemetry_resources",
                    cpu=after.cpu_percent or 0.0,
                    ram=after.ram_percent or 0.0,
                    gpu=after.gpu_percent or 0.0,
                )
            )
        else:
            self.telemetry_resources.setText("")
        if any(v is not None for v in (after.system_temp, after.gpu_temp, after.gpu_hotspot)):
            self.telemetry_temp.setText(
                tr(
                    "game_telemetry_temp",
                    cpu=after.system_temp or 0.0,
                    gpu=after.gpu_temp or 0.0,
                    hot=after.gpu_hotspot or 0.0,
                )
            )
        else:
            self.telemetry_temp.setText("")
        before = session.before
        if any(v is not None for v in (before.cpu_percent, after.cpu_percent, before.ram_percent, after.ram_percent)):
            self.telemetry_before.setText(
                tr(
                    "game_telemetry_before_after",
                    before=before.cpu_percent or 0.0,
                    after=after.cpu_percent or 0.0,
                    rb=before.ram_percent or 0.0,
                    ra=after.ram_percent or 0.0,
                )
            )
        else:
            self.telemetry_before.setText("")

    def _refresh_session_history(self) -> None:
        sessions = self._telemetry.sessions(limit=10)
        self.session_history.setRowCount(len(sessions))
        for row, session in enumerate(sessions):
            when = datetime.fromtimestamp(session.started).strftime("%Y-%m-%d %H:%M")
            values = (
                when,
                session.game_name,
                tr(f"opt_profile_{session.profile.lower()}"),
                self._value(session.stats.fps_avg),
                self._value(session.stats.low_1),
            )
            for col, value in enumerate(values):
                self.session_history.setItem(row, col, QTableWidgetItem(value))

    def _on_profile_changed(self) -> None:
        game = self._selected_game()
        profile = self.profile_combo.currentData()
        if game is None or not profile:
            return
        try:
            self._service.set_game_profile(game.id, str(profile))
        except GamingError as e:
            QMessageBox.warning(self, tr("game_add_warn"), str(e))
            return
        game = replace(game, profile=str(profile))
        for index, item in enumerate(self._games):
            if item.id == game.id:
                self._games[index] = game
                break
        self.status_label.setText(tr("game_profile_label") + ": " + self.profile_combo.currentText())

    def start_toggle_mode(self) -> None:
        if self._task is not None:
            return
        active = self._service.active
        if active:
            question = tr("game_confirm_disable")
            running_text = tr("game_disabling")
        else:
            question = tr("game_confirm_enable")
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
        if active:
            runner = self._service.deactivate
        else:
            selected = self._selected_game()
            profile = selected.profile if selected else self._service.active_profile
            want_restore = (
                QMessageBox.question(
                    self,
                    tr("game_restore_ask_title"),
                    tr("game_restore_ask_msg"),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                == QMessageBox.StandardButton.Yes
            )
            def runner() -> object:
                return self._service.activate(with_restore_point=want_restore, profile=profile)
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
        log_action(
            tr("act_game"),
            tr("game_mode_on") if self._service.active else tr("game_mode_off"),
            outcome_level(has_errors=bool(errors), achieved=bool(applied)),
        )
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
        index = self.profile_combo.findData(game.profile)
        self.profile_combo.blockSignals(True)
        self.profile_combo.setCurrentIndex(max(index, 0))
        self.profile_combo.blockSignals(False)
        self.detail_rows["source"].setText(tr("game_detail_source", value=game.source))
        self.detail_rows["status"].setText(tr("game_detail_status", value=self._render_status(game)))
        self.detail_rows["location"].setText(tr("game_detail_location", value=game.location))
        busy = self._task is not None
        self.launch_button.setEnabled(game.installed and not busy)
        self.remove_button.setEnabled(game.custom and not busy)
