"""Layout and painting of the roll-top desk, seen from the chair (modelled on desk_inspo.jpg).

Everything is drawn on a fixed 1920-wide scene. The screen shows the top 1080 rows; the rest
(below the front edge) comes into view when the camera tilts down into an open drawer.
"""

import getpass

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QRadialGradient, QTransform)

from . import textures

W, H = 1920, 1080  # the visible viewport
SCENE_H = 1520

# --- layout -----------------------------------------------------------------
ORGANIZER = QRectF(214, 60, 1492, 374)
SURFACE_BACK_Y, SURFACE_FRONT_Y = 432, 880
SURFACE = QPolygonF([QPointF(214, 432), QPointF(1706, 432), QPointF(2080, 880), QPointF(-160, 880)])
SURFACE_WORLD = QRectF(0, 0, 2200, 1000)  # flat desk-top coordinates mapped onto SURFACE
BLOTTER_WORLD = QRectF(560, 500, 1080, 440)
FRONT_EDGE = QRectF(-20, 880, 1960, 38)
BODY_TOP = 918

FILES_DRAWER = LEFT_DRAWER = QRectF(30, 930, 500, 136)
CENTER_DRAWER = QRectF(580, 930, 760, 136)
PROGRAMS_DRAWER = QRectF(1390, 930, 500, 136)
LOWER_DRAWERS = [QRectF(30, 1084, 500, 196), QRectF(30, 1296, 500, 206),
                 QRectF(1390, 1084, 500, 196), QRectF(1390, 1296, 500, 206)]
KNEEHOLE = QRectF(560, 1082, 800, SCENE_H - 1082)


def _cubbies():
    o = ORGANIZER
    cells = []
    for block in (QRectF(o.left() + 14, o.top() + 14, 466, 282), QRectF(o.right() - 480, o.top() + 14, 466, 282)):
        cw = (block.width() - 2 * 10) / 3
        rh = (block.height() - 10) / 2
        for r in range(2):
            for c in range(3):
                cells.append(QRectF(block.left() + c * (cw + 10), block.top() + r * (rh + 10), cw, rh))
    return cells


CUBBIES = _cubbies()
SLOTS = QRectF(708, 148, 504, 208)  # the upright letter slots in the middle: one per open program
N_SLOTS = 11

# the gauge stand sits back against the organiser, in front of its middle drawers
GAUGE_STAND = QRectF(745, 380, 430, 104)  # front face; the lit top sits just above it
GAUGE_RADIUS = 44
GAUGE_CENTERS = [(807 + i * 102, 432) for i in range(4)]
RADIO = QRectF(434.8, 366.7, 194.4, 125.3)  # front face of the radio, back left beside the gauges
GLOBE_CENTER = (1600, 486)
GLOBE_RADIUS = 66

BRASS_LIGHT = QColor(246, 214, 128)
BRASS = QColor(196, 152, 66)
BRASS_DARK = QColor(104, 72, 22)
BRONZE_LIGHT = QColor(240, 186, 116)
BRONZE = QColor(176, 110, 52)
BRONZE_DARK = QColor(78, 40, 14)


# --- helpers ------------------------------------------------------------------

def _tex(pixmap, dx=0, dy=0):
    b = QBrush(pixmap)
    b.setTransform(QTransform.fromTranslate(dx, dy))
    return b


def surface_transform():
    t = QTransform()
    corners = QPolygonF([SURFACE_WORLD.topLeft(), SURFACE_WORLD.topRight(),
                         SURFACE_WORLD.bottomRight(), SURFACE_WORLD.bottomLeft()])
    QTransform.quadToQuad(corners, SURFACE, t)
    return t


