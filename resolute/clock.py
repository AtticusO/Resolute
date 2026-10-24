"""A walnut mantel clock on the desk top, with a small battery gauge set into its face."""

import math
import time
from types import SimpleNamespace

import psutil
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QConicalGradient, QFont, QLinearGradient, QPainter, QPainterPath, QPen,
                         QRadialGradient, QTransform)

from . import desk, textures

CX = 1712.0
BASE_Y = 772.0
CASE_W = 250.0
DIAL_R = 60.0
DIAL = QPointF(CX, BASE_Y - 92)
SUB_R = 17.0
SUB = QPointF(CX, DIAL.y() + 27)  # battery sub-dial at six o'clock

NUMERALS = ["12", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11"]
FACE_INK = QColor(36, 28, 20)


def bounds():
    return QRectF(CX - CASE_W / 2 - 16, BASE_Y - 170, CASE_W + 40, 190)


def contains(pt):
    return _case_path().contains(pt) or QRectF(CX - CASE_W / 2 - 8, BASE_Y - 26, CASE_W + 16, 26).contains(pt)


def part_at(pt):
    if math.hypot(pt.x() - SUB.x(), pt.y() - SUB.y()) <= SUB_R + 3:
        return "battery"
    return "time"


def battery():
    """(percent, plugged in) or None when the machine has no battery."""
    try:
        b = psutil.sensors_battery()
    except (AttributeError, OSError):
        return None
    if b is None:
        return None
    return b.percent, bool(b.power_plugged)


def _case_path():
    """Napoleon-hat profile: low shoulders rising in curves to a tall centre."""
    l, r = CX - CASE_W / 2, CX + CASE_W / 2
    top = BASE_Y - 168
    shoulder = BASE_Y - 74
    path = QPainterPath()
    path.moveTo(l, BASE_Y - 20)
    path.lineTo(l, shoulder)
    path.cubicTo(l + 10, shoulder - 24, CX - 70, shoulder - 30, CX - 64, top + 40)
    path.cubicTo(CX - 52, top + 6, CX + 52, top + 6, CX + 64, top + 40)
    path.cubicTo(CX + 70, shoulder - 30, r - 10, shoulder - 24, r, shoulder)
    path.lineTo(r, BASE_Y - 20)
    path.closeSubpath()
    return path


def paint_static(p: QPainter):
    """Case, dial and numerals; drawn into the static layer."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # contact shadow on the desk
    sh = QRadialGradient(QPointF(CX + 14, BASE_Y + 2), CASE_W * 0.7)
    sh.setColorAt(0, QColor(0, 0, 0, 180))
    sh.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.translate(0, (BASE_Y + 2) * (1 - 0.2))
    p.scale(1, 0.2)
    p.setBrush(sh)
    p.drawEllipse(QPointF(CX + 14, BASE_Y + 2), CASE_W * 0.72, CASE_W * 0.72)
    p.restore()

    # stepped plinth with brass bun feet
    p.setPen(Qt.PenStyle.NoPen)
    for x in (CX - CASE_W / 2 + 14, CX + CASE_W / 2 - 14):
        g = QRadialGradient(QPointF(x - 3, BASE_Y - 2), 10)
        g.setColorAt(0, desk.BRASS_LIGHT)
        g.setColorAt(1, desk.BRASS_DARK)
        p.setBrush(g)
        p.drawEllipse(QPointF(x, BASE_Y - 2), 11, 6)
    plinth = QRectF(CX - CASE_W / 2 - 8, BASE_Y - 26, CASE_W + 16, 20)
    desk.bevel(p, plinth, desk._tex(textures.stand_wood(), 21, 5), depth=3, radius=3)
    p.setBrush(QColor(22, 7, 2, 180))
    p.drawRoundedRect(plinth, 3, 3)
    # case body: a darker, richer walnut than the desk so it stands apart, with visible depth on the right
    case = _case_path()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(20, 8, 3))
    p.drawPath(case.translated(7, -3))  # side of the case, seen past its front
    p.setBrush(desk._tex(textures.stand_wood(), 160, 60))
    p.drawPath(case)
    p.setBrush(QColor(22, 7, 2, 195))  # deep, almost black walnut stain
    p.drawPath(case)
    shade = QLinearGradient(CX - CASE_W / 2, 0, CX + CASE_W / 2, 0)
    shade.setColorAt(0, QColor(0, 0, 0, 140))
    shade.setColorAt(0.3, QColor(255, 220, 170, 30))
    shade.setColorAt(0.6, QColor(0, 0, 0, 0))
    shade.setColorAt(1, QColor(0, 0, 0, 160))
    p.setBrush(shade)
    p.drawPath(case)
    top_light = QLinearGradient(0, BASE_Y - 168, 0, BASE_Y - 60)
    top_light.setColorAt(0, QColor(255, 214, 160, 50))
    top_light.setColorAt(1, QColor(255, 214, 160, 0))
    p.setBrush(top_light)
    p.drawPath(case)
    # carved moulding just inside the edge, and a crisp outline
    inner = QPainterPath(case)
    t = QTransform()
    t.translate(CX, BASE_Y - 20)
    t.scale(0.93, 0.9)
    t.translate(-CX, -(BASE_Y - 20))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0, 120), 2))
    p.drawPath(t.map(inner))
    p.setPen(QPen(QColor(255, 210, 160, 60), 1))
    p.drawPath(t.map(inner).translated(0, 1.5))
    p.setPen(QPen(QColor(10, 4, 1), 1.6))
    p.drawPath(case)
    p.setPen(QPen(QColor(255, 220, 170, 90), 1.2))
    p.drawPath(case.translated(0, 1))
    # inlaid string line following the curve
    inlay = QPainterPath()
    inlay.moveTo(CX - CASE_W / 2 + 12, BASE_Y - 32)
    inlay.lineTo(CX + CASE_W / 2 - 12, BASE_Y - 32)
    p.setPen(QPen(QColor(220, 180, 110, 130), 1.4))
    p.drawPath(inlay)

    # brass bezel and cream dial
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 110))
    p.drawEllipse(DIAL + QPointF(2, 4), DIAL_R + 9, DIAL_R + 9)
    ring = QConicalGradient(DIAL, 135)
    for stop, c in ((0, desk.BRASS_LIGHT), (0.25, desk.BRASS_DARK), (0.5, desk.BRASS_LIGHT),
                    (0.75, desk.BRASS_DARK), (1, desk.BRASS_LIGHT)):
        ring.setColorAt(stop, c)
    p.setBrush(ring)
    p.drawEllipse(DIAL, DIAL_R + 8, DIAL_R + 8)
    face = QRadialGradient(DIAL - QPointF(0, DIAL_R * 0.3), DIAL_R * 1.3)
    face.setColorAt(0, QColor(246, 238, 214))
    face.setColorAt(1, QColor(214, 198, 160))
    p.setBrush(face)
    p.drawEllipse(DIAL, DIAL_R, DIAL_R)
    # minute track and numerals
    for i in range(60):
        a = math.radians(90 - i * 6)
        outer = DIAL + QPointF(math.cos(a), -math.sin(a)) * (DIAL_R - 3)
        inner = DIAL + QPointF(math.cos(a), -math.sin(a)) * (DIAL_R - (8 if i % 5 == 0 else 5))
        p.setPen(QPen(FACE_INK, 1.6 if i % 5 == 0 else 0.7))
        p.drawLine(inner, outer)
    font = QFont("C059")
    font.setPixelSize(14)
    font.setBold(True)
    p.setFont(font)
    p.setPen(FACE_INK)
    for i, numeral in enumerate(NUMERALS):
        if i == 6:
            continue  # the battery sub-dial sits where 6 would be
        a = math.radians(90 - i * 30)
        c = DIAL + QPointF(math.cos(a), -math.sin(a)) * (DIAL_R - 18)
        p.drawText(QRectF(c.x() - 14, c.y() - 8, 28, 16), Qt.AlignmentFlag.AlignCenter, numeral)
    # battery sub-dial: a tiny bronze-rimmed gauge like the ones on the stand
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 60))
    p.drawEllipse(SUB + QPointF(0.6, 1), SUB_R + 2.5, SUB_R + 2.5)
    p.setBrush(desk.BRONZE)
    p.drawEllipse(SUB, SUB_R + 2, SUB_R + 2)
    p.setBrush(QColor(240, 230, 202))
    p.drawEllipse(SUB, SUB_R, SUB_R)
    for k in range(6):  # 0, 20 ... 100 per cent across 180 degrees
        a = math.radians(180 - k * 36)
        o = SUB + QPointF(math.cos(a), -math.sin(a)) * (SUB_R - 1.5)
        i = SUB + QPointF(math.cos(a), -math.sin(a)) * (SUB_R - 5)
        p.setPen(QPen(FACE_INK, 1))
        p.drawLine(i, o)
    p.setPen(QPen(QColor(180, 40, 30), 2.2, cap=Qt.PenCapStyle.FlatCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    arc = QRectF(SUB.x() - SUB_R + 3, SUB.y() - SUB_R + 3, 2 * SUB_R - 6, 2 * SUB_R - 6)
    p.drawArc(arc, int((180 - 36) * 16), int(36 * 16))  # red zone below 20 %
    font = QFont("DejaVu Sans")
    font.setPixelSize(6)
    font.setBold(True)
    p.setFont(font)
    p.setPen(FACE_INK)
    p.drawText(QRectF(SUB.x() - 12, SUB.y() + 2, 24, 8), Qt.AlignmentFlag.AlignCenter, "BATT")
    p.drawText(QRectF(SUB.x() - SUB_R + 1, SUB.y() - 3, 6, 7), Qt.AlignmentFlag.AlignCenter, "E")
    p.drawText(QRectF(SUB.x() + SUB_R - 7, SUB.y() - 3, 6, 7), Qt.AlignmentFlag.AlignCenter, "F")
    p.restore()


class Clock:
    def __init__(self):
        self.battery = battery()
        self.tags = {"time": SimpleNamespace(cx=DIAL.x(), cy=DIAL.y() - DIAL_R + 6, r=12, detail=""),
                     "battery": SimpleNamespace(cx=SUB.x(), cy=SUB.y(), r=SUB_R + 4, detail="")}
        self.update_tags()

    def poll(self):
        self.battery = battery()
        self.update_tags()

    def update_tags(self):
        self.tags["time"].detail = time.strftime("%A %-d %B %Y, %H:%M")
        b = self.battery
        if b is None:
            self.tags["battery"].detail = "No battery: running on mains power"
        else:
            pct, plugged = b
            state = "charging" if plugged and pct < 99.5 else ("plugged in" if plugged else "on battery")
            self.tags["battery"].detail = f"Battery {pct:.0f}%, {state}"

    def damage_rect(self):
        return QRectF(DIAL.x() - DIAL_R - 2, DIAL.y() - DIAL_R - 2, 2 * DIAL_R + 4, 2 * DIAL_R + 4)

    def paint(self, p: QPainter):
        now = time.localtime()
        frac = time.time() % 1
        sec = now.tm_sec + frac
        minute = now.tm_min + sec / 60
        hour = (now.tm_hour % 12) + minute / 60
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # battery needle (sweeps 180 degrees across the top of the sub-dial)
        b = self.battery
        pct = b[0] if b else 100.0
        a = math.radians(180 - 180 * pct / 100)
        tip = SUB + QPointF(math.cos(a), -math.sin(a)) * (SUB_R - 3)
        p.setPen(QPen(QColor(30, 24, 18), 1.4, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(SUB, tip)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(30, 24, 18))
        p.drawEllipse(SUB, 1.8, 1.8)
        if b and b[1]:  # small lit pip when on mains power
            p.setBrush(QColor(120, 220, 110))
            p.drawEllipse(SUB + QPointF(SUB_R - 6, 5), 1.8, 1.8)
        elif b and b[0] < 20:
            p.setBrush(QColor(240, 60, 40))
            p.drawEllipse(SUB + QPointF(SUB_R - 6, 5), 1.8, 1.8)
        # hands: spade hour and minute hands, thin red seconds
        self._hand(p, hour * 30, DIAL_R * 0.52, 4.2, spade=True)
        self._hand(p, minute * 6, DIAL_R * 0.78, 2.6, spade=True)
        self._hand(p, sec * 6, DIAL_R * 0.86, 1.0, color=QColor(180, 30, 20), tail=12)
        g = QRadialGradient(DIAL - QPointF(1.5, 1.5), 5)
        g.setColorAt(0, desk.BRASS_LIGHT)
        g.setColorAt(1, desk.BRASS_DARK)
        p.setBrush(g)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(DIAL, 4, 4)
        # domed glass
        glass = QLinearGradient(DIAL - QPointF(DIAL_R, DIAL_R), DIAL + QPointF(DIAL_R * 0.3, DIAL_R * 0.3))
        glass.setColorAt(0, QColor(255, 255, 255, 60))
        glass.setColorAt(0.5, QColor(255, 255, 255, 0))
        clip = QPainterPath()
        clip.addEllipse(DIAL, DIAL_R, DIAL_R)
        sheen = QPainterPath()
        sheen.addEllipse(DIAL - QPointF(DIAL_R * 0.35, DIAL_R * 0.45), DIAL_R * 0.95, DIAL_R * 0.6)
        p.setBrush(glass)
        p.drawPath(clip.intersected(sheen))
        p.restore()

    @staticmethod
    def _hand(p, degrees, length, width, color=FACE_INK, spade=False, tail=8):
        p.save()
        p.translate(DIAL)
        p.rotate(degrees)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 60))
        shape = QPainterPath()
        shape.moveTo(-width / 2, tail)
        shape.lineTo(-width / 2, -length * 0.72)
        if spade:
            shape.cubicTo(-width * 2.2, -length * 0.8, -width * 0.6, -length * 0.92, 0, -length)
            shape.cubicTo(width * 0.6, -length * 0.92, width * 2.2, -length * 0.8, width / 2, -length * 0.72)
        else:
            shape.lineTo(0, -length)
            shape.lineTo(width / 2, -length * 0.72)
        shape.lineTo(width / 2, tail)
        shape.closeSubpath()
        p.drawPath(shape.translated(1.5, 2))
        p.setBrush(color)
        p.drawPath(shape)
        p.restore()
