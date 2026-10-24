"""The tabletop radio: volume and microphone knobs, plus a dial for choosing audio devices.

Styled after radio_inspo*.jpg: wooden cabinet, copper bezel, woven speaker grille, backlit dial.
"""

import math
from types import SimpleNamespace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QConicalGradient, QFont, QFontMetrics, QLinearGradient, QPainter,
                         QPainterPath, QPen, QPolygonF, QRadialGradient, QTransform)

from . import desk, textures

# The radio is laid out at its original full size (R) and drawn scaled down into desk.RADIO.
R = QRectF(452, 318, 270, 174)
SCALE = desk.RADIO.width() / R.width()
TO_SCENE = QTransform().translate(desk.RADIO.left(), desk.RADIO.top()).scale(SCALE, SCALE).translate(-R.left(), -R.top())
TO_LAYOUT = TO_SCENE.inverted()[0]
COPPER_LIGHT = QColor(246, 190, 140)
COPPER = QColor(196, 120, 72)
COPPER_DARK = QColor(92, 46, 20)

BEZEL = R.adjusted(12, 10, -12, -16)
GRILLE = QRectF(BEZEL.left() + 10, BEZEL.top() + 9, BEZEL.width() - 20, 68)
STRIP = QRectF(BEZEL.left() + 8, GRILLE.bottom() + 4, BEZEL.width() - 16, 4)
PANEL = QRectF(BEZEL.left() + 8, STRIP.bottom() + 4, BEZEL.width() - 16, BEZEL.bottom() - 8 - (STRIP.bottom() + 4))
KNOB_R = 17
VOLUME_KNOB = QPointF(PANEL.left() + 28, PANEL.top() + 21)
INPUT_KNOB = QPointF(PANEL.right() - 28, PANEL.top() + 21)
DIAL = QRectF(PANEL.left() + 56, PANEL.top() + 5, PANEL.width() - 112, PANEL.height() - 10)


