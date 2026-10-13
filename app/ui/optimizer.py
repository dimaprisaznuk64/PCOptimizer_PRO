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

from app.i18n import tr
from app.optimizer import PROFILES, ApplyReport, OptimizerService, OptimizerState
from app.restore import (
    STATUS_CANCELLED,
    STATUS_CREATED,
    STATUS_DISABLED,
    STATUS_SKIPPED,
    RestoreResult,
)

from .components import glyph_tile
from .activity import record as log_action
from .tasks import Task


_PROFILE_ICONS = {"balanced": "health", "gaming": "gaming", "performance": "cpu"}

_PROFILE_TR = {
    "balanced": "opt_profile_balanced",
    "gaming": "opt_profile_gaming",
    "performance": "opt_profile_performance",
}

_VALUE_TR = {
    "Balanced": "opt_val_balanced", "High performance": "opt_val_highperf", "Ultimate performance": "opt_val_ultimate",
    "Power saver": "opt_val_saver", "Unknown": "opt_val_unknown", "Custom": "opt_val_custom",
    "Let Windows decide": "opt_val_vis_default", "Adjust for best performance": "opt_val_vis_perf",
    "Adjust for best appearance": "opt_val_vis_look",
}


def _value(text: str) -> str:
    key = _VALUE_TR.get(text)
    return tr(key) if key else text


_PROFILE_DESC_TR = {
    "balanced": "opt_profdesc_balanced",
    "gaming": "opt_profdesc_gaming",
    "performance": "opt_profdesc_performance",
}

