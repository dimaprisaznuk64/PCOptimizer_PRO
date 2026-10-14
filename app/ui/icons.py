from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from .theme import BRAND_A, BRAND_B, TEXT_DIM

_SIZE = 20


def _stroke(painter: QPainter, color: str, width: float = 1.6) -> None:
    pen = QPen(QColor(color), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)


def _dashboard(p: QPainter) -> None:
    for x, y in ((3, 3), (11, 3), (3, 11), (11, 11)):
        p.drawRoundedRect(QRectF(x, y, 6, 6), 1.5, 1.5)


def _monitor(p: QPainter) -> None:
    path = QPainterPath(QPointF(2, 11))
    for x, y in ((6, 11), (8, 5), (11, 16), (13.5, 8), (15, 11), (18, 11)):
        path.lineTo(x, y)
    p.drawPath(path)


def _gpu(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(2.5, 5, 15, 9), 2, 2)
    p.drawEllipse(QPointF(10, 9.5), 2.6, 2.6)
    p.drawLine(QPointF(5, 17), QPointF(15, 17))


def _processes(p: QPainter) -> None:
    for y in (5, 10, 15):
        p.drawLine(QPointF(7, y), QPointF(17, y))
        p.drawPoint(QPointF(3.5, y))


def _cleaner(p: QPainter) -> None:
    p.drawLine(QPointF(3.5, 5.5), QPointF(16.5, 5.5))
    p.drawLine(QPointF(8, 5.5), QPointF(8, 3.5))
    p.drawLine(QPointF(12, 5.5), QPointF(12, 3.5))
    path = QPainterPath(QPointF(5, 5.5))
    path.lineTo(6, 16.5)
    path.lineTo(14, 16.5)
    path.lineTo(15, 5.5)
    p.drawPath(path)


def _startup(p: QPainter) -> None:
    p.drawArc(QRectF(3.5, 4.5, 13, 13), 120 * 16, -300 * 16)
    p.drawLine(QPointF(10, 2.5), QPointF(10, 9))


def _optimizer(p: QPainter) -> None:
    for y, x in ((5, 7), (10, 13), (15, 8)):
        p.drawLine(QPointF(3, y), QPointF(17, y))
        p.drawEllipse(QPointF(x, y), 2, 2)


def _gaming(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(2, 6, 16, 9), 4, 4)
    p.drawLine(QPointF(6, 8.5), QPointF(6, 12.5))
    p.drawLine(QPointF(4, 10.5), QPointF(8, 10.5))
    p.drawPoint(QPointF(13, 9.5))
    p.drawPoint(QPointF(15, 11.5))


def _network(p: QPainter) -> None:
    p.drawArc(QRectF(2.5, 6, 15, 15), 45 * 16, 90 * 16)
    p.drawArc(QRectF(5.5, 9.5, 9, 9), 45 * 16, 90 * 16)
    p.drawPoint(QPointF(10, 15.5))


def _disk(p: QPainter) -> None:
    p.drawEllipse(QRectF(3, 3, 14, 14))
    p.drawEllipse(QPointF(10, 10), 2.2, 2.2)


def _health(p: QPainter) -> None:
    path = QPainterPath(QPointF(10, 17))
    path.cubicTo(2, 11.5, 2.5, 4.5, 6.5, 4.5)
    path.cubicTo(8.5, 4.5, 9.5, 5.5, 10, 6.5)
    path.cubicTo(10.5, 5.5, 11.5, 4.5, 13.5, 4.5)
    path.cubicTo(17.5, 4.5, 18, 11.5, 10, 17)
    p.drawPath(path)


def _settings(p: QPainter) -> None:
    for y, x in ((6, 13), (14, 7)):
        p.drawLine(QPointF(3, y), QPointF(17, y))
        p.drawEllipse(QPointF(x, y), 2.2, 2.2)


def _bell(p: QPainter) -> None:
    path = QPainterPath(QPointF(10, 2.5))
    path.cubicTo(6.5, 2.5, 5, 5.5, 5, 9)
    path.lineTo(4.5, 13)
    path.lineTo(15.5, 13)
    path.lineTo(15, 9)
    path.cubicTo(15, 5.5, 13.5, 2.5, 10, 2.5)
    p.drawPath(path)
    p.drawLine(QPointF(8.5, 15.5), QPointF(11.5, 15.5))
    p.drawArc(QRectF(9, 14.5, 2, 2.5), 0, -180 * 16)


def _cpu(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(5, 5, 10, 10), 2, 2)
    p.drawRect(QRectF(8, 8, 4, 4))
    for v in (7.5, 12.5):
        p.drawLine(QPointF(v, 2.5), QPointF(v, 5))
        p.drawLine(QPointF(v, 15), QPointF(v, 17.5))
        p.drawLine(QPointF(2.5, v), QPointF(5, v))
        p.drawLine(QPointF(15, v), QPointF(17.5, v))


