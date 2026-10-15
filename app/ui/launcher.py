from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.gaming import DetectedGame, GamingError, LauncherService
from app.gaming.launcher import SORT_MODES
from app.i18n import tr

from .activity import ActivityLog
from .activity import record as log_action
from .components import attach_empty_hint
from .tasks import Task

_COVER_W = 168
_COVER_H = 94
_TILE_W = 188
_SIDE_MIN = 280
_SIDE_MAX = 420


def _wrap_path(text: str) -> str:
    """Insert zero-width spaces after separators so Qt can break a long path.

    A path like ``D:\\SteamLibrary\\steamapps\\common\\PUBG\\TslGame.exe`` has no
    spaces, so ``setWordWrap`` alone cannot wrap it and the unbreakable run
    inflates the splitter's size hint.
    """
    return text.replace("\\", "\\\u200b").replace("/", "/\u200b")


def _placeholder_cover(name: str, width: int, height: int) -> QPixmap:
    pix = QPixmap(width, height)
    grad = QLinearGradient(0, 0, width, height)
    grad.setColorAt(0.0, QColor("#1b2434"))
    grad.setColorAt(1.0, QColor("#0d1420"))
    painter = QPainter(pix)
    painter.fillRect(0, 0, width, height, grad)
    initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"
    font = painter.font()
    font.setBold(True)
    font.setPixelSize(int(height * 0.42))
    painter.setFont(font)
    painter.setPen(QColor("#5f7699"))
    painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, initials)
    painter.end()
    return pix