_FIELD_TR = {"power": "opt_field_power", "game_mode": "opt_field_game", "hags": "opt_field_hags", "visual": "opt_field_visual"}


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

        title = QLabel(tr("opt_title"))
        title.setObjectName("pageTitle")
        layout.addWidget(title)
        desc = QLabel(tr("opt_desc"))
        desc.setObjectName("pageDesc")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self._title = title
        self._desc = desc

        toolbar = QHBoxLayout()
        self.refresh_button = QPushButton(tr("opt_refresh"))
        self.refresh_button.setProperty("secondary", True)
        self.refresh_button.clicked.connect(self.start_refresh)
        toolbar.addWidget(self.refresh_button)

        self.restore_button = QPushButton(tr("opt_restore_btn"))
        self.restore_button.setProperty("secondary", True)
        self.restore_button.clicked.connect(self.start_restore_point)
        toolbar.addWidget(self.restore_button)

        self.revert_button = QPushButton(tr("opt_revert"))
        self.revert_button.setProperty("secondary", True)
        self.revert_button.setEnabled(False)
        self.revert_button.clicked.connect(self.start_revert)
        toolbar.addWidget(self.revert_button)

        self.status_label = QLabel(tr("opt_idle"))
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
            head.setSpacing(12)
            head.addWidget(glyph_tile(_PROFILE_ICONS.get(name.lower(), "optimizer")))
            name_label = QLabel(tr(_PROFILE_TR.get(name.lower(), "opt_title")))
            name_label.setObjectName("gpuName")
            head.addWidget(name_label)
            head.addStretch(1)
            apply_button = QPushButton(tr("opt_apply"))
            apply_button.setProperty("secondary", True)
            apply_button.clicked.connect(lambda _checked=False, n=name: self.start_apply(n))
            head.addWidget(apply_button)
            card_layout.addLayout(head)

            summary = QLabel(tr(_PROFILE_DESC_TR.get(name.lower(), "opt_desc")))
            summary.setProperty("profile", name.lower())
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

        state_title = QLabel(tr("opt_current_state"))
        state_title.setObjectName("cardTitle")
        state_layout.addWidget(state_title)

        self._state_title = state_title

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

        self.note = QLabel(tr("opt_note"))
        self.note.setObjectName("cardSub")
        self.note.setWordWrap(True)
        state_layout.addWidget(self.note)
        state_layout.addStretch(1)
        splitter.addWidget(state_card)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._profile_names: dict[str, QLabel] = {}
        for name, (card, _match) in self.profile_cards.items():
            labels = card.findChildren(QLabel, "gpuName")
            if labels:
                self._profile_names[name] = labels[0]

    def retranslate(self) -> None:
        """Refresh static texts after a language change."""
        self._title.setText(tr("opt_title"))
        self._desc.setText(tr("opt_desc"))
        self.refresh_button.setText(tr("opt_refresh"))
        self.restore_button.setText(tr("opt_restore_btn"))
        self.revert_button.setText(tr("opt_revert"))
        self._state_title.setText(tr("opt_current_state"))
        self.note.setText(tr("opt_note"))
        for name, label in self._profile_names.items():
            label.setText(tr(_PROFILE_TR.get(name.lower(), "opt_title")))
        for card, _match in self.profile_cards.values():
            for lbl in card.findChildren(QLabel):
                key = lbl.property("profile")
                if key:
                    lbl.setText(tr(_PROFILE_DESC_TR.get(str(key), "opt_desc")))
        for card, _match in self.profile_cards.values():
            for button in card.findChildren(QPushButton):
                button.setText(tr("opt_apply"))
        if self._state is not None:
            self._render_state(self._state)

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
        self.status_label.setText(tr("opt_reading"))
        self._set_busy(True)
        self._task = Task(self._service.state, parent=self)
        self._task.done.connect(self._apply_state)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _apply_state(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, OptimizerState):
            self.status_label.setText(tr("opt_load_failed", msg=result))
            return
        self._state = result
        self._render_state(result)
        self.revert_button.setEnabled(self._service.backup_exists())
        self._refresh_profile_matches(result)
        self.status_label.setText(tr("opt_state_loaded"))

    def _render_state(self, result: OptimizerState) -> None:
        def _tri(value: bool | None, on_key: str, off_key: str, none_key: str) -> str:
            return tr(on_key) if value is True else tr(off_key) if value is False else tr(none_key)

        self.state_rows["power"].setText(tr("opt_power", name=_value(result.power_name)))
        self.state_rows["game_mode"].setText(
            tr("opt_game_mode", state=_tri(result.game_mode, "opt_on", "opt_off", "opt_default"))
        )
        self.state_rows["hags"].setText(
            tr("opt_hags", state=_tri(result.hags, "opt_on", "opt_off", "opt_not_set"))
        )
        self.state_rows["visual"].setText(tr("opt_visual", name=_value(result.visual_name)))
        self.state_rows["privileges"].setText(
            tr("opt_privileges", value=tr("opt_admin") if result.is_admin else tr("opt_standard"))
        )
        self.state_errors.setVisible(bool(result.errors))
        self.state_errors.setText(" · ".join(result.errors))

    def _refresh_profile_matches(self, state: OptimizerState) -> None:
        for name, (_card, match_label) in self.profile_cards.items():
            spec = PROFILES[name]
            parts: list[str] = []
            power = spec.get("power")
            if power:
                parts.append(
                    tr("opt_match_ok", name=tr("opt_field_power"))
                    if state.power_guid == power
                    else tr("opt_match_next", name=tr("opt_field_power"))
                )
            game_mode = spec.get("game_mode")
            if game_mode is not None:
                parts.append(
                    tr("opt_match_ok", name=tr("opt_field_game"))
                    if state.game_mode == game_mode
                    else tr("opt_match_next", name=tr("opt_field_game"))
                )
            hags = spec.get("hags")
            if hags is not None:
                parts.append(
                    tr("opt_match_ok", name="HAGS") if state.hags == hags else tr("opt_match_next", name="HAGS")
                )
            visual = spec.get("visual")
            if visual is not None:
                parts.append(
                    tr("opt_match_ok", name=tr("opt_field_visual"))
                    if state.visual_fx == visual
                    else tr("opt_match_next", name=tr("opt_field_visual"))
                )
            current = all(p.startswith("✓") for p in parts) if parts else False
            match_label.setText((tr("opt_current_profile") if current else "") + "  ".join(parts))

    def start_apply(self, name: str) -> None:
        if self._task is not None:
            return
        display = tr(_PROFILE_TR.get(name.lower(), "opt_title"))
        answer = QMessageBox.question(
            self,
            tr("opt_confirm_title"),
            tr("opt_confirm_msg", name=display),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        want_restore = self._ask_restore_point()
        self.status_label.setText(tr("opt_applying", name=display.lower()))
        self._set_busy(True)
        self._task = Task(
            lambda: self._service.apply_profile(name, with_restore_point=want_restore), parent=self
        )
        self._task.done.connect(lambda result, n=name: self._after_apply(n, result))
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _ask_restore_point(self) -> bool:
        answer = QMessageBox.question(
            self,
            tr("opt_restore_ask_title"),
            tr("opt_restore_ask_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def _after_apply(self, name: str, result: object) -> None:
        self._task = None
        self._set_busy(False)
        display = tr(_PROFILE_TR.get(name.lower(), "opt_title")).lower()
        if not isinstance(result, ApplyReport):
            self.status_label.setText(tr("opt_apply_failed", msg=result))
            return
        if not result.applied and result.restore_status not in (None, STATUS_CREATED):
            self.status_label.setText(
                self._restore_message(RestoreResult(False, result.restore_status, result.errors[0] if result.errors else ""))
            )
            self.revert_button.setEnabled(self._service.backup_exists())
            return
        if result.errors and not result.applied:
            self.status_label.setText(tr("opt_failed_line", name=display, msg=result.errors[0]))
        elif result.errors:
            self.status_label.setText(tr("opt_partial", name=display, msg=result.errors[0]))
        else:
            self.status_label.setText(tr("opt_applied", name=display, count=len(result.applied)))
        log_action(tr("act_opt"), display, "warn" if result.errors else "ok")
        if result.restore_status == STATUS_CREATED:
            self._notify(True, tr("opt_restore_apply_created"))
        self.start_refresh()

    def start_restore_point(self) -> None:
        if self._task is not None:
            return
        self.status_label.setText(tr("opt_restore_creating"))
        self._set_busy(True)
        self._task = Task(
            lambda: self._service.create_restore_point("PCOptimizer_PRO manual"), parent=self
        )
        self._task.done.connect(self._after_restore_point)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_restore_point(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if not isinstance(result, RestoreResult):
            message = tr("opt_restore_failed", msg=result)
            self.status_label.setText(message)
            self._notify(False, message)
            return
        message = self._restore_message(result)
        self.status_label.setText(message)
        if result.status == STATUS_CREATED:
            log_action(tr("act_opt"), result.label or tr("opt_restore_btn"), "ok")
            self._notify(True, message)
        elif result.status == STATUS_DISABLED:
            self._offer_enable_protection()
        else:
            self._notify(False, message)

    def _notify(self, success: bool, text: str) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning)
        box.setWindowTitle(tr("opt_restore_ask_title"))
        box.setText(text)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.exec()

    @staticmethod
    def _restore_message(result: RestoreResult) -> str:
        if result.status == STATUS_CREATED:
            return tr("opt_restore_created", name=result.label or "")
        if result.status == STATUS_SKIPPED:
            return tr("opt_restore_skipped")
        if result.status == STATUS_DISABLED:
            return tr("opt_restore_disabled")
        if result.status == STATUS_CANCELLED:
            return tr("opt_restore_cancelled")
        return tr("opt_restore_failed", msg=result.message or "?")

    def _offer_enable_protection(self) -> None:
        answer = QMessageBox.question(
            self,
            tr("opt_restore_enable_title"),
            tr("opt_restore_enable_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self._set_busy(True)
        self.status_label.setText(tr("opt_restore_creating"))
        self._task = Task(self._service.enable_system_protection, parent=self)
        self._task.done.connect(self._after_enable_protection)
        self._task.failed.connect(self._on_task_failed)
        self._task.start()

    def _after_enable_protection(self, result: object) -> None:
        self._task = None
        self._set_busy(False)
        if isinstance(result, RestoreResult) and result.ok:
            self.status_label.setText(tr("opt_restore_enable_done"))
        else:
            message = result.message if isinstance(result, RestoreResult) else str(result)
            self.status_label.setText(tr("opt_restore_failed", msg=message))

    def start_revert(self) -> None:
        if self._task is not None:
            return
        answer = QMessageBox.question(
            self,
            tr("opt_revert_title"),
            tr("opt_revert_msg"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.status_label.setText(tr("opt_reverting"))
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
                self.status_label.setText(tr("opt_partial", name=tr("opt_revert_title").lower(), msg=result.errors[0]))
            else:
                self.status_label.setText(tr("opt_reverted_n", count=len(result.applied)))
        else:
            self.status_label.setText(tr("opt_revert_failed", msg=result))
        self.start_refresh()

    def _on_task_failed(self, message: str) -> None:
        self._task = None
        self._set_busy(False)
        self.status_label.setText(tr("opt_failed", msg=message))

    def _set_busy(self, busy: bool) -> None:
        self.refresh_button.setEnabled(not busy)
        self.restore_button.setEnabled(not busy)
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
