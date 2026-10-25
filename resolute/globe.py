"""A small antique desk globe that spins on hover."""

import math

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF, QRadialGradient)

TILT = math.radians(23.5)
FRAMES = 240

# Coarse coastlines as (lon, lat) polygons. Good enough for a 60px globe.
LAND = [
    # North America
    [(-168, 66), (-162, 70), (-140, 70), (-125, 70), (-95, 72), (-80, 73), (-65, 62), (-60, 55),
     (-55, 50), (-66, 45), (-70, 42), (-76, 35), (-81, 31), (-80, 25), (-82, 27), (-85, 30),
     (-90, 29), (-97, 27), (-97, 22), (-92, 18), (-87, 21), (-88, 15), (-83, 10), (-78, 8),
     (-80, 7), (-85, 10), (-92, 14), (-105, 20), (-110, 24), (-115, 30), (-117, 33), (-121, 35),
     (-124, 40), (-124, 47), (-130, 55), (-140, 60), (-150, 60), (-158, 57), (-165, 60)],
    [(-120, 74), (-80, 74), (-70, 80), (-90, 82), (-120, 77)],
    [(-80, 73), (-65, 67), (-62, 66), (-75, 63), (-80, 70)],
    # Greenland, Iceland
    [(-73, 78), (-60, 82), (-30, 83), (-20, 80), (-20, 70), (-40, 64), (-50, 62), (-55, 68), (-60, 75)],
    [(-24, 64), (-14, 64), (-14, 66), (-22, 66)],
    # South America
    [(-80, 8), (-75, 11), (-62, 11), (-50, 2), (-35, -5), (-38, -13), (-40, -22), (-48, -27),
     (-58, -35), (-62, -40), (-66, -46), (-68, -54), (-72, -50), (-74, -40), (-71, -30),
     (-70, -18), (-76, -14), (-81, -5), (-80, 0), (-78, 5)],
    # Eurasia
    [(-10, 36), (-9, 43), (-2, 44), (-5, 48), (2, 51), (8, 54), (10, 57), (5, 60), (5, 62),
     (15, 69), (25, 71), (40, 68), (45, 68), (60, 70), (70, 73), (80, 73), (100, 77), (115, 74),
     (140, 72), (160, 70), (180, 68), (180, 65), (170, 60), (163, 58), (156, 51), (160, 60),
     (150, 59), (140, 55), (135, 44), (130, 42), (127, 38), (126, 35), (121, 40), (118, 38),
     (122, 31), (120, 26), (110, 21), (108, 16), (109, 12), (105, 9), (100, 13), (100, 7),
     (104, 1), (100, 3), (98, 8), (98, 16), (92, 22), (88, 22), (80, 15), (77, 8), (73, 17),
     (72, 21), (67, 24), (57, 25), (56, 27), (50, 30), (48, 29), (55, 25), (59, 22), (56, 18),
     (52, 16), (44, 12), (42, 16), (35, 28), (34, 31), (36, 36), (30, 36), (27, 37), (26, 40),
     (23, 40), (22, 37), (20, 40), (19, 42), (14, 45), (12, 44), (16, 40), (16, 38), (12, 38),
     (15, 41), (10, 44), (3, 43), (0, 39), (-5, 36)],
    [(-180, 68), (-170, 66), (-180, 64)],
    # Britain
    [(-6, 50), (2, 51), (0, 53), (-3, 56), (-5, 58), (-6, 55), (-5, 52)],
    # Africa, Madagascar
    [(-17, 21), (-17, 15), (-15, 11), (-8, 4), (5, 5), (9, 4), (10, -2), (13, -12), (12, -18),
     (15, -27), (18, -34), (25, -34), (32, -29), (35, -24), (40, -15), (40, -10), (40, -3),
     (51, 11), (44, 11), (38, 18), (33, 30), (25, 32), (20, 31), (10, 33), (10, 37), (0, 36),
     (-6, 36), (-10, 30)],
    [(44, -25), (47, -25), (50, -15), (49, -12), (44, -17)],
    # Australia, New Zealand, Japan, islands of SE Asia
    [(114, -22), (114, -34), (118, -35), (130, -32), (138, -35), (146, -39), (150, -37),
     (153, -28), (145, -15), (142, -11), (136, -12), (130, -12), (126, -14), (122, -18)],
    [(172, -35), (178, -38), (174, -41), (167, -46)],
    [(130, 31), (135, 34), (140, 36), (142, 41), (141, 45), (140, 40), (135, 35), (130, 33)],
    [(109, 1), (117, 7), (119, 0), (116, -4), (110, -3)],
    [(95, 5), (98, 4), (106, -6), (103, -5)],
    [(131, -1), (141, -3), (150, -10), (141, -9)],
    # Antarctica
    [(-180, -90), (180, -90), (180, -70), (60, -67), (0, -70), (-58, -63), (-75, -72), (-180, -75)],
]


