from __future__ import annotations

import ctypes
import time
from collections import deque
from collections.abc import Callable

from PySide6.QtCore import QObject, QPoint, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QFont,
    QGuiApplication,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
)
from PySide6.QtWidgets import QApplication, QWidget
from shiboken6 import isValid

from app.gaming.telemetry import FrameSample, ResourceMetrics, frame_stats
from app.i18n import tr

from .hotkey import OverlayHotkey

_FRESH_SECONDS = 5.0
_FRAME_HISTORY = 240
_TOPMOST = -1
_SWP_RESTORE = 0x0001 | 0x0002 | 0x0010 | 0x0040


def _force_topmost(window: QWidget) -> None:
    user32 = getattr(ctypes, "windll", None)
    if user32 is None:
        return
    try:
        user32.SetWindowPos(int(window.winId()), _TOPMOST, 0, 0, 0, 0, _SWP_RESTORE)
    except Exception:
        return


class OverlayHandle(QWidget):
    def __init__(self, owner: OverlayWidget, *, on_moved: Callable[[int, int], None] | None = None) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self._owner = owner
        self._on_moved = on_moved
        self._drag_origin: QPoint | None = None
        self._drag_start = QPoint()
        self.setObjectName("overlayHandle")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setCursor(QCursor(Qt.CursorShape.SizeAllCursor))
        self.setFixedHeight(owner._handle_height())
        self.resize(owner.width(), self.height())

    def align(self) -> None:
        self.setFixedHeight(self._owner._handle_height())
        self.resize(self._owner.width(), self.height())
        self.move(self._owner.pos())
        _force_topmost(self)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            event.ignore()
            return
        self._drag_origin = event.globalPosition().toPoint()
        self._drag_start = QPoint(self._owner.pos())
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is None:
            event.ignore()
            return
        delta = event.globalPosition().toPoint() - self._drag_origin
        self._owner.move_to(self._drag_start.x() + delta.x(), self._drag_start.y() + delta.y())
        event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_origin is None:
            event.ignore()
            return
        self._drag_origin = None
        self._owner._commit_position()
        event.accept()


