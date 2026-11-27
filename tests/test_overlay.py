from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QObject, QPoint, Qt, Signal
from PySide6.QtTest import QTest

from app.gaming.telemetry import FrameSample, StaticFrameProvider
from app.overlay import OverlayService, OverlayWidget
from app.settings import SettingsService


class FakeHotkey(QObject):
    triggered = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.registers = 0
        self.unregisters = 0

    def register(self) -> bool:
        self.registers += 1
        return True

    def unregister(self) -> None:
        self.unregisters += 1


def _service(qapp, tmp_path, **kwargs) -> tuple[OverlayService, FakeHotkey]:
    settings = SettingsService(tmp_path / "settings.json")
    hotkey = FakeHotkey()
    service = OverlayService(
        settings,
        hotkey=hotkey,
        provider=StaticFrameProvider([]),
        **kwargs,
    )
    return service, hotkey


def test_overlay_disabled_by_default_still_registers_hotkey(qapp, tmp_path) -> None:
    service, hotkey = _service(qapp, tmp_path)
    try:
        assert service.enabled is False
        assert hotkey.registers == 1
        assert service.widget.isHidden() or not service.widget.isVisible()
    finally:
        service.close()
    assert hotkey.unregisters == 1


def test_overlay_hotkey_enables_hidden_overlay(qapp, tmp_path) -> None:
    service, hotkey = _service(qapp, tmp_path)
    try:
        assert service.enabled is False
        hotkey.triggered.emit()
        assert service.enabled is True
        assert service.widget.isVisible()
        assert SettingsService(tmp_path / "settings.json").get("overlay_enabled") is True
    finally:
        service.close()


def test_overlay_toggle_persists_without_reregistering_hotkey(qapp, tmp_path) -> None:
    service, hotkey = _service(qapp, tmp_path)
    events: list[bool] = []
    service.state_changed.connect(events.append)
    try:
        service.toggle()
        assert service.enabled is True
        assert service.widget.isVisible()
        assert hotkey.registers == 1
        assert service._poll_timer.isActive()
        assert events == [True]
        assert SettingsService(tmp_path / "settings.json").get("overlay_enabled") is True

        service.toggle()
        assert service.enabled is False
        assert hotkey.registers == 1
        assert not service._poll_timer.isActive()
        assert events == [True, False]
    finally:
        service.close()


def test_overlay_keeps_injected_provider_on_source_refresh(qapp, tmp_path) -> None:
    provider = StaticFrameProvider(
        [FrameSample(ts=1.0, frametime_ms=16.7, fps=59.9, source="fake")],
        source="fake",
    )
    settings = SettingsService(tmp_path / "settings.json")
    service = OverlayService(settings, hotkey=FakeHotkey(), provider=provider)
    try:
        service.refresh_source()
        assert service.provider is provider
        assert service.widget._source == "fake"
        assert service.widget._source_available is True
    finally:
        service.close()


def test_overlay_poll_updates_latest_frame(qapp, tmp_path) -> None:
    frame = FrameSample(ts=2.0, frametime_ms=8.0, fps=125.0, source="fake")
    service, _hotkey = _service(qapp, tmp_path)
    service.provider = StaticFrameProvider([frame], source="fake")
    try:
        service.set_enabled(True)
        service.poll_frame()
        assert service.widget._frame is frame
        assert service.widget._current_frame() is frame
    finally:
        service.close()


def test_overlay_retranslate_refreshes_layout(qapp, tmp_path, monkeypatch) -> None:
    service, _hotkey = _service(qapp, tmp_path)
    calls: list[int] = []
    monkeypatch.setattr(service.widget, "refresh_layout", lambda: calls.append(1))
    try:
        service.retranslate()
        assert calls == [1]
    finally:
        service.close()


def test_overlay_close_is_idempotent(qapp, tmp_path) -> None:
    service, hotkey = _service(qapp, tmp_path)
    service.close()
    service.close()
    assert hotkey.unregisters == 1


def test_overlay_widget_stale_frame_is_not_shown(qapp) -> None:
    clock = SimpleNamespace(now=10.0)
    widget = OverlayWidget(clock=lambda: clock.now)
    frame = FrameSample(ts=1.0, frametime_ms=16.7, fps=59.9, source="fake")
    widget.update_frame(frame)
    assert widget._current_frame() is frame
    clock.now = 15.1
    assert widget._current_frame() is None
    widget.close()
    widget.deleteLater()


def test_overlay_widget_restores_saved_position(qapp) -> None:
    widget = OverlayWidget(position="321,222")
    try:
        assert widget.pos() == QPoint(321, 222)
    finally:
        widget.close()


def test_overlay_widget_drag_moves_handle_and_reports_position(qapp) -> None:
    moved: list[tuple[int, int]] = []
    widget = OverlayWidget(
        clock=lambda: 0.0,
        position="100,100",
        on_moved=lambda x, y: moved.append((x, y)),
    )
    try:
        widget.show_overlay()
        qapp.processEvents()
        before = QPoint(widget.pos())
        handle = widget._handle
        QTest.mousePress(handle, Qt.MouseButton.LeftButton, pos=QPoint(20, 10))
        QTest.mouseMove(handle, pos=QPoint(80, 40))
        QTest.mouseRelease(handle, Qt.MouseButton.LeftButton, pos=QPoint(80, 40))
        qapp.processEvents()
        assert widget.pos() == before + QPoint(60, 30)
        assert handle.pos() == widget.pos()
        assert moved == [(widget.x(), widget.y())]
    finally:
        widget.close()


def test_overlay_service_persists_moved_position(qapp, tmp_path) -> None:
    service, _hotkey = _service(qapp, tmp_path)
    try:
        service.widget.move_to(333, 244)
        service.widget._commit_position()
        assert SettingsService(tmp_path / "settings.json").get("overlay_position") == "333,244"
    finally:
        service.close()


def test_overlay_keep_topmost_reasserts_both_windows(qapp, tmp_path, monkeypatch) -> None:
    service, _hotkey = _service(qapp, tmp_path)
    calls: list[object] = []
    monkeypatch.setattr("app.overlay.widget._force_topmost", calls.append)
    try:
        service.set_enabled(True)
        assert service.widget in calls
        assert service.widget._handle in calls
    finally:
        service.close()
