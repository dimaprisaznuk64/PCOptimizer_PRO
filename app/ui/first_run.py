from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)

from app.i18n import tr
from app.settings import SettingsService

from .combos import COMBO_WIDTH, tune_combo
from .components import CardTitleLabel
from .theme import CARD_PADDING, PAGE_SPACING, SPACING_LG, SPACING_MD, SPACING_SM, SPACING_XL


class FirstRunWizard(QDialog):
    settings_applied = Signal(dict)
    open_settings_requested = Signal()

    THEMES = ("TITANIUM", "GRAPHITE", "ARCTIC")
    SCALES = (100, 110, 125, 150)

    def __init__(self, service: SettingsService | None = None, parent=None) -> None:
        super().__init__(parent)
        self._service = service or SettingsService()
        self._step = 0
        self.changes: dict[str, object] = {}
        self.setWindowTitle(tr("wiz_title"))
        self.setMinimumSize(620, 520)
        self.resize(720, 620)
        self.setObjectName("firstRunWizard")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING)
        outer.setSpacing(PAGE_SPACING)

        self.step_label = QLabel()
        self.step_label.setObjectName("cardSub")
        self.title_label = QLabel(tr("wiz_title"))
        self.title_label.setObjectName("pageTitle")
        self.subtitle_label = QLabel(tr("wiz_subtitle"))
        self.subtitle_label.setObjectName("pageDesc")
        self.subtitle_label.setWordWrap(True)
        outer.addWidget(self.step_label)
        outer.addWidget(self.title_label)
        outer.addWidget(self.subtitle_label)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_welcome())
        self._stack.addWidget(self._build_preferences())
        self._stack.addWidget(self._build_finish())
        outer.addWidget(self._stack, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING_SM)
        self.skip_button = QPushButton(tr("wiz_skip"))
        self.skip_button.setObjectName("wizSkip")
        self.skip_button.setProperty("secondary", True)
        self.skip_button.clicked.connect(self.skip)
        buttons.addWidget(self.skip_button)
        buttons.addStretch(1)
        self.back_button = QPushButton(tr("wiz_back"))
        self.back_button.setObjectName("wizBack")
        self.back_button.setProperty("secondary", True)
        self.back_button.clicked.connect(self.back)
        buttons.addWidget(self.back_button)
        self.next_button = QPushButton(tr("wiz_next"))
        self.next_button.setObjectName("wizNext")
        self.next_button.setProperty("primary", True)
        self.next_button.clicked.connect(self.next)
        buttons.addWidget(self.next_button)
        self.finish_button = QPushButton(tr("wiz_finish"))
        self.finish_button.setObjectName("wizFinish")
        self.finish_button.setProperty("primary", True)
        self.finish_button.clicked.connect(self.finish)
        buttons.addWidget(self.finish_button)
        outer.addLayout(buttons)

        self._show_step(0)

    def _build_welcome(self) -> QFrame:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        layout.setSpacing(SPACING_MD)
        heading = CardTitleLabel(tr("wiz_welcome_heading"))
        layout.addWidget(heading)
        body = QLabel(tr("wiz_welcome_body"))
        body.setObjectName("pageDesc")
        body.setWordWrap(True)
        layout.addWidget(body)
        self._welcome_features = []
        for key in ("wiz_feature_1", "wiz_feature_2", "wiz_feature_3"):
            feature = QLabel("•  " + tr(key))
            feature.setObjectName("cardSub")
            feature.setWordWrap(True)
            layout.addWidget(feature)
            self._welcome_features.append((feature, key))
        layout.addStretch(1)
        self._welcome_heading = heading
        self._welcome_body = body
        return page

    def _build_preferences(self) -> QFrame:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        layout.setSpacing(SPACING_MD)
        heading = CardTitleLabel(tr("wiz_pref_heading"))
        layout.addWidget(heading)
        self._pref_heading = heading

        self.language_combo = QComboBox()
        tune_combo(self.language_combo, COMBO_WIDTH)
        self.theme_combo = QComboBox()
        tune_combo(self.theme_combo, COMBO_WIDTH)
        self.scale_combo = QComboBox()
        tune_combo(self.scale_combo, COMBO_WIDTH)
        self._fill_language_combo()
        self._fill_theme_combo()
        self._fill_scale_combo()
        self._set_combo_data(self.language_combo, str(self._service.get("language")))
        self._set_combo_data(self.theme_combo, str(self._service.get("theme")))
        self._set_combo_data(self.scale_combo, int(self._service.get("ui_scale")))

        self._language_label = self._add_field(layout, tr("wiz_language"), self.language_combo)
        self._theme_label = self._add_field(layout, tr("wiz_theme"), self.theme_combo)
        self._scale_label = self._add_field(layout, tr("wiz_scale"), self.scale_combo)

        self.update_check = QCheckBox(tr("wiz_option_updates"))
        self.temp_check = QCheckBox(tr("wiz_option_temp"))
        self.usage_check = QCheckBox(tr("wiz_option_usage"))
        self.quiet_check = QCheckBox(tr("wiz_option_quiet"))
        self.tray_check = QCheckBox(tr("wiz_option_tray"))
        self.update_check.setChecked(bool(self._service.get("update_check_enabled")))
        self.temp_check.setChecked(bool(self._service.get("temp_alerts_enabled")))
        self.usage_check.setChecked(bool(self._service.get("usage_alerts_enabled")))
        self.quiet_check.setChecked(bool(self._service.get("alerts_quiet_during_games")))
        self.tray_check.setChecked(bool(self._service.get("minimize_to_tray")))
        for check in (
            self.update_check,
            self.temp_check,
            self.usage_check,
            self.quiet_check,
            self.tray_check,
        ):
            layout.addWidget(check)
        layout.addStretch(1)
        return page

    def _build_finish(self) -> QFrame:
        page = QFrame()
        page.setObjectName("card")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(SPACING_XL, SPACING_LG, SPACING_XL, SPACING_LG)
        layout.setSpacing(SPACING_MD)
        self._finish_heading = CardTitleLabel(tr("wiz_finish_heading"))
        layout.addWidget(self._finish_heading)
        self._finish_body = QLabel(tr("wiz_finish_body"))
        self._finish_body.setObjectName("pageDesc")
        self._finish_body.setWordWrap(True)
        layout.addWidget(self._finish_body)
        self.open_settings_check = QCheckBox(tr("wiz_open_settings"))
        layout.addWidget(self.open_settings_check)
        layout.addStretch(1)
        return page

    @staticmethod
    def _add_field(layout: QVBoxLayout, text: str, field: QComboBox) -> QLabel:
        label = QLabel(text)
        label.setObjectName("cardSub")
        layout.addWidget(label)
        layout.addWidget(field)
        return label

    @staticmethod
    def _set_combo_data(combo: QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _fill_language_combo(self) -> None:
        self.language_combo.blockSignals(True)
        self.language_combo.clear()
        for code in ("UA", "EN"):
            self.language_combo.addItem(tr(f"wiz_lang_{code}"), code)
        self.language_combo.blockSignals(False)

    def _fill_theme_combo(self) -> None:
        self.theme_combo.blockSignals(True)
        self.theme_combo.clear()
        for key in self.THEMES:
            label = tr(f"theme_{key}")
            if label == f"theme_{key}":
                label = key.title()
            self.theme_combo.addItem(label, key)
        self.theme_combo.blockSignals(False)

    def _fill_scale_combo(self) -> None:
        self.scale_combo.blockSignals(True)
        self.scale_combo.clear()
        for value in self.SCALES:
            self.scale_combo.addItem(tr(f"wiz_scale_{value}"), value)
        self.scale_combo.blockSignals(False)

    def _show_step(self, step: int) -> None:
        self._step = max(0, min(step, self._stack.count() - 1))
        self._stack.setCurrentIndex(self._step)
        self.step_label.setText(
            tr("wiz_step", step=self._step + 1, total=self._stack.count())
        )
        self.back_button.setVisible(self._step > 0)
        self.next_button.setVisible(self._step < self._stack.count() - 1)
        self.finish_button.setVisible(self._step == self._stack.count() - 1)
        self.skip_button.setVisible(True)

    def next(self) -> None:
        self._show_step(self._step + 1)

    def back(self) -> None:
        self._show_step(self._step - 1)

    def collect_values(self) -> dict[str, object]:
        return {
            "language": str(self.language_combo.currentData()),
            "theme": str(self.theme_combo.currentData()),
            "ui_scale": int(self.scale_combo.currentData()),
            "update_check_enabled": self.update_check.isChecked(),
            "temp_alerts_enabled": self.temp_check.isChecked(),
            "usage_alerts_enabled": self.usage_check.isChecked(),
            "alerts_quiet_during_games": self.quiet_check.isChecked(),
            "minimize_to_tray": self.tray_check.isChecked(),
            "first_run_completed": True,
        }

    def _valid_choice(self) -> bool:
        valid = (
            self.language_combo.currentData() in ("UA", "EN")
            and self.theme_combo.currentData() in self.THEMES
            and self.scale_combo.currentData() in self.SCALES
        )
        if not valid:
            self._warn(tr("wiz_invalid_choice"))
        return valid

    def _warn(self, message: str) -> None:
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.warning(self, tr("wiz_title"), message)

    def finish(self) -> None:
        if not self._valid_choice():
            return
        values = self.collect_values()
        try:
            for key, value in values.items():
                self._service.set(key, value)
            self._service.save()
        except (OSError, ValueError) as exc:
            self._warn(tr("wiz_save_failed", msg=exc))
            return
        self.changes = dict(values)
        self.settings_applied.emit(dict(values))
        if self.open_settings_check.isChecked():
            self.open_settings_requested.emit()
        self.accept()

    def skip(self) -> None:
        try:
            self._service.set("first_run_completed", True)
            self._service.save()
        except (OSError, ValueError) as exc:
            self._warn(tr("wiz_save_failed", msg=exc))
            return
        self.changes = {"first_run_completed": True}
        self.reject()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("wiz_title"))
        self.title_label.setText(tr("wiz_title"))
        self.subtitle_label.setText(tr("wiz_subtitle"))
        self.step_label.setText(
            tr("wiz_step", step=self._step + 1, total=self._stack.count())
        )
        self._welcome_heading.setText(tr("wiz_welcome_heading"))
        self._welcome_body.setText(tr("wiz_welcome_body"))
        for label, key in self._welcome_features:
            label.setText("•  " + tr(key))
        self._pref_heading.setText(tr("wiz_pref_heading"))
        self._language_label.setText(tr("wiz_language"))
        self._theme_label.setText(tr("wiz_theme"))
        self._scale_label.setText(tr("wiz_scale"))
        self._fill_language_combo()
        self._fill_theme_combo()
        self._fill_scale_combo()
        self._set_combo_data(self.language_combo, str(self._service.get("language")))
        self._set_combo_data(self.theme_combo, str(self._service.get("theme")))
        self._set_combo_data(self.scale_combo, int(self._service.get("ui_scale")))
        self.update_check.setText(tr("wiz_option_updates"))
        self.temp_check.setText(tr("wiz_option_temp"))
        self.usage_check.setText(tr("wiz_option_usage"))
        self.quiet_check.setText(tr("wiz_option_quiet"))
        self.tray_check.setText(tr("wiz_option_tray"))
        self._finish_heading.setText(tr("wiz_finish_heading"))
        self._finish_body.setText(tr("wiz_finish_body"))
        self.open_settings_check.setText(tr("wiz_open_settings"))
        self.skip_button.setText(tr("wiz_skip"))
        self.back_button.setText(tr("wiz_back"))
        self.next_button.setText(tr("wiz_next"))
        self.finish_button.setText(tr("wiz_finish"))
