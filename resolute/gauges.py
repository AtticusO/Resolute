"""Vintage dashboard gauges: bronze bezel, cream face, red needle (see dial_inspo*.jpeg)."""

import math

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QConicalGradient, QFont, QLinearGradient, QPainter,
                         QPainterPath, QPen, QRadialGradient)

START_ANGLE = 225.0  # degrees, measured counter-clockwise from 3 o'clock
SWEEP = 270.0

SERIF = "C059"
FACE_INK = QColor(40, 30, 22)
NEEDLE_RED = QColor(196, 30, 22)


def _polar(cx, cy, r, deg):
    a = math.radians(deg)
    return QPointF(cx + r * math.cos(a), cy - r * math.sin(a))


class Gauge:
    def __init__(self, center, radius, title, subtitle, lo, hi, major, minors, red_from, has_lamp=False):
        self.cx, self.cy = center
        self.r = radius
        self.title = title
        self.subtitle = subtitle
        self.lo, self.hi = lo, hi
        self.major = major
        self.minors = minors
        self.red_from = red_from
        self.value = lo  # what the needle shows (eased)
        self.target = lo
        self.readout = "--"
        self.detail = ""  # longer description shown on hover
        self.has_lamp = has_lamp
        self.lamp = False  # amber warning lamp, lit when there is no reading

    # -- animation ---------------------------------------------------------
    def set_target(self, value, readout, detail=""):
        self.target = self.lo if value is None else max(self.lo, min(self.hi, value))
        self.readout = readout
        self.detail = detail
        self.lamp = value is None

    def step(self):
        """Ease the needle towards its target. Returns True while still moving."""
        diff = self.target - self.value
        if abs(diff) < (self.hi - self.lo) * 0.001:
            self.value = self.target
            return False
        self.value += diff * 0.12
        return True

    def contains(self, pt):
        return math.hypot(pt.x() - self.cx, pt.y() - self.cy) <= self.r

    def _angle(self, value):
        f = (value - self.lo) / (self.hi - self.lo)
        return START_ANGLE - SWEEP * f

    # -- painting ----------------------------------------------------------
    def paint_static(self, p: QPainter):
        cx, cy, r = self.cx, self.cy, self.r
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # recess shadow cut into the wood
        shadow = QRadialGradient(QPointF(cx + 2, cy + 4), r * 1.12)
        shadow.setColorAt(0.85, QColor(0, 0, 0, 150))
        shadow.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shadow)
        p.drawEllipse(QPointF(cx + 2, cy + 4), r * 1.12, r * 1.12)

        # polished bronze bezel
        bronze = QConicalGradient(QPointF(cx, cy), 135)
        for stop, (cr, cg, cb) in ((0.0, (246, 196, 128)), (0.12, (122, 66, 26)), (0.25, (222, 160, 92)),
                                   (0.4, (86, 44, 16)), (0.55, (236, 180, 110)), (0.7, (110, 58, 22)),
                                   (0.85, (214, 150, 84)), (1.0, (246, 196, 128))):
            bronze.setColorAt(stop, QColor(cr, cg, cb))
        p.setBrush(bronze)
        p.setPen(QPen(QColor(50, 26, 8), 1.2))
        p.drawEllipse(QPointF(cx, cy), r, r)
        inner = QLinearGradient(cx, cy - r, cx, cy + r)
        inner.setColorAt(0, QColor(70, 36, 12))
        inner.setColorAt(1, QColor(228, 168, 100))
        p.setBrush(inner)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPointF(cx, cy), r * 0.88, r * 0.88)

        # cream face
        fr = r * 0.84
        face = QRadialGradient(QPointF(cx, cy - fr * 0.25), fr * 1.2)
        face.setColorAt(0, QColor(244, 234, 204))
        face.setColorAt(0.7, QColor(230, 216, 178))
        face.setColorAt(1, QColor(196, 178, 136))
        p.setBrush(face)
        p.drawEllipse(QPointF(cx, cy), fr, fr)

        # red zone band
        if self.red_from is not None:
            a0 = self._angle(self.red_from)
            a1 = self._angle(self.hi)
            band = QRectF(cx - fr * 0.86, cy - fr * 0.86, fr * 1.72, fr * 1.72)
            p.setPen(QPen(QColor(178, 40, 30, 210), fr * 0.07, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            p.drawArc(band, int(a1 * 16), int((a0 - a1) * 16))

        # ticks
        span = self.hi - self.lo
        n_major = int(round(span / self.major))
        for i in range(n_major + 1):
            v = self.lo + i * self.major
            a = self._angle(v)
            p.setPen(QPen(FACE_INK, max(1.0, r * 0.03), cap=Qt.PenCapStyle.FlatCap))
            p.drawLine(_polar(cx, cy, fr * 0.93, a), _polar(cx, cy, fr * 0.76, a))
            if i < n_major:
                for m in range(1, self.minors):
                    am = self._angle(v + self.major * m / self.minors)
                    p.setPen(QPen(FACE_INK, max(0.6, r * 0.014)))
                    p.drawLine(_polar(cx, cy, fr * 0.93, am), _polar(cx, cy, fr * 0.84, am))

        # numerals
        font = QFont(SERIF)
        font.setPixelSize(max(7, int(r * 0.17)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(FACE_INK)
        for i in range(n_major + 1):
            v = self.lo + i * self.major
            pt = _polar(cx, cy, fr * 0.62, self._angle(v))
            box = QRectF(pt.x() - r * 0.25, pt.y() - r * 0.12, r * 0.5, r * 0.24)
            p.drawText(box, Qt.AlignmentFlag.AlignCenter, f"{v:g}")

        # title / subtitle in the style of "MILES PER HOUR"
        font = QFont(SERIF)
        font.setPixelSize(max(7, int(r * 0.15)))
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 108)
        p.setFont(font)
        p.drawText(QRectF(cx - r * 0.6, cy - r * 0.33, r * 1.2, r * 0.18), Qt.AlignmentFlag.AlignCenter, self.title)
        if r >= 60:  # the unit line is unreadable on small dials
            font.setPixelSize(max(5, int(r * 0.09)))
            font.setBold(False)
            font.setItalic(True)
            p.setFont(font)
            p.drawText(QRectF(cx - r * 0.5, cy + r * 0.13, r, r * 0.13), Qt.AlignmentFlag.AlignCenter, self.subtitle)
        p.restore()

    def paint_dynamic(self, p: QPainter):
        cx, cy, r = self.cx, self.cy, self.r
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # odometer-style readout window
        w, h = r * 0.74, r * 0.24
        box = QRectF(cx - w / 2, cy + r * 0.44, w, h)
        p.setPen(QPen(QColor(150, 100, 50), 1))
        p.setBrush(QColor(18, 14, 10))
        p.drawRoundedRect(box, 2, 2)
        font = QFont("DejaVu Sans Mono")
        font.setPixelSize(max(6, int(h * 0.68)))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(240, 236, 222))
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, self.readout)

        if self.has_lamp:
            self._paint_lamp(p)
        self._paint_needle(p)
        p.restore()

    def _paint_lamp(self, p):
        cx, cy, r = self.cx, self.cy, self.r
        lamp_c = QPointF(cx + r * 0.3, cy)
        lg = QRadialGradient(lamp_c, r * 0.07)
        if self.lamp:
            lg.setColorAt(0, QColor(255, 220, 120))
            lg.setColorAt(1, QColor(220, 130, 20))
        else:
            lg.setColorAt(0, QColor(110, 80, 40))
            lg.setColorAt(1, QColor(60, 40, 20))
        p.setPen(QPen(QColor(60, 50, 40), 0.8))
        p.setBrush(lg)
        p.drawEllipse(lamp_c, r * 0.055, r * 0.055)

    def _paint_needle(self, p):
        cx, cy, r = self.cx, self.cy, self.r
        # needle with a soft drop shadow
        a = self._angle(self.value)
        needle = QPainterPath()
        tip = _polar(0, 0, r * 0.74, a)
        tail = _polar(0, 0, r * 0.18, a + 180)
        side1 = _polar(0, 0, r * 0.035, a + 90)
        side2 = _polar(0, 0, r * 0.035, a - 90)
        needle.moveTo(tip)
        needle.lineTo(side1)
        needle.lineTo(tail)
        needle.lineTo(side2)
        needle.closeSubpath()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        p.drawPath(needle.translated(cx + r * 0.03, cy + r * 0.05))
        p.setBrush(NEEDLE_RED)
        p.drawPath(needle.translated(cx, cy))

        # centre cap
        cap = QRadialGradient(QPointF(cx - r * 0.03, cy - r * 0.03), r * 0.12)
        cap.setColorAt(0, QColor(236, 186, 120))
        cap.setColorAt(1, QColor(50, 24, 8))
        p.setBrush(cap)
        p.drawEllipse(QPointF(cx, cy), r * 0.09, r * 0.09)

        # glass reflection
        fr = r * 0.84
        glass = QLinearGradient(cx - fr, cy - fr, cx + fr * 0.2, cy + fr * 0.2)
        glass.setColorAt(0, QColor(255, 255, 255, 90))
        glass.setColorAt(0.45, QColor(255, 255, 255, 10))
        glass.setColorAt(1, QColor(255, 255, 255, 0))
        clip = QPainterPath()
        clip.addEllipse(QPointF(cx, cy), fr, fr)
        sheen = QPainterPath()
        sheen.addEllipse(QPointF(cx - fr * 0.35, cy - fr * 0.45), fr * 0.95, fr * 0.6)
        p.setBrush(QBrush(glass))
        p.drawPath(clip.intersected(sheen))