def _land_mask(w=720, h=360):
    img = QImage(w, h, QImage.Format.Format_Grayscale8)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255))
    for poly in LAND:
        p.drawPolygon(QPolygonF([QPointF((lon + 180) / 360 * w, (90 - lat) / 180 * h) for lon, lat in poly]))
    p.end()
    ptr = img.constBits()
    ptr.setsize(img.bytesPerLine() * h)
    arr = np.frombuffer(ptr, np.uint8).reshape(h, img.bytesPerLine())[:, :w]
    return arr.astype(float) / 255.0


class Globe:
    def __init__(self, center, radius):
        self.cx, self.cy = center
        self.r = radius
        self.frame = 0.0
        self.speed = 0.3  # frames per tick when idle
        self.hover = False
        self._frames = []
        self._px = 0

    def build(self, scale):
        """Pre-render every rotation frame at device resolution."""
        px = max(16, int(self.r * 2 * scale))
        if px == self._px:
            return
        self._px = px
        mask = _land_mask()
        mh, mw = mask.shape
        coords = (np.arange(px) + 0.5) / px * 2 - 1
        x, y = np.meshgrid(coords, -coords)
        d2 = x * x + y * y
        inside = d2 <= 1.0
        z = np.sqrt(np.clip(1 - d2, 0, 1))
        # undo the axial tilt so we can read latitude straight off the rotated y
        xr = x * math.cos(TILT) + y * math.sin(TILT)
        yr = -x * math.sin(TILT) + y * math.cos(TILT)
        lat = np.arcsin(np.clip(yr, -1, 1))
        base_lon = np.arctan2(xr, z)
        light = np.clip(-0.45 * x + 0.55 * y + 0.7 * z, 0, 1) * 0.75 + 0.3
        rim = np.clip((1 - z) * 1.6, 0, 1)
        ocean = np.array((74, 118, 122), float)
        land = np.array((214, 190, 136), float)
        line = np.array((60, 50, 36), float)
        my = np.clip(((math.pi / 2 - lat) / math.pi * mh).astype(int), 0, mh - 1)
        self._frames = []
        for i in range(FRAMES):
            lon = base_lon + i / FRAMES * 2 * math.pi
            lon = (lon + math.pi) % (2 * math.pi) - math.pi
            mx = np.clip(((lon + math.pi) / (2 * math.pi) * mw).astype(int), 0, mw - 1)
            m = mask[my, mx][..., None]
            rgb = ocean * (1 - m) + land * m
            # graticule every 30 degrees
            grat = ((np.abs((np.degrees(lat) + 90) % 30 - 15) > 14.2) |
                    (np.abs((np.degrees(lon) + 180) % 30 - 15) > 14.2))[..., None]
            rgb = rgb * (1 - grat * 0.35) + line * grat * 0.35
            rgb = rgb * light[..., None]
            rgb = rgb * (1 - rim[..., None] * 0.35)
            rgba = np.zeros((px, px, 4), np.uint8)
            rgba[..., :3] = np.clip(rgb, 0, 255)
            rgba[..., 3] = inside * 255
            img = QImage(rgba.tobytes(), px, px, 4 * px, QImage.Format.Format_RGBA8888).copy()
            self._frames.append(img)

    def contains(self, pt):
        return math.hypot(pt.x() - self.cx, pt.y() - self.cy) <= self.r * 1.25 or \
            QRectF(self.cx - self.r * 0.8, self.cy, self.r * 1.6, self.r * 1.9).contains(pt)

    def step(self):
        target = 1.8 if self.hover else 0.3  # twice the frames of old, so twice as many per tick for the same pace
        self.speed += (target - self.speed) * 0.08
        self.frame = (self.frame + self.speed) % FRAMES
        return True

    def paint_stand(self, p: QPainter):
        """Base and pillar; drawn into the static layer."""
        cx, cy, r = self.cx, self.cy, self.r
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        base_y = cy + r * 1.85
        # shadow on the desk
        sh = QRadialGradient(QPointF(cx + 6, base_y + 4), r * 1.0)
        sh.setColorAt(0, QColor(0, 0, 0, 120))
        sh.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(sh)
        p.drawEllipse(QPointF(cx + 6, base_y + 4), r * 1.1, r * 0.32)
        # turned wooden base
        for (w, h, dy, top, bot) in ((0.78, 0.22, 0.0, (110, 50, 24), (60, 24, 10)),
                                     (0.58, 0.16, -0.12, (150, 74, 38), (90, 40, 18))):
            g = QLinearGradient(cx - r * w, 0, cx + r * w, 0)
            g.setColorAt(0, QColor(*bot))
            g.setColorAt(0.35, QColor(*top))
            g.setColorAt(1, QColor(*bot))
            p.setBrush(g)
            p.drawEllipse(QPointF(cx, base_y + dy * r), r * w, r * h)
        # brass pillar
        g = QLinearGradient(cx - r * 0.08, 0, cx + r * 0.08, 0)
        g.setColorAt(0, QColor(120, 90, 30))
        g.setColorAt(0.4, QColor(240, 210, 120))
        g.setColorAt(1, QColor(110, 80, 25))
        p.setBrush(g)
        p.drawRect(QRectF(cx - r * 0.07, cy + r * 0.95, r * 0.14, base_y - cy - r * 1.05))
        p.restore()

    def paint_dynamic(self, p: QPainter):
        cx, cy, r = self.cx, self.cy, self.r
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._frames:
            # cross-fade into the next frame so the turn moves a little every tick rather than in steps
            i = int(self.frame)
            rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
            p.drawImage(rect, self._frames[i % FRAMES])
            p.setOpacity(self.frame - i)
            p.drawImage(rect, self._frames[(i + 1) % FRAMES])
            p.setOpacity(1.0)
        # varnish highlight
        hl = QRadialGradient(QPointF(cx - r * 0.4, cy - r * 0.45), r * 0.7)
        hl.setColorAt(0, QColor(255, 250, 230, 110 if self.hover else 80))
        hl.setColorAt(1, QColor(255, 250, 230, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(hl)
        p.drawEllipse(QPointF(cx, cy), r, r)
        # front half of the meridian ring, tilted with the axis
        p.translate(cx, cy)
        p.rotate(-math.degrees(TILT))
        p.translate(-cx, -cy)
        ring = QRectF(cx - r * 1.14, cy - r * 1.14, r * 2.28, r * 2.28)
        g = QLinearGradient(cx - r, cy - r, cx + r, cy + r)
        g.setColorAt(0, QColor(250, 222, 140))
        g.setColorAt(1, QColor(140, 100, 35))
        p.setPen(QPen(g, r * 0.07, cap=Qt.PenCapStyle.FlatCap))
        p.drawArc(ring, -90 * 16, 180 * 16)
        # axis pins
        p.setPen(QPen(QColor(200, 170, 90), r * 0.05))
        p.drawLine(QPointF(cx, cy - r * 1.22), QPointF(cx, cy - r * 1.0))
        p.drawLine(QPointF(cx, cy + r * 1.0), QPointF(cx, cy + r * 1.22))
        p.restore()
        # cradle joining ring and pillar
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.moveTo(cx - r * 0.25, cy + r * 1.18)
        path.quadTo(cx, cy + r * 0.95, cx + r * 0.25, cy + r * 1.18)
        p.setPen(QPen(QColor(170, 130, 50), r * 0.06))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.restore()