def bevel(p, rect, brush, depth=3, radius=0, light=60, dark=120):
    """Fill a rectangle and give it a raised edge."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(brush)
    p.drawRoundedRect(rect, radius, radius)
    for i in range(depth):
        a = int(light * (1 - i / depth))
        p.setPen(QPen(QColor(255, 210, 170, a), 1))
        p.drawLine(QPointF(rect.left() + i, rect.top() + i + 0.5), QPointF(rect.right() - i, rect.top() + i + 0.5))
        p.drawLine(QPointF(rect.left() + i + 0.5, rect.top() + i), QPointF(rect.left() + i + 0.5, rect.bottom() - i))
        a = int(dark * (1 - i / depth))
        p.setPen(QPen(QColor(10, 3, 0, a), 1))
        p.drawLine(QPointF(rect.left() + i, rect.bottom() - i - 0.5), QPointF(rect.right() - i, rect.bottom() - i - 0.5))
        p.drawLine(QPointF(rect.right() - i - 0.5, rect.top() + i), QPointF(rect.right() - i - 0.5, rect.bottom() - i))
    p.restore()


def inset(p, rect, alpha=190, lining=None):
    """A shadowed recess (cubby, drawer cavity), optionally lined with a texture."""
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(12, 5, 2) if lining is None else lining)
    p.drawRect(rect)
    g = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
    g.setColorAt(0, QColor(0, 0, 0, alpha))
    g.setColorAt(0.6, QColor(0, 0, 0, 0))
    p.setBrush(g)
    p.drawRect(rect)
    p.restore()


def _metal(p, c, r, light, mid, dark):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 110))
    p.drawEllipse(c + QPointF(r * 0.2, r * 0.35), r * 1.05, r * 1.05)
    g = QRadialGradient(c - QPointF(r * 0.35, r * 0.35), r * 1.3)
    g.setColorAt(0, light)
    g.setColorAt(0.5, mid)
    g.setColorAt(1, dark)
    p.setBrush(g)
    p.drawEllipse(c, r, r)


def brass_knob(p, c, r):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # rosette back plate
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(BRASS_DARK)
    p.drawEllipse(c, r * 1.35, r * 1.35)
    _metal(p, c, r, BRASS_LIGHT, BRASS, BRASS_DARK)
    p.setPen(QPen(QColor(90, 60, 20, 160), max(1.0, r * 0.12)))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r * 0.55, r * 0.55)
    # specular glint
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 250, 220, 200))
    p.drawEllipse(c - QPointF(r * 0.38, r * 0.38), r * 0.18, r * 0.14)
    p.restore()


def bail_pull(p, c, w):
    """Chippendale-style bail handle like the deep drawers in desk_inspo.jpg."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    h = w * 0.32
    for sx in (-1, 1):
        brass_knob(p, c + QPointF(sx * w * 0.42, -h * 0.25), w * 0.06)
    path = QPainterPath()
    path.moveTo(c.x() - w * 0.42, c.y() - h * 0.25)
    path.cubicTo(c.x() - w * 0.55, c.y() + h * 0.2, c.x() - w * 0.3, c.y() + h * 0.9, c.x() - w * 0.15, c.y() + h * 0.6)
    path.lineTo(c.x() + w * 0.15, c.y() + h * 0.6)
    path.cubicTo(c.x() + w * 0.3, c.y() + h * 0.9, c.x() + w * 0.55, c.y() + h * 0.2, c.x() + w * 0.42, c.y() - h * 0.25)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.setPen(QPen(QColor(0, 0, 0, 110), w * 0.07, cap=Qt.PenCapStyle.RoundCap))
    p.drawPath(path.translated(2, 5))
    g = QLinearGradient(c.x(), c.y() - h, c.x(), c.y() + h)
    g.setColorAt(0, BRASS_LIGHT)
    g.setColorAt(1, BRASS_DARK)
    p.setPen(QPen(QBrush(g), w * 0.06, cap=Qt.PenCapStyle.RoundCap))
    p.drawPath(path)
    grip = QRectF(c.x() - w * 0.17, c.y() + h * 0.42, w * 0.34, h * 0.36)
    gg = QLinearGradient(grip.topLeft(), grip.bottomLeft())
    gg.setColorAt(0, QColor(140, 70, 36))
    gg.setColorAt(1, QColor(60, 22, 8))
    p.setPen(QPen(BRASS_DARK, 1))
    p.setBrush(gg)
    p.drawRoundedRect(grip, h * 0.18, h * 0.18)
    p.restore()


def keyhole(p, c, s):
    """Brass escutcheon with a keyhole."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    plate = QPainterPath()
    plate.addEllipse(c, s * 0.9, s * 1.3)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 100))
    p.drawPath(plate.translated(1, 2))
    g = QLinearGradient(c - QPointF(s, s), c + QPointF(s, s))
    g.setColorAt(0, BRASS_LIGHT)
    g.setColorAt(1, BRASS_DARK)
    p.setBrush(g)
    p.drawPath(plate)
    hole = QPainterPath()
    hole.addEllipse(c - QPointF(0, s * 0.3), s * 0.25, s * 0.25)
    hole.addRect(QRectF(c.x() - s * 0.1, c.y() - s * 0.3, s * 0.2, s * 0.8))
    p.setBrush(QColor(10, 4, 0))
    p.drawPath(hole.simplified())
    p.restore()


def card_holder(p, c, w, text):
    """Brass label frame, as on old filing drawers."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    h = w * 0.3
    frame = QRectF(c.x() - w / 2, c.y() - h / 2, w, h)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 100))
    p.drawRoundedRect(frame.translated(2, 3), 3, 3)
    g = QLinearGradient(frame.topLeft(), frame.bottomLeft())
    g.setColorAt(0, BRASS_LIGHT)
    g.setColorAt(0.5, BRASS)
    g.setColorAt(1, BRASS_DARK)
    p.setPen(QPen(QColor(70, 45, 10), 1))
    p.setBrush(g)
    p.drawRoundedRect(frame, 3, 3)
    card = frame.adjusted(w * 0.06, h * 0.18, -w * 0.06, -h * 0.18)
    p.setBrush(QColor(232, 220, 190))
    p.setPen(QPen(QColor(120, 90, 40), 0.8))
    p.drawRect(card)
    font = QFont("C059")
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 115)
    size = int(card.height() * 0.62)
    font.setPixelSize(size)
    while size > 6 and QFontMetrics(font).horizontalAdvance(text) > card.width() - 8:
        size -= 1
        font.setPixelSize(size)
    p.setFont(font)
    p.setPen(QColor(50, 36, 24))
    p.drawText(card, Qt.AlignmentFlag.AlignCenter, text)
    for x in (frame.left() + w * 0.03, frame.right() - w * 0.03):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(BRASS_DARK)
        p.drawEllipse(QPointF(x, c.y()), 1.8, 1.8)
    p.restore()