def paint_cabinet(p: QPainter):
    """Everything that does not move; drawn into the static layer."""
    p.save()
    p.setTransform(TO_SCENE, True)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    # telescopic antenna, raised up and to the left
    base = QPointF(R.left() + 30, R.top() - 4)
    tip = QPointF(R.left() - 66, R.top() - 168)
    for i, (t0, t1, w) in enumerate(((0.0, 0.4, 4.0), (0.4, 0.72, 3.0), (0.72, 1.0, 2.2))):
        a = base + (tip - base) * t0
        b = base + (tip - base) * t1
        g = QLinearGradient(a + QPointF(-w, 0), a + QPointF(w, 0))
        g.setColorAt(0, QColor(110, 110, 116))
        g.setColorAt(0.5, QColor(236, 236, 242))
        g.setColorAt(1, QColor(96, 96, 102))
        p.setPen(QPen(g, w, cap=Qt.PenCapStyle.FlatCap))
        p.drawLine(a, b)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(220, 220, 226))
    p.drawEllipse(tip, 3, 3)
    p.setBrush(desk.BRONZE_DARK)
    p.drawEllipse(base, 6, 4)

    # feet
    for x in (R.left() + 30, R.right() - 30):
        p.setBrush(QColor(24, 12, 6))
        p.drawRoundedRect(QRectF(x - 14, R.bottom() - 4, 28, 9), 3, 3)
    # top of the cabinet, catching the lamp
    top = QPolygonF([QPointF(R.left() + 12, R.top() - 10), QPointF(R.right() - 12, R.top() - 10),
                     QPointF(R.right() - 2, R.top() + 6), QPointF(R.left() + 2, R.top() + 6)])
    p.setBrush(desk._tex(textures.stand_wood(), 40, 9))
    p.drawPolygon(top)
    p.setBrush(QColor(255, 220, 170, 40))
    p.drawPolygon(top)
    # cabinet front
    body = QPainterPath()
    body.addRoundedRect(R, 22, 22)
    p.setBrush(desk._tex(textures.stand_wood(), 300, 120))
    p.drawPath(body)
    for x0, x1 in ((R.left(), R.left() + 34), (R.right(), R.right() - 34)):
        g = QLinearGradient(x0, 0, x1, 0)
        g.setColorAt(0, QColor(0, 0, 0, 130))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g)
        p.drawPath(body.intersected(_rect_path(QRectF(min(x0, x1), R.top(), 34, R.height()))))
    shade = QLinearGradient(R.topLeft(), R.bottomLeft())
    shade.setColorAt(0, QColor(255, 220, 170, 18))
    shade.setColorAt(1, QColor(0, 0, 0, 90))
    p.setBrush(shade)
    p.drawPath(body)

    # copper bezel around grille and controls
    bezel = QPainterPath()
    bezel.addRoundedRect(BEZEL, 12, 12)
    g = QLinearGradient(BEZEL.topLeft(), BEZEL.bottomRight())
    g.setColorAt(0, COPPER_LIGHT)
    g.setColorAt(0.45, COPPER)
    g.setColorAt(1, COPPER_DARK)
    p.setBrush(g)
    p.drawPath(bezel)
    inner = QPainterPath()
    inner.addRoundedRect(BEZEL.adjusted(6, 6, -6, -6), 8, 8)
    p.setBrush(QColor(30, 16, 8))
    p.drawPath(inner)

    # woven speaker grille
    p.setBrush(QColor(28, 14, 6))
    p.drawRect(GRILLE)
    p.save()
    p.setClipRect(GRILLE)
    cell = 7.0
    rows = int(GRILLE.height() / cell) + 1
    cols = int(GRILLE.width() / cell) + 1
    for r in range(rows):
        for c in range(cols):
            x = GRILLE.left() + c * cell
            y = GRILLE.top() + r * cell
            weave = QRectF(x + 1, y + 1.5, cell - 2, cell - 3) if (r + c) % 2 else QRectF(x + 1.5, y + 1, cell - 3, cell - 2)
            tone = 150 + ((r * 7 + c * 13) % 5) * 8
            p.setBrush(QColor(tone, int(tone * 0.6), int(tone * 0.36)))
            p.drawRoundedRect(weave, 1.5, 1.5)
    g = QLinearGradient(GRILLE.topLeft(), GRILLE.bottomLeft())
    g.setColorAt(0, QColor(0, 0, 0, 120))
    g.setColorAt(0.3, QColor(0, 0, 0, 0))
    g.setColorAt(1, QColor(0, 0, 0, 60))
    p.setBrush(g)
    p.drawRect(GRILLE)
    p.restore()

    # gold strip and the striped control panel below it
    g = QLinearGradient(STRIP.topLeft(), STRIP.bottomLeft())
    g.setColorAt(0, desk.BRASS_LIGHT)
    g.setColorAt(1, desk.BRASS_DARK)
    p.setBrush(g)
    p.drawRect(STRIP)
    p.setBrush(QColor(46, 26, 14))
    p.drawRoundedRect(PANEL, 4, 4)
    p.setPen(QPen(QColor(110, 70, 40, 90), 1))
    y = PANEL.top() + 4
    while y < PANEL.bottom() - 2:
        p.drawLine(QPointF(PANEL.left() + 4, y), QPointF(PANEL.right() - 4, y))
        y += 4
    # knob wells and labels
    for c, label in ((VOLUME_KNOB, "VOLUME"), (INPUT_KNOB, "INPUT")):
        p.setPen(QPen(COPPER, 1.2))
        p.setBrush(QColor(20, 10, 4))
        p.drawEllipse(c, KNOB_R + 4, KNOB_R + 4)
        font = QFont("DejaVu Sans")
        font.setPixelSize(7)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(230, 190, 130))
        p.drawText(QRectF(c.x() - 26, PANEL.bottom() - 10, 52, 9), Qt.AlignmentFlag.AlignCenter, label)
    p.restore()


def _rect_path(rect):
    path = QPainterPath()
    path.addRect(rect)
    return path