class OverlayWidget(QWidget):
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
        position: str = "",
        on_moved: Callable[[int, int], None] | None = None,
    ) -> None:
        super().__init__(
            None,
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self._clock = clock or time.monotonic
        self._metrics = ResourceMetrics()
        self._frame: FrameSample | None = None
        self._frame_at = 0.0
        self._frames: deque[FrameSample] = deque(maxlen=_FRAME_HISTORY)
        self._source = ""
        self._source_available = False
        self._on_moved = on_moved
        self.setObjectName("overlayWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setMouseTracking(False)
        self.setWindowTitle("PCOptimizer PRO")
        self.setFixedSize(*self._size())
        self._handle = OverlayHandle(self, on_moved=on_moved)
        self._position = ""
        self.restore_position(position)

    def _size(self) -> tuple[int, int]:
        from app.ui import theme

        return theme.ls(300), theme.ls(156)

    def _handle_height(self) -> int:
        from app.ui import theme

        return theme.ls(24)

    def restore_position(self, value: str) -> None:
        text = str(value or "").strip()
        if text:
            try:
                x, y = (int(part) for part in text.split(",", 1))
            except ValueError:
                self.place()
                return
            self.move_to(x, y)
            return
        self.place()

    def place(self) -> None:
        from app.ui import theme

        screen = QGuiApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        area = screen.availableGeometry()
        gap = theme.ls(22)
        self.move_to(area.right() - self.width() - gap, area.top() + gap)

    def move_to(self, x: int, y: int) -> None:
        screen = QGuiApplication.screenAt(QPoint(x, y)) or QApplication.primaryScreen()
        area = screen.availableGeometry() if screen is not None else self.geometry()
        x = max(area.left(), min(x, area.right() - self.width()))
        y = max(area.top(), min(y, area.bottom() - self.height()))
        super().move(x, y)
        if isValid(self._handle):
            self._handle.move(self.pos())
        self._position = f"{x},{y}"

    def _commit_position(self) -> None:
        if self._on_moved is not None:
            self._on_moved(self.x(), self.y())

    def show_overlay(self) -> None:
        self.refresh_layout()
        self.show()
        self._handle.show()
        self.raise_()
        self.keep_topmost()

    def hide(self) -> None:
        if isValid(self._handle):
            self._handle.hide()
        super().hide()

    def closeEvent(self, event) -> None:
        if isValid(self._handle):
            self._handle.close()
            self._handle.deleteLater()
        super().closeEvent(event)

    def refresh_layout(self) -> None:
        self.setFixedSize(*self._size())
        if self._position:
            self.restore_position(self._position)
        else:
            self.place()
        self._handle.align()
        self.keep_topmost()

    def keep_topmost(self) -> None:
        if self.isVisible() and isValid(self):
            _force_topmost(self)
        if self._handle.isVisible() and isValid(self._handle):
            _force_topmost(self._handle)

    def set_source(self, name: str, available: bool) -> None:
        self._source = str(name)
        self._source_available = bool(available)

    def update_metrics(self, metrics: ResourceMetrics) -> None:
        self._metrics = metrics

    def update_frame(self, frame: FrameSample) -> None:
        self._frame = frame
        self._frame_at = self._clock()
        self._frames.append(frame)

    def _current_frame(self) -> FrameSample | None:
        if self._frame is None:
            return None
        if self._clock() - self._frame_at > _FRESH_SECONDS:
            return None
        return self._frame

    @staticmethod
    def _pct(value: float | None) -> str:
        return "—" if value is None else f"{value:.0f}%"

    @staticmethod
    def _temp(value: float | None) -> str:
        return "—" if value is None else f"{value:.0f}°C"

    def _font(self, size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
        from app.ui import theme

        families = getattr(theme, "MONO_FONT_FAMILIES", ["Geist Mono", "Consolas", "monospace"])
        font = QFont(families[0] if families else "monospace")
        font.setPixelSize(theme.fs(size))
        font.setWeight(weight)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 106.0)
        return font

    def paintEvent(self, event) -> None:
        from app.ui import theme

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        path = QPainterPath()
        path.addRoundedRect(rect, theme.RADIUS_MD, theme.RADIUS_MD)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        top = QColor(theme.PANEL)
        top.setAlpha(238)
        bottom = QColor(theme.BG)
        bottom.setAlpha(246)
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(1.0, bottom)
        painter.fillPath(path, gradient)
        border = QColor(theme.BORDER_HI)
        border.setAlpha(210)
        painter.setPen(border)
        painter.drawPath(path)
        accent = QColor(theme.ACCENT)
        accent.setAlpha(230)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(
            QRectF(rect.left() + theme.ls(10), rect.top() + 3, rect.width() - theme.ls(20), 1),
            accent,
        )

        m = theme.ls(14)
        handle_h = self._handle_height()
        dot_y = rect.top() + theme.ls(12)
        painter.setBrush(QColor(theme.BORDER_HI))
        for index in range(3):
            painter.drawEllipse(QRectF(m + index * theme.ls(6), dot_y, 3, 3))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setFont(self._font(8, QFont.Weight.Medium))
        painter.setPen(QColor(theme.TEXT_DIM))
        painter.drawText(
            QRectF(m + theme.ls(22), rect.top() + theme.ls(4), theme.ls(54), handle_h - theme.ls(8)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tr("overlay_drag_hint"),
        )
        painter.drawText(
            QRectF(m, rect.top() + theme.ls(4), theme.ls(54), handle_h - theme.ls(8)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            tr("overlay_live"),
        )
        source = self._source if self._source_available else tr("overlay_no_source")
        source_text = painter.fontMetrics().elidedText(source, Qt.TextElideMode.ElideRight, theme.ls(130))
        painter.drawText(
            QRectF(rect.right() - m - theme.ls(130), rect.top() + theme.ls(4), theme.ls(130), handle_h - theme.ls(8)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            source_text,
        )

        frame = self._current_frame()
        stats = frame_stats(list(self._frames))
        metrics = self._metrics
        fps_top = rect.top() + handle_h + theme.ls(2)
        fps = f"{frame.fps:.0f}" if frame is not None else "—"
        painter.setFont(self._font(30, QFont.Weight.DemiBold))
        painter.setPen(QColor(theme.ACCENT if frame is not None else theme.TEXT_DIM))
        painter.drawText(
            QRectF(m, fps_top, theme.ls(112), theme.ls(42)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fps,
        )
        painter.setFont(self._font(9, QFont.Weight.Medium))
        painter.setPen(QColor(theme.TEXT_DIM))
        painter.drawText(
            QRectF(m + theme.ls(2), fps_top + theme.ls(35), theme.ls(90), theme.ls(16)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            tr("overlay_fps"),
        )
        right_edge = rect.right() - m
        low = f"{stats.low_1:.0f}" if stats.low_1 is not None else "—"
        painter.drawText(
            QRectF(m + theme.ls(132), fps_top + theme.ls(2), right_edge - m - theme.ls(132), theme.ls(22)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{tr('overlay_low')} {low}",
        )
        frame_ms = (
            f"{tr('overlay_frame')} {frame.frametime_ms:.1f} {tr('overlay_min_ago')}"
            if frame is not None
            else tr("overlay_no_source")
        )
        painter.drawText(
            QRectF(m + theme.ls(132), fps_top + theme.ls(26), right_edge - m - theme.ls(132), theme.ls(18)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            frame_ms,
        )

        separator_y = fps_top + theme.ls(52)
        separator = QColor(theme.BORDER)
        separator.setAlpha(150)
        painter.setPen(separator)
        painter.drawLine(int(m), int(separator_y), int(right_edge), int(separator_y))

        metric_top = separator_y + theme.ls(6)
        column_width = (right_edge - m) / 3
        pairs = (
            (tr("overlay_cpu"), self._pct(metrics.cpu_percent)),
            (tr("overlay_ram"), self._pct(metrics.ram_percent)),
            (tr("overlay_gpu"), self._pct(metrics.gpu_percent)),
        )
        for index, (label, value) in enumerate(pairs):
            left = m + index * column_width
            painter.setFont(self._font(8, QFont.Weight.Medium))
            painter.setPen(QColor(theme.TEXT_DIM))
            painter.drawText(
                QRectF(left, metric_top, column_width, theme.ls(14)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                label,
            )
            painter.setFont(self._font(13, QFont.Weight.DemiBold))
            painter.setPen(QColor(theme.TEXT))
            painter.drawText(
                QRectF(left, metric_top + theme.ls(14), column_width, theme.ls(20)),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                value,
            )
            if index < 2:
                painter.setPen(separator)
                painter.drawLine(
                    int(left + column_width),
                    int(metric_top + 2),
                    int(left + column_width),
                    int(metric_top + theme.ls(32)),
                )

        temp_color = theme.TEXT_DIM
        if metrics.system_temp is not None and metrics.system_temp >= 85:
            temp_color = theme.DANGER
        elif metrics.gpu_temp is not None and metrics.gpu_temp >= 80:
            temp_color = theme.WARN
        painter.setFont(self._font(10, QFont.Weight.Medium))
        painter.setPen(QColor(temp_color))
        painter.drawText(
            QRectF(m, rect.bottom() - theme.ls(24), right_edge - m, theme.ls(18)),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            f"{tr('overlay_sys')} {self._temp(metrics.system_temp)}   "
            f"{tr('overlay_gpu')} {self._temp(metrics.gpu_temp)}",
        )


class OverlayService(QObject):
    state_changed = Signal(bool)

    def __init__(
        self,
        settings,
        *,
        parent: QObject | None = None,
        widget: OverlayWidget | None = None,
        hotkey: OverlayHotkey | None = None,
        provider=None,
        poll_interval_ms: int = 250,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        if widget is None:
            widget = OverlayWidget(
                position=str(settings.get("overlay_position") or ""),
                on_moved=self._on_overlay_moved,
            )
        self.widget = widget
        self.hotkey = hotkey or OverlayHotkey(self)
        self._provider_injected = provider is not None
        self.provider = provider if provider is not None else self._make_provider()
        self._enabled = False
        self._closed = False
        self._poll_timer = QTimer(self)
        self._poll_timer.setInterval(max(50, poll_interval_ms))
        self._poll_timer.timeout.connect(self.poll_frame)
        self.hotkey.triggered.connect(self.toggle)
        self.hotkey.register()
        self.refresh_source()
        self.set_enabled(bool(self._settings.get("overlay_enabled")))

    @staticmethod
    def _make_provider():
        from app.gaming import default_frame_provider

        return default_frame_provider()

    @property
    def enabled(self) -> bool:
        return self._enabled

    def _on_overlay_moved(self, x: int, y: int) -> None:
        self._settings.set("overlay_position", f"{x},{y}")
        self._settings.save()

    def refresh_source(self) -> None:
        from app.gaming import default_frame_provider

        if not self._provider_injected:
            path = str(self._settings.get("presentmon_csv_path") or "")
            self.provider = default_frame_provider(path)
        self.widget.set_source(self.provider.source_name(), self.provider.available)

    def set_enabled(self, enabled: bool, *, persist: bool = False) -> None:
        enabled = bool(enabled)
        if persist:
            self._settings.set("overlay_enabled", enabled)
            self._settings.save()
        changed = enabled != self._enabled
        self._enabled = enabled
        if enabled:
            self.widget.show_overlay()
            self._poll_timer.start()
        else:
            self._poll_timer.stop()
            self.widget.hide()
        if changed or persist:
            self.state_changed.emit(enabled)

    def toggle(self, *, persist: bool = True) -> None:
        self.set_enabled(not self._enabled, persist=persist)

    def apply_snapshot(self, snapshot) -> None:
        from app.gaming import resource_metrics

        self.widget.update_metrics(resource_metrics(snapshot))

    def poll_frame(self) -> None:
        if not self._enabled:
            return
        self.widget.keep_topmost()
        frame = self.provider.latest_frame()
        if frame is not None:
            self.widget.update_frame(frame)

    def retranslate(self) -> None:
        self._poll_timer.stop()
        self.widget.refresh_layout()
        if self._enabled:
            self.widget.show_overlay()
            self._poll_timer.start()
        self.widget.update()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._poll_timer.stop()
        self.hotkey.unregister()
        if isValid(self.widget):
            self.widget.close()
            self.widget.deleteLater()
