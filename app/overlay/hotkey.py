from __future__ import annotations

import ctypes

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject, Signal
from PySide6.QtWidgets import QApplication

_MOD_ALT = 0x0001
_MOD_CONTROL = 0x0002
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_VK_F9 = 0x78
_HOTKEY_ID = 0x4F50


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_ulong),
        ("pt", _POINT),
    ]


class OverlayHotkey(QObject, QAbstractNativeEventFilter):
    triggered = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        windll = getattr(ctypes, "windll", None)
        self._user32 = getattr(windll, "user32", None) if windll is not None else None
        self._registered = False

    @property
    def registered(self) -> bool:
        return self._registered

    def register(self) -> bool:
        if self._registered or self._user32 is None:
            return False
        modifiers = _MOD_CONTROL | _MOD_ALT | _MOD_NOREPEAT
        try:
            ok = bool(self._user32.RegisterHotKey(None, _HOTKEY_ID, modifiers, _VK_F9))
        except OSError:
            return False
        if not ok:
            return False
        app = QApplication.instance()
        if app is not None:
            app.installNativeEventFilter(self)
        self._registered = True
        return True

    def unregister(self) -> bool:
        if not self._registered or self._user32 is None:
            return False
        app = QApplication.instance()
        if app is not None:
            app.removeNativeEventFilter(self)
        self._registered = False
        try:
            return bool(self._user32.UnregisterHotKey(None, _HOTKEY_ID))
        except OSError:
            return False

    def nativeEvent(self, eventType, message) -> tuple[bool, int]:
        if not self._registered:
            return False, 0
        name = bytes(eventType.data()) if isinstance(eventType, QByteArray) else str(eventType).encode()
        if b"windows" not in name.lower():
            return False, 0
        msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
        if msg.message == _WM_HOTKEY and int(msg.wParam) & 0xFFFF == _HOTKEY_ID:
            self.triggered.emit()
            return True, 0
        return False, 0