def _ram(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(2.5, 5.5, 15, 7), 1.5, 1.5)
    for x in (6, 10, 14):
        p.drawLine(QPointF(x, 8), QPointF(x, 10))
    for x in (5, 8, 11, 14):
        p.drawLine(QPointF(x, 12.5), QPointF(x, 15))



def _fan(p: QPainter) -> None:
    p.drawEllipse(QRectF(3, 3, 14, 14))
    p.drawEllipse(QPointF(10, 10), 2, 2)
    p.drawArc(QRectF(7, 3.5, 6, 6), 30 * 16, 120 * 16)
    p.drawArc(QRectF(4, 9, 6, 6), 150 * 16, 120 * 16)
    p.drawArc(QRectF(10, 9, 6, 6), 270 * 16, 120 * 16)


def _thermometer(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(8.5, 2.5, 3, 9), 1.5, 1.5)
    p.drawEllipse(QRectF(7, 10, 6, 6))
    p.drawLine(QPointF(10, 6), QPointF(10, 13))


def _check(p: QPainter) -> None:
    path = QPainterPath(QPointF(4, 10.5))
    path.lineTo(8, 14.5)
    path.lineTo(16, 5.5)
    p.drawPath(path)


def _warning(p: QPainter) -> None:
    path = QPainterPath(QPointF(10, 2.5))
    path.lineTo(17.5, 16.5)
    path.lineTo(2.5, 16.5)
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(10, 7), QPointF(10, 11.5))
    p.drawPoint(QPointF(10, 14))


def _info(p: QPainter) -> None:
    p.drawEllipse(QRectF(3, 3, 14, 14))
    p.drawLine(QPointF(10, 8.5), QPointF(10, 13.5))
    p.drawPoint(QPointF(10, 6))


def _bolt(p: QPainter) -> None:
    path = QPainterPath(QPointF(11, 2.5))
    path.lineTo(5.5, 10.5)
    path.lineTo(10, 10.5)
    path.lineTo(8.5, 17.5)
    path.lineTo(14.5, 9.5)
    path.lineTo(10, 9.5)
    path.closeSubpath()
    p.drawPath(path)


def _shield(p: QPainter) -> None:
    path = QPainterPath(QPointF(10, 2.5))
    path.lineTo(16.5, 5)
    path.quadTo(16.5, 12, 10, 17.5)
    path.quadTo(3.5, 12, 3.5, 5)
    path.closeSubpath()
    p.drawPath(path)


_DRAWERS = {
    "cpu": _cpu,
    "ram": _ram,
    "dashboard": _dashboard,
    "monitor": _monitor,
    "gpu": _gpu,
    "processes": _processes,
    "cleaner": _cleaner,
    "startup": _startup,
    "optimizer": _optimizer,
    "gaming": _gaming,
    "network": _network,
    "disk": _disk,
    "health": _health,
    "bell": _bell,
    "settings": _settings,
    "fan": _fan,
    "thermometer": _thermometer,
    "check": _check,
    "warning": _warning,
    "info": _info,
    "bolt": _bolt,
    "shield": _shield,
}


def _pixmap(key: str, color: str, scale: int = 2) -> QPixmap:
    pix = QPixmap(_SIZE * scale, _SIZE * scale)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.scale(scale, scale)
    _stroke(painter, color)
    drawer = _DRAWERS.get(key)
    if drawer is not None:
        drawer(painter)
    painter.end()
    return pix


def nav_icon(key: str) -> QIcon:
    icon = QIcon()
    icon.addPixmap(_pixmap(key, TEXT_DIM), QIcon.Mode.Normal, QIcon.State.Off)
    icon.addPixmap(_pixmap(key, "#FFFFFF"), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def glyph(key: str, color: str) -> QPixmap:
    return _pixmap(key, color)


def app_icon(color: str = "") -> QIcon:
    """Brand icon: gradient rounded square with "PC"; optional status dot (tray)."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen

    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(QColor(0, 0, 0, 0))
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        rect = QRectF(size * 0.04, size * 0.04, size * 0.92, size * 0.92)
        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.0, QColor(BRAND_A))
        grad.setColorAt(1.0, QColor(BRAND_B))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawRoundedRect(rect, size * 0.24, size * 0.24)
        font = QFont()
        font.setFamilies(["Segoe UI Variable Display", "Segoe UI", "Inter", "DejaVu Sans"])
        font.setWeight(QFont.Weight.ExtraBold)
        font.setPixelSize(max(8, int(size * 0.42)))
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "PC")
        if color:
            r = size * 0.17
            cx, cy = size * 0.80, size * 0.80
            p.setPen(QPen(QColor("#0B1020"), max(1.0, size * 0.04)))
            p.setBrush(QColor(color))
            p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        p.end()
        icon.addPixmap(pix)
    return icon
