from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.optimizer import PROFILES, ApplyReport, OptimizerService, OptimizerState

from .tasks import Task


class OptimizerPage(QWidget):
    def __init__(self, service: OptimizerService | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page")
        self._service = service or OptimizerService()
        self._task: Task | None = None
        self._state: OptimizerState | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 32)
        layout.setSpacing(10)

        title = QLabel("Optimizer")
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(
            "Safe, reversible Windows tuning: power plan, Game Mode, "
            "hardware-accelerated GPU scheduling and visual effects. "
            "A system restore point is created before every change."
        )
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh state")
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)

        self.revert_button = QPushButton("Revert last apply")
        self.revert_button.setProperty("secondary", True)
        self.revert_button.setEnabled(False)
        self.revert_button.clicked.connect(self.start_revert)
        toolbar.addWidget(self.revert_button)

        self.status_label = QLabel("Idle")
        self.status_label.setObjectName("cardSub")
        toolbar.addWidget(self.status_label, 1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        profiles_column = QVBoxLayout()
        profiles_column.setSpacing(8)
        self.profile_cards: dict[str, tuple[QFrame, QLabel]] = {}
        for name, spec in PROFILES.items():
            card = QFrame()
            card.setObjectName("card")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 14, 18, 14)
            card_layout.setSpacing(4)

            head = QHBoxLayout()
            name_label = QLabel(name.title())
            name_label.setObjectName("gpuName")
            head.addWidget(name_label)
            head.addStretch(1)
            apply_button = QPushButton("Apply")
            apply_button.setProperty("secondary", True)
            apply_button.clicked.connect(lambda _checked=False, n=name: self.start_apply(n))
            head.addWidget(apply_button)
            card_layout.addLayout(head)

            summary = QLabel(str(spec["description"]))
            summary.setObjectName("cardSub")
            summary.setWordWrap(True)
            card_layout.addWidget(summary)

            match_label = QLabel("")
            match_label.setObjectName("cardRow")
            card_layout.addWidget(match_label)

            profiles_column.addWidget(card)
            self.profile_cards[name] = (card, match_label)
        profiles_column.addStretch(1)
        profiles_widget = QWidget()
        profiles_widget.setLayout(profiles_column)
        splitter.addWidget(profiles_widget)

        state_card = QFrame()
        state_card.setObjectName("card")
        state_card.setMinimumWidth(320)
        state_layout = QVBoxLayout(state_card)
        state_layout.setContentsMargins(18, 16, 18, 16)
        state_layout.setSpacing(8)

        state_title = QLabel("CURRENT STATE")
        state_title.setObjectName("cardTitle")
        state_layout.addWidget(state_title)

        self.state_rows: dict[str, QLabel] = {}
        for key in ("power", "game_mode", "hags", "visual", "privileges"):
            row = QLabel("…")
            row.setObjectName("cardRow")
            row.setWordWrap(True)
            self.state_rows[key] = row
            state_layout.addWidget(row)

        self.state_errors = QLabel("")
        self.state_errors.setObjectName("cardSub")
        self.state_errors.setWordWrap(True)
        self.state_errors.setVisible(False)
        state_layout.addWidget(self.state_errors)

        note = QLabel(
            "Every apply writes a backup of the previous values; "
            "Revert restores them. No hidden registry tweaks."
        )
        note.setObjectName("cardSub")
        note.setWordWrap(True)
        state_layout.addWidget(note)
        state_layout.addStretch(1)
        splitter.addWidget(state_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

    @property
    def service(self) -> OptimizerService:
        return self._service

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if self._state is None and self._task is None:
            self.start_refresh()

    def start_refresh(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText("Reading system state…")
        self._set_busy(True)
        self._task = Task(self._service.state, parent=self)
        self._task.done.connect(self._apply_state)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_state(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, OptimizerState):
            self.status_label.setText(f"Load failed: {result}")
            return
        self._state = result
        self.state_rows["power"].setText(f"Power plan  {result.power_name}")
        self.state_rows["game_mode"].setText(
            "Game Mode  " + ("on" if result.game_mode else "off" if result.game_mode is False else "default")
        )
        self.state_rows["hags"].setText(
            "GPU scheduling  " + ("on" if result.hags else "off" if result.hags is False else "not set")
        )
        self.state_rows["visual"].setText(f"Visual effects  {result.visual_name}")
        self.state_rows["privileges"].setText(
            "Privileges  " + ("administrator" if result.is_admin else "standard user (UAC prompts for admin actions)")
        )
        self.state_errors.setVisible(bool(result.errors))
        self.state_errors.setText(" · ".join(result.errors))
        self.revert_button.setEnabled(self._service.backup_exists())
        self._refresh_profile_matches(result)
        self.status_label.setText("State loaded")

    def _refresh_profile_matches(self, state: OptimizerState) -> None:
        for name, (_card, match_label) in self.profile_cards.items():
            spec = PROFILES[name]
            parts: list[str] = []
            power = spec.get("power")
            if power:
                parts.append("✓ power" if state.power_guid == power else "→ power")
            game_mode = spec.get("game_mode")
            if game_mode is not None:
                parts.append("✓ game mode" if state.game_mode == game_mode else "→ game mode")
            hags = spec.get("hags")
            if hags is not None:
                parts.append("✓ HAGS" if state.hags == hags else "→ HAGS")
            visual = spec.get("visual")
            if visual is not None:
                parts.append("✓ visual" if state.visual_fx == visual else "→ visual")
            current = all(p.startswith("✓") for p in parts) if parts else False
            match_label.setText(("CURRENT PROFILE · " if current else "") + "  ".join(parts))

    def start_apply(self, name: str) -> None:
        if self._task is not None:
            return
        answer = QMessageBox.question(
            self,
            "Apply profile",
            (
                f"Apply the {name.title()} profile?\n\n"
                "A system restore point is created first. "
                "You can undo the change with Revert last apply."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(f"Applying {name}…")
        self._set_busy(True)
        self._task = Task(lambda: self._service.apply_profile(name), parent=self)
        self._task.done.connect(lambda result, n=name: self._after_apply(n, result))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_apply(self, name: str, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, ApplyReport):
            self.status_label.setText(f"Apply failed: {result}")
            return
        if result.errors and not result.applied:
            self.status_label.setText(f"{name}: FAILED — {result.errors[0]}")
        elif result.errors:
            self.status_label.setText(f"{name}: partial — {result.errors[0]}")
        else:
            self.status_label.setText(f"{name}: applied {len(result.applied)} change(s)")
        self.start_refresh()

    def start_revert(self) -> None:
        if self._task is not None:
            return
        answer = QMessageBox.question(
            self,
            "Revert",
            "Restore the previous system settings from the last backup?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText("Reverting…")
        self._set_busy(True)
        self._task = Task(self._service.revert, parent=self)
        self._task.done.connect(self._after_revert)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_revert(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if isinstance(result, ApplyReport):
            if result.errors:
                self.status_label.setText(f"Revert: partial — {result.errors[0]}")
            else:
                self.status_label.setText(f"Reverted {len(result.applied)} change(s)")
        else:
            self.status_label.setText(f"Revert failed: {result}")
        self.start_refresh()

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(f"Failed: {message}")

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        if busy:
            self.revert_button.setEnabled(False)
            for _card, _label in self.profile_cards.values():
                for button in _card.findChildren(QPushButton):
                    button.setEnabled(False)
        elif self._state is not None:
            self.revert_button.setEnabled(self._service.backup_exists())
            for _card, _label in self.profile_cards.values():
                for button in _card.findChildren(QPushButton):
                    button.setEnabled(True)
