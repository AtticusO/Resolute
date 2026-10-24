"""A leather pen cup holding pencils and pens. Clicking it opens a terminal."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient

from . import desk, textures

CX = 1290.0
BASE_Y = 478.0
W = 74.0  # cup diameter
H = 88.0
RY = 9.0  # half-height of the rim ellipse (we look slightly down into it)
TOP_Y = BASE_Y - H

# (angle from vertical in degrees, length above the rim, kind, x offset at the rim)
PENS = [
    (-17, 112, "pencil", -20),
    (-6, 128, "fountain", -8),
    (9, 104, "pencil", 6),
    (-12, 96, "ballpoint", 14),
    (19, 118, "pencil", 20),
    (3, 86, "marker", -2),
]


def bounds():
    return QRectF(CX - 90, TOP_Y - 140, 180, H + 160)


def contains(pt):
    return QRectF(CX - W / 2 - 4, TOP_Y - 120, W + 8, H + 126).contains(pt)


def paint_shadow(p):
    """Contact shadow on the desk; drawn in the static layer."""
    g = QRadialGradient(QPointF(CX + 8, BASE_Y + 2), W * 0.9)
    g.setColorAt(0, QColor(0, 0, 0, 170))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.translate(0, (BASE_Y + 2) * (1 - 0.25))
    p.scale(1, 0.25)
    p.setBrush(g)
    p.drawEllipse(QPointF(CX + 8, BASE_Y + 2), W, W)
    p.restore()


def paint(p: QPainter, lift=0.0):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    rim = QRectF(CX - W / 2, TOP_Y - RY, W, 2 * RY)
    # inside of the cup, seen over the front rim
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(20, 8, 4))
    p.drawEllipse(rim)
    # pens, back to front; they rise a little on hover
    for angle, length, kind, dx in PENS:
        _pen(p, QPointF(CX + dx, TOP_Y + 4 - lift * (6 + length * 0.05)), angle, length, kind)
    # cup body: oxblood leather with gilt tooling
    body = QPainterPath()
    body.moveTo(CX - W / 2, TOP_Y)
    body.lineTo(CX - W / 2, BASE_Y)
    body.arcTo(QRectF(CX - W / 2, BASE_Y - RY, W, 2 * RY), 180, 180)
    body.lineTo(CX + W / 2, TOP_Y)
    body.arcTo(rim, 0, -180)
    body.closeSubpath()
    p.setBrush(desk._tex(textures.leather(), 33, 9))
    p.drawPath(body)
    round_ = QLinearGradient(CX - W / 2, 0, CX + W / 2, 0)
    round_.setColorAt(0, QColor(0, 0, 0, 150))
    round_.setColorAt(0.3, QColor(255, 220, 180, 40))
    round_.setColorAt(0.55, QColor(0, 0, 0, 0))
    round_.setColorAt(1, QColor(0, 0, 0, 170))
    p.setBrush(round_)
    p.drawPath(body)
    gold = QColor(206, 164, 84, 210)
    for y in (TOP_Y + 10, BASE_Y - 12):
        band = QPainterPath()
        band.arcMoveTo(QRectF(CX - W / 2, y - RY, W, 2 * RY), 180)
        band.arcTo(QRectF(CX - W / 2, y - RY, W, 2 * RY), 180, 180)
        p.setPen(QPen(gold, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(band)
    # brass rim
    p.setPen(QPen(QColor(220, 180, 100), 2.4))
    p.drawArc(rim, 180 * 16, 180 * 16)
    p.setPen(QPen(QColor(120, 86, 34), 1.4))
    p.drawArc(rim, 0, 180 * 16)
    p.restore()


def _pen(p, base, angle, length, kind):
    p.save()
    p.translate(base)
    p.rotate(angle)
    p.setPen(Qt.PenStyle.NoPen)
    if kind == "pencil":
        w = 7
        body = QRectF(-w / 2, -length, w, length)
        g = QLinearGradient(-w / 2, 0, w / 2, 0)
        g.setColorAt(0, QColor(170, 120, 10))
        g.setColorAt(0.45, QColor(250, 200, 40))
        g.setColorAt(1, QColor(150, 100, 0))
        p.setBrush(g)
        p.drawRect(body)
        p.setBrush(QColor(170, 170, 176))  # ferrule
        p.drawRect(QRectF(-w / 2, -length - 6, w, 6))
        p.setBrush(QColor(232, 140, 140))  # eraser
        p.drawRoundedRect(QRectF(-w / 2, -length - 13, w, 8), 2, 2)
    elif kind == "fountain":
        w = 9
        g = QLinearGradient(-w / 2, 0, w / 2, 0)
        g.setColorAt(0, QColor(10, 10, 14))
        g.setColorAt(0.4, QColor(70, 70, 80))
        g.setColorAt(1, QColor(6, 6, 8))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(-w / 2, -length, w, length), 4, 4)
        p.setBrush(desk.BRASS)
        p.drawRect(QRectF(-w / 2, -length + 18, w, 3))
        p.drawRect(QRectF(w / 2 - 2, -length + 4, 2.4, 30))  # clip
    elif kind == "ballpoint":
        w = 6
        g = QLinearGradient(-w / 2, 0, w / 2, 0)
        g.setColorAt(0, QColor(20, 40, 110))
        g.setColorAt(0.45, QColor(70, 110, 200))
        g.setColorAt(1, QColor(16, 30, 90))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(-w / 2, -length, w, length), 3, 3)
        p.setBrush(QColor(200, 200, 206))
        p.drawRect(QRectF(-w / 2, -length + 2, w, 5))
    else:  # marker
        w = 11
        g = QLinearGradient(-w / 2, 0, w / 2, 0)
        g.setColorAt(0, QColor(110, 16, 12))
        g.setColorAt(0.45, QColor(200, 46, 36))
        g.setColorAt(1, QColor(90, 12, 10))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(-w / 2, -length, w, length), 4, 4)
        p.setBrush(QColor(30, 30, 30))
        p.drawRoundedRect(QRectF(-w / 2 - 0.5, -length - 4, w + 1, 22), 4, 4)
    p.restore()