class Radio:
    def __init__(self):
        self.state = None  # audio.AudioState
        self.hover = None  # "volume", "input" or "dial"
        # hover-tag targets, shaped like the gauges so the window can reuse their tag code
        vol, inp, dial = (TO_SCENE.map(VOLUME_KNOB), TO_SCENE.map(INPUT_KNOB), TO_SCENE.map(DIAL.center()))
        self.tags = {
            "volume": SimpleNamespace(cx=vol.x(), cy=vol.y(), r=(KNOB_R + 4) * SCALE, detail=""),
            "input": SimpleNamespace(cx=inp.x(), cy=inp.y(), r=(KNOB_R + 4) * SCALE, detail=""),
            "dial": SimpleNamespace(cx=dial.x(), cy=dial.y(), r=DIAL.height() / 2 * SCALE,
                                    detail="Choose speakers and microphone"),
        }

    def update_tags(self):
        s = self.state
        if s and s.sink:
            self.tags["volume"].detail = f"Volume {s.sink.volume}%{' (muted)' if s.sink.muted else ''}: scroll or drag, click to mute"
        else:
            self.tags["volume"].detail = "No speakers found"
        if s and s.source:
            self.tags["input"].detail = f"Microphone {s.source.volume}%{' (muted)' if s.source.muted else ''}: scroll or drag, click to mute"
        else:
            self.tags["input"].detail = "No microphone found"

    def part_at(self, pt):
        pt = TO_LAYOUT.map(pt)
        for name, c in (("volume", VOLUME_KNOB), ("input", INPUT_KNOB)):
            if math.hypot(pt.x() - c.x(), pt.y() - c.y()) <= KNOB_R + 5:
                return name
        if DIAL.contains(pt):
            return "dial"
        return None

    def contains(self, pt):
        return R.adjusted(0, -10, 0, 6).contains(TO_LAYOUT.map(pt))

    def damage_rect(self):
        return TO_SCENE.mapRect(PANEL.adjusted(-8, -8, 8, 8))

    def paint(self, p: QPainter):
        s = self.state
        sink = s.sink if s else None
        source = s.source if s else None
        p.save()
        p.setTransform(TO_SCENE, True)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_dial(p, sink, source)
        self._paint_knob(p, VOLUME_KNOB, sink, self.hover == "volume")
        self._paint_knob(p, INPUT_KNOB, source, self.hover == "input")
        p.restore()

    def _paint_dial(self, p, sink, source):
        lit = sink is not None and not sink.muted
        g = QLinearGradient(DIAL.topLeft(), DIAL.bottomLeft())
        if lit:
            g.setColorAt(0, QColor(250, 214, 140))
            g.setColorAt(1, QColor(214, 150, 70))
        else:
            g.setColorAt(0, QColor(120, 100, 70))
            g.setColorAt(1, QColor(90, 70, 46))
        p.setPen(QPen(COPPER_DARK, 1))
        p.setBrush(g)
        p.drawRoundedRect(DIAL, 3, 3)
        if lit:  # warm glow spilling onto the panel
            glow = QRadialGradient(DIAL.center(), DIAL.width() * 0.7)
            glow.setColorAt(0, QColor(255, 190, 90, 50))
            glow.setColorAt(1, QColor(255, 190, 90, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawRect(DIAL.adjusted(-20, -8, 20, 8))
        font = QFont("DejaVu Sans Condensed")
        font.setPixelSize(8)
        font.setBold(True)
        fm = QFontMetrics(font)
        p.setFont(font)
        ink = QColor(60, 30, 10)
        half = DIAL.height() / 2
        for i, (tag, dev) in enumerate((("OUT", sink), ("IN", source))):
            row = QRectF(DIAL.left() + 4, DIAL.top() + i * half, DIAL.width() - 8, half)
            p.setPen(ink)
            p.drawText(QRectF(row.left(), row.top(), 18, row.height()), Qt.AlignmentFlag.AlignVCenter, tag)
            name = dev.description if dev else "none"
            if dev and dev.muted:
                name = "muted"
            p.drawText(QRectF(row.left() + 19, row.top(), row.width() - 19, row.height()), Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(name, Qt.TextElideMode.ElideRight, int(row.width() - 19)))
        # tuning needle shows the output volume across the dial
        if sink:
            x = DIAL.left() + 3 + (DIAL.width() - 6) * min(sink.volume, 100) / 100
            p.setPen(QPen(QColor(200, 30, 20, 220), 1.6))
            p.drawLine(QPointF(x, DIAL.top() + 2), QPointF(x, DIAL.bottom() - 2))
        if self.hover == "dial":
            p.setPen(QPen(QColor(255, 230, 170, 200), 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(DIAL.adjusted(-2, -2, 2, 2), 4, 4)

    def _paint_knob(self, p, c, dev, hover):
        r = KNOB_R
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawEllipse(c + QPointF(1.5, 3), r, r)
        skirt = QRadialGradient(c - QPointF(r * 0.4, r * 0.4), r * 1.4)
        skirt.setColorAt(0, COPPER_LIGHT.lighter(110) if hover else COPPER_LIGHT)
        skirt.setColorAt(0.55, COPPER)
        skirt.setColorAt(1, COPPER_DARK)
        p.setBrush(skirt)
        p.drawEllipse(c, r, r)
        # brushed-metal cap, like the knobs in radio_inspo3.jpg
        cap = QConicalGradient(c, 45)
        for stop, shade in ((0, 250), (0.25, 180), (0.5, 240), (0.75, 170), (1, 250)):
            cap.setColorAt(stop, QColor(shade, int(shade * 0.72), int(shade * 0.52)))
        p.setBrush(cap)
        p.drawEllipse(c, r * 0.64, r * 0.64)
        # pointer: -135 deg at 0 %, +135 deg at 100 %
        level = min(dev.volume, 100) / 100 if dev else 0
        a = math.radians(-135 + 270 * level - 90)
        tip = c + QPointF(math.cos(a) * r * 0.86, math.sin(a) * r * 0.86)
        p.setPen(QPen(QColor(40, 18, 6), 2.2, cap=Qt.PenCapStyle.RoundCap))
        p.drawLine(c + QPointF(math.cos(a) * r * 0.6, math.sin(a) * r * 0.6), tip)
        # mute lamp
        lamp = c + QPointF(r + 5, -r - 2)
        muted = dev is not None and dev.muted
        p.setPen(QPen(QColor(40, 20, 10), 0.6))
        p.setBrush(QColor(240, 50, 30) if muted else QColor(70, 30, 20))
        p.drawEllipse(lamp, 2.6, 2.6)