def leaf_carving(p, c, w):
    """The carved olive branch on the centre drawer of desk_inspo.jpg."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for offset, color in ((QPointF(0, 1.4), QColor(255, 190, 140, 45)), (QPointF(0, 0), QColor(16, 5, 1, 190))):
        p.setPen(QPen(color, 1.8, cap=Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        stem = QPainterPath()
        o = c + offset
        stem.moveTo(o.x() - w / 2, o.y() + 5)
        stem.cubicTo(o.x() - w / 4, o.y() - 7, o.x() + w / 4, o.y() + 7, o.x() + w / 2, o.y() - 5)
        p.drawPath(stem)
        for i in range(1, 12):
            t = i / 12
            pt = stem.pointAtPercent(t)
            ang = stem.angleAtPercent(t)
            for side in (-1, 1):
                leaf = QPainterPath()
                leaf.moveTo(0, 0)
                leaf.quadTo(10, side * 6, 20, side * 8)
                leaf.quadTo(9, side * 1, 0, 0)
                tr = QTransform()
                tr.translate(pt.x(), pt.y())
                tr.rotate(-ang + side * 28 - 10)
                p.setBrush(color if offset.y() == 0 else Qt.BrushStyle.NoBrush)
                p.drawPath(tr.map(leaf))
    p.restore()


def drawer_front(p, rect, kind, label=None, highlight=0.0):
    """kind: 'knob' (small drawer), 'bail' (deep drawer) or 'center'."""
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 140))
    p.drawRect(rect.adjusted(-3, -2, 4, 5))
    bevel(p, rect, _tex(textures.desk_wood(), rect.left() * 1.7, rect.top() * 2.3), depth=5)
    # moulded raised panel
    panel = rect.adjusted(14, 12, -14, -12)
    p.setPen(QPen(QColor(10, 3, 0, 150), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(panel)
    p.setPen(QPen(QColor(255, 200, 150, 45), 1))
    p.drawRect(panel.adjusted(2, 2, -2, -2))
    # satin finish: only a faint lift at the top where the lamp catches it
    sheen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    sheen.setColorAt(0, QColor(255, 220, 180, 10))
    sheen.setColorAt(0.5, QColor(255, 220, 180, 0))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(sheen)
    p.drawRect(rect)
    c = rect.center()
    if kind == "knob":
        if label:
            card_holder(p, QPointF(c.x(), rect.top() + rect.height() * 0.33), 150, label)
            brass_knob(p, QPointF(c.x(), rect.top() + rect.height() * 0.7), 13)
        else:
            brass_knob(p, c, 13)
    elif kind == "bail":
        bail_pull(p, c - QPointF(0, 8), rect.width() * 0.3)
    elif kind == "center":
        brass_knob(p, QPointF(rect.left() + 80, c.y()), 13)
        brass_knob(p, QPointF(rect.right() - 80, c.y()), 13)
        card_holder(p, QPointF(c.x(), c.y() - 18), 170, label or "")
        keyhole(p, QPointF(c.x(), c.y() + 30), 9)
        leaf_carving(p, QPointF(c.x() - 185, c.y()), 160)
        leaf_carving(p, QPointF(c.x() + 185, c.y()), 160)
    if highlight > 0:
        p.setPen(QPen(QColor(255, 214, 140, int(130 * highlight)), 3))
        p.setBrush(QColor(255, 220, 160, int(22 * highlight)))
        p.drawRect(rect.adjusted(1, 1, -1, -1))
    p.restore()


# --- static scene -------------------------------------------------------------

def _room(p):
    p.fillRect(QRectF(0, 0, W, SCENE_H), _tex(textures.wallpaper()))
    p.fillRect(QRectF(0, 0, W, SCENE_H), QColor(0, 0, 0, 90))


def _tambour(p):
    """Underside of the rolled-up tambour, curving overhead."""
    band = QRectF(150, 0, 1620, ORGANIZER.top() + 4)
    p.fillRect(band, _tex(textures.desk_wood_dark()))
    y = band.bottom()
    step = 7.0
    while y > 0:
        p.fillRect(QRectF(band.left(), y, band.width(), 1.4), QColor(0, 0, 0, 150))
        p.fillRect(QRectF(band.left(), y + 1.4, band.width(), 1), QColor(255, 190, 140, 18))
        y -= step
        step *= 1.12  # slats spread out as the curve comes towards us
    g = QLinearGradient(0, 0, 0, band.bottom())
    g.setColorAt(0, QColor(0, 0, 0, 120))
    g.setColorAt(1, QColor(0, 0, 0, 200))
    p.fillRect(band, g)


def _organizer(p):
    o = ORGANIZER
    p.fillRect(o.adjusted(-14, -10, 14, 0), _tex(textures.desk_wood_dark()))
    bevel(p, o, _tex(textures.desk_wood(), 31, 0), depth=4)
    blocks = [QRectF(o.left() + 14, o.top() + 14, 466, 282), QRectF(o.right() - 480, o.top() + 14, 466, 282)]
    for cell in CUBBIES:
        inset(p, cell, alpha=140, lining=_tex(textures.felt()))  # lined with the same baize as the drawers
        p.fillRect(cell, QColor(0, 0, 0, 70))  # deeper in, so a little darker than an open drawer
        # soft shadow cast by the shelf above, fading into the baize rather than a dark band
        g = QLinearGradient(0, cell.top(), 0, cell.top() + 28)
        g.setColorAt(0, QColor(0, 0, 0, 120))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(cell.left(), cell.top(), cell.width(), 28), g)

    # centre: arched valance over upright letter slots, after desk_inspo2.jpeg
    centre = QRectF(blocks[0].right() + 14, o.top() + 14, blocks[1].left() - blocks[0].right() - 28, 282)
    slots = SLOTS
    n_slots = N_SLOTS
    sw = slots.width() / n_slots
    # the back panel: the desk's own wood, set well back, so it is darker than the dividers in front of it
    inset(p, slots, alpha=170, lining=_tex(textures.desk_wood(vertical=True), 23, 5))
    p.fillRect(slots, QColor(0, 0, 0, 105))
    g = QLinearGradient(0, slots.top(), 0, slots.top() + 46)  # shadow of the arched valance overhead
    g.setColorAt(0, QColor(0, 0, 0, 150))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(slots.left(), slots.top(), slots.width(), 46), g)
    for i in range(n_slots):
        x0, x1 = slots.left() + i * sw + 3, slots.left() + (i + 1) * sw - 3
        # each divider throws a shadow to its right, away from the lamp on the left
        g = QLinearGradient(x0, 0, x0 + 14, 0)
        g.setColorAt(0, QColor(0, 0, 0, 140))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(x0, slots.top(), 14, slots.height()), g)
        # and the far corner, where the back meets the next divider, is a little darker
        g = QLinearGradient(x1, 0, x1 - 6, 0)
        g.setColorAt(0, QColor(0, 0, 0, 80))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(QRectF(x1 - 6, slots.top(), 6, slots.height()), g)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i in range(n_slots):
        x = slots.left() + i * sw
        if i:
            div = QRectF(x - 3, slots.top(), 6, slots.height())
            p.fillRect(div, _tex(textures.desk_wood(vertical=True), i * 17))
            p.fillRect(QRectF(x - 3, slots.top(), 1.5, slots.height()), QColor(255, 200, 150, 50))
            p.fillRect(QRectF(x + 1.5, slots.top(), 1.5, slots.height()), QColor(0, 0, 0, 120))
    p.restore()
    valance = QRectF(centre.left(), centre.top(), centre.width(), 74)
    arch = QPainterPath()
    arch.moveTo(valance.bottomLeft())
    arch.lineTo(valance.left(), valance.top())
    arch.lineTo(valance.right(), valance.top())
    arch.lineTo(valance.bottomRight())
    arch.cubicTo(valance.right() - 40, valance.top() + 34, valance.left() + 40, valance.top() + 34, valance.left(), valance.bottom())
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 120))
    p.drawPath(arch.translated(0, 5))
    p.setBrush(_tex(textures.desk_wood(), 70, 11))
    p.drawPath(arch)
    p.setPen(QPen(QColor(255, 200, 150, 60), 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(arch)
    # gilt lettering: the owner's name, made smaller if it is long
    name = getpass.getuser().upper()
    font = QFont("C059")
    font.setBold(True)
    font.setLetterSpacing(QFont.SpacingType.PercentageSpacing, 160)
    for size in range(22, 11, -1):
        font.setPixelSize(size)
        if QFontMetrics(font).horizontalAdvance(name) <= valance.width() - 80:
            break
    p.setFont(font)
    text_box = QRectF(valance.left() + 40, valance.top() + 4, valance.width() - 80, 30)
    name = QFontMetrics(font).elidedText(name, Qt.TextElideMode.ElideRight, int(text_box.width()))
    p.setPen(QColor(0, 0, 0, 150))
    p.drawText(text_box.translated(1, 1.5), Qt.AlignmentFlag.AlignCenter, name)
    p.setPen(QColor(222, 180, 92))
    p.drawText(text_box, Qt.AlignmentFlag.AlignCenter, name)
    p.restore()

    # row of small drawers along the bottom
    row = QRectF(o.left() + 14, o.top() + 306, o.width() - 28, o.height() - 316)
    widths = [233, 233, 162, 162, 162, 233, 233]
    gap = (row.width() - sum(widths)) / (len(widths) - 1)
    x = row.left()
    for i, w in enumerate(widths):
        d = QRectF(x, row.top(), w, row.height())
        inset(p, d.adjusted(-2, -2, 2, 2))
        bevel(p, d, _tex(textures.desk_wood(), x * 3, i * 40), depth=3)
        brass_knob(p, d.center(), 7)
        x += w + gap


def _side_panel(p, mirror):
    """The curved roll-top side, seen from the inside at close range."""
    def m(x, y):
        return QPointF(W - x if mirror else x, y)

    face = QPainterPath()
    face.moveTo(m(214, -10))
    face.lineTo(m(214, 432))
    face.lineTo(m(-160, 880))
    face.cubicTo(m(-70, 430), m(50, 130), m(160, -10))
    face.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(_tex(textures.desk_wood(vertical=True), 40 if mirror else 0))
    p.drawPath(face)
    g = QLinearGradient(m(0, 0), m(214, 0))
    g.setColorAt(0, QColor(255, 210, 160, 30))
    g.setColorAt(1, QColor(0, 0, 0, 150))
    p.setBrush(g)
    p.drawPath(face)
    # the corner where side meets back is in shadow
    p.setBrush(QColor(0, 0, 0, 80))
    corner = QPainterPath()
    corner.moveTo(m(214, -10))
    corner.lineTo(m(214, 432))
    corner.lineTo(m(190, 460))
    corner.lineTo(m(190, -10))
    corner.closeSubpath()
    p.drawPath(corner)

    edge = QPainterPath()
    edge.moveTo(m(160, -10))
    edge.cubicTo(m(50, 130), m(-70, 430), m(-160, 880))
    edge.lineTo(m(-200, 880))
    edge.cubicTo(m(-110, 420), m(14, 120), m(126, -10))
    edge.closeSubpath()
    p.setBrush(_tex(textures.desk_wood(vertical=True), 13))
    p.drawPath(edge)
    p.setBrush(QColor(20, 6, 0, 80))
    p.drawPath(edge)
    p.setPen(QPen(QColor(255, 210, 160, 80), 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    hl = QPainterPath()
    hl.moveTo(m(158, -10))
    hl.cubicTo(m(48, 130), m(-72, 430), m(-162, 880))
    p.drawPath(hl)


def _surface(p):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    # wood and leather drawn flat, then projected so the grain recedes properly
    p.setTransform(surface_transform(), True)
    p.drawTiledPixmap(SURFACE_WORLD, textures.desk_top(), QPointF(0, 140))
    b = BLOTTER_WORLD
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 90))
    p.drawRect(b.translated(4, 8))
    p.drawTiledPixmap(b, textures.leather())
    gold = QPen(QColor(200, 158, 76, 200), 2.5)
    p.setPen(gold)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(b.adjusted(18, 18, -18, -18))
    p.setPen(QPen(QColor(200, 158, 76, 150), 1.2))
    p.drawRect(b.adjusted(26, 26, -26, -26))
    # darker leather corner pieces of the desk pad
    p.setPen(Qt.PenStyle.NoPen)
    for cx, cy, sx, sy in ((b.left(), b.top(), 1, 1), (b.right(), b.top(), -1, 1),
                           (b.left(), b.bottom(), 1, -1), (b.right(), b.bottom(), -1, -1)):
        tri = QPolygonF([QPointF(cx, cy), QPointF(cx + sx * 120, cy), QPointF(cx, cy + sy * 120)])
        p.setBrush(QColor(30, 8, 5, 200))
        p.drawPolygon(tri)
        p.setPen(QPen(QColor(200, 158, 76, 160), 1.5))
        p.drawLine(QPointF(cx + sx * 120, cy), QPointF(cx, cy + sy * 120))
        p.setPen(Qt.PenStyle.NoPen)
    p.restore()

    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    path = QPainterPath()
    path.addPolygon(SURFACE)
    p.setClipPath(path)
    # ambient occlusion where the surface meets the organiser, light pooling towards us
    g = QLinearGradient(0, SURFACE_BACK_Y, 0, SURFACE_FRONT_Y)
    g.setColorAt(0, QColor(0, 0, 0, 200))
    g.setColorAt(0.12, QColor(0, 0, 0, 70))
    g.setColorAt(0.5, QColor(0, 0, 0, 0))
    g.setColorAt(1, QColor(0, 0, 0, 40))
    p.fillRect(QRectF(-200, SURFACE_BACK_Y, W + 400, 450), g)
    # varnish: a broad soft reflection of the lamp
    # a soft warm pool of lamplight rather than a mirror-like reflection
    sheen = QRadialGradient(QPointF(760, 560), 620)
    sheen.setColorAt(0, QColor(255, 200, 140, 18))
    sheen.setColorAt(1, QColor(255, 200, 140, 0))
    p.setTransform(QTransform(1, 0, 0, 0.38, 0, 560 * 0.62), True)
    p.fillRect(QRectF(0, 0, W, 2000), sheen)
    p.restore()


def _front_edge(p):
    e = FRONT_EDGE
    p.save()
    g = QLinearGradient(e.topLeft(), e.bottomLeft())
    g.setColorAt(0, QColor(255, 210, 160, 50))
    g.setColorAt(0.18, QColor(255, 210, 160, 12))
    g.setColorAt(0.55, QColor(0, 0, 0, 30))
    g.setColorAt(1, QColor(0, 0, 0, 200))
    p.fillRect(e, _tex(textures.desk_wood(), 0, 77))
    p.fillRect(e, g)
    p.fillRect(QRectF(e.left(), e.top(), e.width(), 1.5), QColor(255, 220, 180, 120))
    p.restore()


def _body(p):
    body = QRectF(-20, BODY_TOP, W + 40, SCENE_H - BODY_TOP)
    p.fillRect(body, _tex(textures.desk_wood(), 0, 3))
    p.fillRect(body, QColor(0, 0, 0, 70))
    # kneehole: the dark space where your legs go
    p.fillRect(KNEEHOLE, _tex(textures.desk_wood_dark(vertical=True)))
    g = QLinearGradient(0, KNEEHOLE.top(), 0, KNEEHOLE.bottom())
    g.setColorAt(0, QColor(0, 0, 0, 230))
    g.setColorAt(1, QColor(0, 0, 0, 170))
    p.fillRect(KNEEHOLE, g)
    for d in LOWER_DRAWERS:
        inset(p, d.adjusted(-3, -3, 3, 3))
        drawer_front(p, d, "bail")
    for d in (LEFT_DRAWER, CENTER_DRAWER, PROGRAMS_DRAWER):
        inset(p, d)  # the live drawers are drawn on top each frame
    # shadow under the lip of the desk top
    lip = QLinearGradient(0, BODY_TOP, 0, BODY_TOP + 60)
    lip.setColorAt(0, QColor(0, 0, 0, 170))
    lip.setColorAt(1, QColor(0, 0, 0, 0))
    p.fillRect(QRectF(body.left(), BODY_TOP, body.width(), 60), lip)


def _contact_shadow(p, c, rx, ry, alpha=160):
    g = QRadialGradient(c, rx)
    g.setColorAt(0, QColor(0, 0, 0, alpha))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.setTransform(QTransform(1, 0, 0, ry / rx, 0, c.y() * (1 - ry / rx)), True)
    p.drawEllipse(c, rx, rx)
    p.restore()


def _reflect(p, paint_fn, area, base_y, strength=0.2, length=70):
    """Faint mirror image of an object in the polished desk top."""
    scale = 2
    img = QImage(int(area.width() * scale), int(area.height() * scale), QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(0)
    ip = QPainter(img)
    ip.setRenderHint(QPainter.RenderHint.Antialiasing)
    ip.scale(scale, scale)
    ip.translate(-area.left(), -area.top())
    paint_fn(ip)
    # fade out with distance from the contact line
    ip.resetTransform()
    ip.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
    fade = QLinearGradient(0, (base_y - area.top()) * scale, 0, (base_y - area.top() - length) * scale)
    fade.setColorAt(0, QColor(0, 0, 0, int(255 * strength)))
    fade.setColorAt(1, QColor(0, 0, 0, 0))
    ip.fillRect(img.rect(), fade)
    ip.end()
    p.save()
    p.translate(0, 2 * base_y)
    p.scale(1, -1)
    p.drawImage(area, img)
    p.restore()


def paint_gauge_stand(p, gauges):
    """A free-standing walnut instrument stand with bronze trim and bun feet."""
    s = GAUGE_STAND
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    # bronze bun feet
    for x in (s.left() + 26, s.right() - 26):
        g = QRadialGradient(QPointF(x - 4, s.bottom() + 2), 16)
        g.setColorAt(0, BRONZE_LIGHT)
        g.setColorAt(1, BRONZE_DARK)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(x, s.bottom() + 5), 15, 9)
    # lit top face, slightly receding
    top = QPolygonF([QPointF(s.left() + 8, s.top() - 12), QPointF(s.right() - 8, s.top() - 12),
                     QPointF(s.right(), s.top()), QPointF(s.left(), s.top())])
    p.setBrush(_tex(textures.stand_wood(), 13, 7))
    p.drawPolygon(top)
    p.setBrush(QColor(255, 220, 170, 50))
    p.drawPolygon(top)
    # front face
    path = QPainterPath()
    path.addRoundedRect(s, 4, 4)
    p.setBrush(_tex(textures.stand_wood(), 90, 40))
    p.drawPath(path)
    gloss = QLinearGradient(s.topLeft(), s.bottomLeft())
    gloss.setColorAt(0, QColor(255, 235, 200, 16))
    gloss.setColorAt(0.4, QColor(255, 235, 200, 0))
    gloss.setColorAt(1, QColor(0, 0, 0, 120))
    p.setBrush(gloss)
    p.drawPath(path)
    # bronze trim along top and base
    for y, h in ((s.top(), 5), (s.bottom() - 8, 8)):
        g = QLinearGradient(0, y, 0, y + h)
        g.setColorAt(0, BRONZE_LIGHT)
        g.setColorAt(1, BRONZE_DARK)
        p.setBrush(g)
        p.drawRect(QRectF(s.left(), y, s.width(), h))
    # end shading so it reads as a solid block
    for x0, x1 in ((s.left(), s.left() + 30), (s.right(), s.right() - 30)):
        g = QLinearGradient(x0, 0, x1, 0)
        g.setColorAt(0, QColor(0, 0, 0, 110))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g)
        p.drawRect(QRectF(min(x0, x1), s.top(), 30, s.height()))
    p.restore()
    for g in gauges:
        g.paint_static(p)


def paint_static(p, gauges, globe, on_desk=None):
    """The unchanging layer. on_desk(p) draws whatever lies flat on the desk top, under the objects standing on it."""
    _room(p)
    _tambour(p)
    _organizer(p)
    _surface(p)
    _side_panel(p, mirror=False)
    _side_panel(p, mirror=True)
    if on_desk:
        on_desk(p)

    # objects standing on the desk, each with a reflection and a contact shadow
    stand_area = QRectF(GAUGE_STAND.left() - 10, GAUGE_STAND.top() - 16, GAUGE_STAND.width() + 20, GAUGE_STAND.height() + 34)
    stand_base = GAUGE_STAND.bottom() + 12
    _reflect(p, lambda q: paint_gauge_stand(q, gauges), stand_area, stand_base, 0.07, 40)
    _contact_shadow(p, QPointF(GAUGE_STAND.center().x() + 10, stand_base), GAUGE_STAND.width() * 0.62, 26, 190)
    paint_gauge_stand(p, gauges)

    gx, gy = GLOBE_CENTER
    gr = GLOBE_RADIUS
    globe_area = QRectF(gx - gr * 1.4, gy + gr * 0.9, gr * 2.8, gr * 1.3)
    _reflect(p, globe.paint_stand, globe_area, gy + gr * 1.85 + gr * 0.22, 0.08, 30)
    globe.paint_stand(p)

    radio_area = QRectF(RADIO.left() - 10, RADIO.top() - 20, RADIO.width() + 20, RADIO.height() + 36)
    radio_base = RADIO.bottom() + 6
    from .radio import paint_cabinet as paint_radio_cabinet  # radio.py builds on this module
    _reflect(p, paint_radio_cabinet, radio_area, radio_base, 0.07, 36)
    _contact_shadow(p, QPointF(RADIO.center().x() + 10, radio_base), RADIO.width() * 0.64, 24, 190)
    paint_radio_cabinet(p)

    from . import clock, lamp, note, pencup
    clock.paint_static(p)
    lamp.paint_shadow(p)
    pencup.paint_shadow(p)
    note.paint_shadow(p)

    _front_edge(p)
    _body(p)


# The sealed letter lies on the desk top in front of the inkwell (flat desk-top coordinates, as SURFACE_WORLD).
ENVELOPE_CENTER = QPointF(1688, 352)
ENVELOPE_SIZE = (214, 136)
ENVELOPE_ANGLE = -8.0  # dropped a little askew
_ENV_IMG = (428, 272)  # resolution the letter is drawn at before it is laid onto the desk
_env_image = None


def envelope_transform(hover=0.0):
    """Letter pixels -> scene: flat on the desk, tipped a little towards the viewer, lifting under the pointer."""
    w, h = ENVELOPE_SIZE
    iw, ih = _ENV_IMG
    t = QTransform()
    t.translate(ENVELOPE_CENTER.x(), ENVELOPE_CENTER.y())
    t.rotate(ENVELOPE_ANGLE)
    t.translate(-w / 2, -h / 2)
    t.scale(w / iw, h / ih)
    flat = (t * surface_transform()).map(QPolygonF(QRectF(0, 0, iw, ih)))
    tl, tr, br, bl = flat[0], flat[1], flat[2], flat[3]
    up = (br - bl)
    height = (up.x() ** 2 + up.y() ** 2) ** 0.5 * ih / iw * 0.8
    upright = 0.25 + 0.1 * hover
    lift = QPointF(0, -5 * hover)
    quad = QPolygonF([tl + (QPointF(bl.x(), bl.y() - height) - tl) * upright + lift,
                      tr + (QPointF(br.x(), br.y() - height) - tr) * upright + lift, br + lift, bl + lift])
    out = QTransform()
    QTransform.quadToQuad(QPolygonF(QRectF(0, 0, iw, ih)), quad, out)
    return out


def envelope_polygon(hover=0.0):
    return envelope_transform(hover).map(QPolygonF(QRectF(0, 0, *_ENV_IMG)))


def envelope_bounds():
    """Scene area the letter, its shadow and its hover lift can cover."""
    return envelope_polygon(1.0).boundingRect().united(envelope_polygon().boundingRect()).adjusted(-10, -10, 16, 16)


def envelope_contains(pt):
    return envelope_polygon().containsPoint(pt, Qt.FillRule.OddEvenFill)


def _envelope_face():
    """The back of a sealed letter: cream paper, the flap, and a red wax seal."""
    iw, ih = _ENV_IMG
    img = QImage(iw, ih, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r = QRectF(1, 1, iw - 2, ih - 2)
    g = QLinearGradient(r.topLeft(), r.bottomRight())
    g.setColorAt(0, QColor(240, 231, 206))
    g.setColorAt(1, QColor(204, 190, 158))
    p.setPen(QPen(QColor(120, 104, 80), 3.6))
    p.setBrush(g)
    p.drawRect(r)
    flap = QPolygonF([r.topLeft(), r.topRight(), QPointF(r.center().x(), r.top() + r.height() * 0.55)])
    p.setBrush(QColor(226, 214, 184))
    p.drawPolygon(flap)
    p.setPen(QPen(QColor(120, 104, 80, 130), 3.6))
    p.drawLine(r.bottomLeft(), QPointF(r.center().x(), r.top() + r.height() * 0.5))
    p.drawLine(r.bottomRight(), QPointF(r.center().x(), r.top() + r.height() * 0.5))
    seal = QPointF(r.center().x(), r.top() + r.height() * 0.55)
    sr = r.height() * 0.15
    sg = QRadialGradient(seal - QPointF(sr * 0.25, sr * 0.25), sr * 1.2)
    sg.setColorAt(0, QColor(220, 60, 50))
    sg.setColorAt(1, QColor(110, 12, 8))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(sg)
    p.drawEllipse(seal, sr, sr * 0.92)
    p.setPen(QPen(QColor(255, 160, 140, 120), 3))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(seal, sr * 0.58, sr * 0.54)
    p.end()
    return img


def paint_envelope(p, hover):
    """A sealed letter lying in front of the inkwell; it lifts a little under the pointer."""
    global _env_image
    if _env_image is None:
        _env_image = _envelope_face()
    poly = envelope_polygon(hover)
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    p.setPen(Qt.PenStyle.NoPen)
    for i, a in enumerate((90, 40)):  # its shadow on the desk, longer when lifted
        d = QPointF(3 + 4 * hover + i * 2, 4 + 6 * hover + i * 2)
        p.setBrush(QColor(0, 0, 0, a))
        p.drawPolygon(QPolygonF([q + d for q in envelope_polygon()]))
    p.setTransform(envelope_transform(hover), True)
    p.drawImage(QRectF(0, 0, *_ENV_IMG), _env_image)
    p.restore()
    if hover > 0:
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(255, 214, 140, int(160 * hover)), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPolygon(poly)
        p.restore()