def _cover_pixmap(game: DetectedGame, width: int, height: int) -> QPixmap:
    cover = game.cover
    if cover and Path(cover).is_file():
        pix = QPixmap(cover)
        if not pix.isNull():
            scaled = pix.scaled(
                width,
                height,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = max(0, (scaled.width() - width) // 2)
            y = max(0, (scaled.height() - height) // 2)
            return scaled.copy(x, y, width, height)
    return _placeholder_cover(game.name, width, height)


class GameTile(QFrame):
    clicked = Signal(str)
    play = Signal(str)
    favorite = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gameTile")
        self.setFixedWidth(_TILE_W)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._game: DetectedGame | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.cover = QLabel()
        self.cover.setObjectName("tileCover")
        self.cover.setFixedSize(_COVER_W, _COVER_H)
        self.cover.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.cover)

        self.name = QLabel()
        self.name.setObjectName("tileTitle")
        layout.addWidget(self.name)

        self.meta = QLabel()
        self.meta.setObjectName("cardSub")
        layout.addWidget(self.meta)

        actions = QHBoxLayout()
        actions.setSpacing(6)
        self.play_button = QPushButton(tr("launch_play"))
        self.play_button.setProperty("primary", True)
        self.play_button.clicked.connect(self._on_play)
        actions.addWidget(self.play_button)
        actions.addStretch(1)

        self.star_button = QPushButton("☆")
        self.star_button.setObjectName("starButton")
        self.star_button.setCheckable(True)
        self.star_button.setFixedWidth(32)
        self.star_button.clicked.connect(self._on_favorite)
        actions.addWidget(self.star_button)
        layout.addLayout(actions)

    def _on_play(self) -> None:
        if self._game is not None:
            self.play.emit(self._game.id)

    def _on_favorite(self) -> None:
        if self._game is not None:
            self.favorite.emit(self._game.id)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._game is not None:
            self.clicked.emit(self._game.id)
        super().mouseReleaseEvent(event)

    def set_game(self, game: DetectedGame, pinned: bool) -> None:
        self._game = game
        self.name.setText(game.name)
        self.name.setToolTip(game.name)
        if game.running:
            status = tr("launch_status_running")
        elif game.installed:
            status = tr("launch_status_installed")
        else:
            status = tr("launch_status_missing")
        self.meta.setText(f"{game.source} · {status}")
        self.cover.setPixmap(_cover_pixmap(game, _COVER_W, _COVER_H))
        self.play_button.setEnabled(game.installed)
        self.star_button.blockSignals(True)
        self.star_button.setChecked(pinned)
        self.star_button.setText("★" if pinned else "☆")
        self.star_button.blockSignals(False)
        self.star_button.setToolTip(tr("launch_unpin") if pinned else tr("launch_pin"))

    def set_selected(self, selected: bool) -> None:
        if bool(self.property("selected")) != selected:
            self.setProperty("selected", selected)
            self.style().unpolish(self)
            self.style().polish(self)

    @property
    def installed(self) -> bool:
        return self._game is not None and self._game.installed


class LauncherPage(QWidget):
    def __init__(self, service: LauncherService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or LauncherService()
        self._games: dict[str, DetectedGame] = {}
        self._all_games: list[DetectedGame] = []
        self._tiles: dict[str, GameTile] = {}
        self._selected: str | None = None
        self._task: Task | None = None
        self._cols = 3

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel(tr("launch_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("launch_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        toolbar.setSpacing(8)
        self.refresh_button = QPushButton(tr("launch_refresh"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)
        self.add_button = QPushButton(tr("launch_add"))
        self.add_button.setProperty("secondary", True)
        self.add_button.clicked.connect(self.add_custom_game)
        toolbar.addWidget(self.add_button)
        self.status_label = QLabel(tr("launch_selected_hint"))
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("launch_search"))
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(lambda _text: self._refilter())
        filters.addWidget(self.search_edit, 1)
        self.installed_only = QCheckBox(tr("launch_installed_only"))
        self.installed_only.toggled.connect(lambda _checked: self._refilter())
        filters.addWidget(self.installed_only)
        self._sort_labels = {
            "default": "launch_sort_default",
            "recent": "launch_sort_recent",
            "most_played": "launch_sort_most_played",
            "name": "launch_sort_name",
            "favorites": "launch_sort_favorites",
        }
        self.sort_combo = QComboBox()
        for mode in SORT_MODES:
            self.sort_combo.addItem(tr(self._sort_labels[mode]), mode)
        self.sort_combo.currentIndexChanged.connect(lambda _index: self._refilter())
        filters.addWidget(self.sort_combo)
        layout.addLayout(filters)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        # Always keep at least one full tile visible, no matter how narrow the
        # splitter gets — otherwise the tiles collapse to a sliver.
        self._scroll.setMinimumWidth(_TILE_W + 24)
        self._grid_host = QWidget()
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(2, 2, 2, 2)
        self._grid.setSpacing(14)
        self._grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_host)
        splitter.addWidget(self._scroll)

        side = QWidget()
        side.setMinimumWidth(_SIDE_MIN)
        side.setMaximumWidth(_SIDE_MAX)
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(10)

        details = QFrame()
        details.setObjectName("card")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(18, 16, 18, 16)
        details_layout.setSpacing(8)
        self._details_title = QLabel(tr("launch_details"))
        self._details_title.setObjectName("cardTitle")
        details_layout.addWidget(self._details_title)
        self.detail_name = QLabel(tr("launch_selected_hint"))
        self.detail_name.setObjectName("gpuName")
        self.detail_name.setWordWrap(True)
        self.detail_name.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        details_layout.addWidget(self.detail_name)
        self.detail_rows: dict[str, QLabel] = {}
        for key in ("source", "status", "path", "last_played", "play_count"):
            row = QLabel("")
            row.setObjectName("cardRow")
            row.setWordWrap(True)
            # Ignore sizeHint width: an unbreakable long path would otherwise
            # force the side panel to expand and squeeze the tiles.
            row.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            row.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.detail_rows[key] = row
            details_layout.addWidget(row)
        self.remove_button = QPushButton(tr("launch_remove"))
        self.remove_button.setProperty("danger", True)
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self.start_remove_custom)
        details_layout.addWidget(self.remove_button)
        side_layout.addWidget(details)

        history_card = QFrame()
        history_card.setObjectName("card")
        history_layout = QVBoxLayout(history_card)
        history_layout.setContentsMargins(18, 16, 18, 16)
        history_layout.setSpacing(8)
        header = QHBoxLayout()
        self._history_title = QLabel(tr("launch_history"))
        self._history_title.setObjectName("cardTitle")
        header.addWidget(self._history_title)
        header.addStretch(1)
        self.clear_history_button = QPushButton(tr("launch_clear"))
        self.clear_history_button.setObjectName("linkButton")
        self.clear_history_button.clicked.connect(self.start_clear_history)
        header.addWidget(self.clear_history_button)
        history_layout.addLayout(header)
        self.history_list = QListWidget()
        self.history_list.setObjectName("historyList")
        attach_empty_hint(self.history_list, "launch_history_empty")
        history_layout.addWidget(self.history_list, 1)
        side_layout.addWidget(history_card, 1)

        splitter.addWidget(side)
        self._splitter = splitter
        self._side = side
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        # stretchFactor only applies when the user resizes; the initial split
        # comes from sizeHint, so pin the starting sizes explicitly.
        splitter.setSizes([900, _SIDE_MIN + 60])
        layout.addWidget(splitter, 1)

    # ---------- lifecycle ----------

    @property
    def service(self) -> LauncherService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._games and self._task is None:
            self.start_refresh()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        cols = max(1, (self._grid_host.width() - 2) // (_TILE_W + 14))
        if cols != self._cols and self._tiles:
            self._cols = cols
            self._relayout()

    def retranslate(self) -> None:
        self._title.setText(tr("launch_title"))
        self._desc.setText(tr("launch_desc"))
        self.refresh_button.setText(tr("launch_refresh"))
        self.add_button.setText(tr("launch_add"))
        self.remove_button.setText(tr("launch_remove"))
        self.clear_history_button.setText(tr("launch_clear"))
        self._details_title.setText(tr("launch_details"))
        self._history_title.setText(tr("launch_history"))
        self.search_edit.setPlaceholderText(tr("launch_search"))
        self.installed_only.setText(tr("launch_installed_only"))
        for index, mode in enumerate(SORT_MODES):
            self.sort_combo.setItemText(index, tr(self._sort_labels[mode]))
        for game in self._games.values():
            tile = self._tiles.get(game.id)
            if tile is not None:
                tile.set_game(game, self._service.is_favorite(game.id))
        self._on_selection_changed()
        self._render_history()

    # ---------- detection ----------

    def start_refresh(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("launch_detecting"))
        self._set_busy(True)
        self._task = Task(self._service.detect, parent=self)
        self._task.done.connect(self._apply_games)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_games(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, list):
            self.status_label.setText(tr("launch_failed", msg=result))
            return
        self._all_games = list(result)
        self._refilter()

    def _refilter(self) -> None:
        if self._task is not None:
            return
        sort_mode = self.sort_combo.currentData() or "default"
        viewed = self._service.view(
            self._all_games,
            search=self.search_edit.text(),
            installed_only=self.installed_only.isChecked(),
            sort=sort_mode,
        )
        self._games = {game.id: game for game in viewed}
        self._render_grid()
        installed = sum(1 for g in self._all_games if g.installed)
        pinned = sum(1 for g in self._all_games if self._service.is_favorite(g.id))
        filtered = bool(self.search_edit.text().strip()) or self.installed_only.isChecked()
        if self._all_games and not viewed and filtered:
            self.status_label.setText(tr("launch_no_matches"))
        else:
            self.status_label.setText(tr("launch_summary", installed=installed, pinned=pinned))
        self._render_history()
        self._on_selection_changed()

    # ---------- grid ----------

    def _clear_grid(self) -> None:
        self._tiles.clear()
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _render_grid(self) -> None:
        self._clear_grid()
        width = self._grid_host.width() or self._scroll.width()
        self._cols = max(1, (width - 2) // (_TILE_W + 14)) if width > _TILE_W else 3
        for index, game in enumerate(self._games.values()):
            tile = GameTile()
            tile.set_game(game, self._service.is_favorite(game.id))
            tile.clicked.connect(self.select_game)
            tile.play.connect(self.start_launch)
            tile.favorite.connect(self.toggle_favorite)
            self._tiles[game.id] = tile
            self._grid.addWidget(tile, index // self._cols, index % self._cols)
        if self._selected in self._tiles:
            self._tiles[self._selected].set_selected(True)
        elif self._games:
            first = next(iter(self._games))
            self.select_game(first)

    def _relayout(self) -> None:
        self._clear_grid()
        for index, game in enumerate(self._games.values()):
            tile = GameTile()
            tile.set_game(game, self._service.is_favorite(game.id))
            tile.clicked.connect(self.select_game)
            tile.play.connect(self.start_launch)
            tile.favorite.connect(self.toggle_favorite)
            if game.id == self._selected:
                tile.set_selected(True)
            self._tiles[game.id] = tile
            self._grid.addWidget(tile, index // self._cols, index % self._cols)

    # ---------- selection ----------

    def select_game(self, game_id: str) -> None:
        self._selected = game_id
        for key, tile in self._tiles.items():
            tile.set_selected(key == game_id)
        self._on_selection_changed()

    def _on_selection_changed(self) -> None:
        game = self._games.get(self._selected) if self._selected else None
        if game is None:
            self.detail_name.setText(tr("launch_selected_hint"))
            for label in self.detail_rows.values():
                label.setText("")
            self.remove_button.setEnabled(False)
            return
        self.detail_name.setText(game.name)
        if game.running:
            status = tr("launch_status_running")
        elif game.installed:
            status = tr("launch_status_installed")
        else:
            status = tr("launch_status_missing")
        self.detail_rows["source"].setText(tr("launch_source", value=game.source))
        self.detail_rows["status"].setText(tr("launch_status", value=status))
        self.detail_rows["path"].setText(
            tr("launch_path", value=_wrap_path(game.location or "—"))
        )
        self.detail_rows["last_played"].setText(
            tr("launch_last_played", value=self._format_when(self._service.last_played(game.id)))
        )
        self.detail_rows["play_count"].setText(
            tr("launch_play_count", value=self._service.launch_count(game.id))
        )
        self.remove_button.setEnabled(game.custom and self._task is None)

    # ---------- actions ----------

    def start_launch(self, game_id: str) -> None:
        game = self._games.get(game_id)
        if game is None or self._task is not None or not game.installed:
            return
        self._set_busy(True)
        self.status_label.setText(tr("game_launching", name=game.name))
        self._task = Task(lambda: self._service.launch(game), parent=self)
        self._task.done.connect(lambda pid, g=game: self._after_launch(g, pid))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_launch(self, game: DetectedGame, result: object) -> None:
        self._task = None
        self._set_busy(False)
        pid = result if isinstance(result, int) else 0
        self.status_label.setText(
            tr("launch_started", name=game.name, pid=pid) if pid else tr("launch_started_nopid", name=game.name)
        )
        ActivityLog.instance().gaming_active = self._service.gaming.active
        log_action(tr("act_launch"), game.name)
        self._render_history()
        self._on_selection_changed()

    def toggle_favorite(self, game_id: str) -> None:
        game = self._games.get(game_id)
        if game is None:
            return
        pinned = self._service.toggle_favorite(game_id)
        tile = self._tiles.get(game_id)
        if tile is not None:
            tile.set_game(game, pinned)
        self._refilter()
        self.status_label.setText(
            tr("launch_pinned_msg", name=game.name) if pinned else tr("launch_unpinned_msg", name=game.name)
        )

    def start_remove_custom(self) -> None:
        game = self._games.get(self._selected) if self._selected else None
        if game is None or self._task is not None or not game.custom:
            return
        answer = QMessageBox.question(
            self,
            tr("launch_remove_title"),
            tr("launch_remove_msg", name=game.name),
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
        self.status_label.setText(tr("launch_removed", name=name))
        self._selected = None
        self.start_refresh()

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

    def start_clear_history(self) -> None:
        if self._task is not None or not self._service.history(limit=1):
            return
        answer = QMessageBox.question(
            self,
            tr("launch_clear_title"),
            tr("launch_clear_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._service.clear_history()
        self.status_label.setText(tr("launch_cleared"))
        self._render_history()
        self._on_selection_changed()

    # ---------- history ----------

    def _render_history(self) -> None:
        self.history_list.clear()
        for record in self._service.history(limit=20):
            item = QListWidgetItem(f"{self._format_when(record.when)}   {record.name}")
            item.setToolTip(record.exe)
            self.history_list.addItem(item)

    @staticmethod
    def _format_when(when: str | None) -> str:
        if not when:
            return tr("launch_never")
        try:
            dt = datetime.fromisoformat(when)
        except ValueError:
            return when
        if dt.date() == datetime.now().date():
            return dt.strftime("%H:%M")
        return dt.strftime("%d.%m %H:%M")

    # ---------- misc ----------

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("launch_failed", msg=message))

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        for tile in self._tiles.values():
            tile.play_button.setEnabled(not busy and tile.installed)
        if not busy:
            self._on_selection_changed()
