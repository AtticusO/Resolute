"""The sketch pad on the left of the writing pad, with a fountain pen lying across it.

Click it and the pad comes up off the leather to stand in the middle of the desk, facing you as
if it were in your hand. The pen follows the pointer: the left button draws, the right one rubs
out, Ctrl+Z takes back the last stroke. The page is saved as a PNG picture.
"""

import math
import time
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QObject, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QFontMetrics, QImage, QLinearGradient, QPainter, QPainterPath, QPen,
                         QPolygonF, QTransform)

from . import config, desk
from .textures import _value_noise

# The pad in its own pixels: grey board behind, cartridge paper on top, wire binding along the top.
PAD_W, PAD_H = 1032, 1290
PAPER = QRectF(16, 24, 1000, 1250)
HOLE_Y = PAPER.top() + 34  # the row of binding holes
COIL_STEP = 30.0
BINDING = QRectF(0, -24, PAD_W, HOLE_Y + 40)  # where the coil and holes are drawn

# Lying on the leather (flat desk-top coordinates of desk.SURFACE_WORLD), left of the note paper.
FLAT_CENTER = QPointF(714, 716)
FLAT_W = 236.0
FLAT_ANGLE = 5.0
THICK = 7.0  # height of the stack of sheets, in scene pixels
PEN_NIB_WORLD, PEN_TAIL_WORLD = QPointF(632, 640), QPointF(812, 818)

# Held up in front of you, in scene pixels.
HELD_CENTER = QPointF(960, 548)
HELD_H = 720.0
HELD_ANGLE = -1.5
HELD_PEN = QPointF(0.5, 0.866) * 236  # from the nib to the end of the pen, which goes down to your hand

INK = QColor(22, 26, 58)
INK_W = 5.0  # in page pixels
RUB_W = 46.0

CLOSE = QRectF(PAPER.right() - 80, PAPER.top() + 66, 60, 60)
NEW_PAGE = QRectF(PAPER.right() - 230, PAPER.bottom() - 66, 206, 50)
STATUS = QRectF(PAPER.left() + 26, PAPER.bottom() - 66, PAPER.width() - 280, 50)
HINT = "Left button draws, right rubs out, Ctrl+Z undoes, Ctrl+X clears"


def _ease(t):
    return 1 - (1 - t) ** 3


def _paper():
    """White cartridge paper with a faint tooth, at half the page's resolution."""
    w, h = int(PAPER.width()) // 2, int(PAPER.height()) // 2
    rng = np.random.default_rng(5)
    n = rng.random((h, w)) * 0.6 + _value_noise(h, w, 10, 8, rng) * 0.4  # fine tooth over a gentle cloud
    rgb = np.clip(np.array((250, 247, 238), float) * (1 - 0.05 * n)[..., None], 0, 255).astype(np.uint8)
    img = QImage(np.ascontiguousarray(rgb).data, w, h, 3 * w, QImage.Format.Format_RGB888)
    return img.convertToFormat(QImage.Format.Format_RGB32)


def _shadow():
    """A soft-edged shadow, small: it is stretched over the pad, which blurs it further."""
    w, h, fade = 160, 200, 26
    y, x = np.mgrid[0:h, 0:w]
    d = np.minimum(np.minimum(x, w - 1 - x), np.minimum(y, h - 1 - y)) / fade
    a = np.clip(d, 0, 1)
    a = (a * a * (3 - 2 * a) * 255).astype(np.uint8)
    argb = np.zeros((h, w, 4), np.uint8)
    argb[..., 3] = a  # black, premultiplied: only alpha is set
    return QImage(np.ascontiguousarray(argb).data, w, h, 4 * w, QImage.Format.Format_ARGB32_Premultiplied).copy()


def _corners(t: QTransform):
    return [t.map(QPointF(x, y)) for x, y in ((0, 0), (PAD_W, 0), (PAD_W, PAD_H), (0, PAD_H))]


def _flat_corners():
    t = QTransform()
    t.translate(FLAT_CENTER.x(), FLAT_CENTER.y())
    t.rotate(FLAT_ANGLE)
    t.scale(FLAT_W / PAD_W, FLAT_W / PAD_W)
    t.translate(-PAD_W / 2, -PAD_H / 2)
    return _corners(t * desk.surface_transform())


def _held_corners():
    t = QTransform()
    t.translate(HELD_CENTER.x(), HELD_CENTER.y())
    t.rotate(HELD_ANGLE)
    t.scale(HELD_H / PAD_H, HELD_H / PAD_H)
    t.translate(-PAD_W / 2, -PAD_H / 2)
    return _corners(t)


def _mid(a, b):
    return (a + b) / 2


def paint_pen(p: QPainter, nib: QPointF, tail: QPointF, width, shadow=QPointF(7, 5)):
    """A black lacquered fountain pen with gold fittings, from its nib to the end of its cap."""
    d = tail - nib
    L = math.hypot(d.x(), d.y())
    w = width / 2
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    for i, a in enumerate((60, 34, 16)):
        p.save()
        p.translate(nib + shadow)
        p.rotate(math.degrees(math.atan2(d.y(), d.x())))
        p.setBrush(QColor(0, 0, 0, a))
        grow = i * w * 0.5
        p.drawRoundedRect(QRectF(L * 0.08 - grow, -w - grow, L * 0.92 + 2 * grow, 2 * w + 2 * grow), w + grow, w + grow)
        p.restore()
    p.translate(nib)
    p.rotate(math.degrees(math.atan2(d.y(), d.x())))

    def lacquer(r):
        g = QLinearGradient(0, -r, 0, r)
        g.setColorAt(0, QColor(70, 70, 78))
        g.setColorAt(0.28, QColor(150, 150, 160))
        g.setColorAt(0.42, QColor(30, 30, 36))
        g.setColorAt(1, QColor(6, 6, 8))
        return g

    def gold(r):
        g = QLinearGradient(0, -r, 0, r)
        g.setColorAt(0, desk.BRASS_DARK)
        g.setColorAt(0.3, desk.BRASS_LIGHT)
        g.setColorAt(1, desk.BRASS_DARK)
        return g

    # nib: a gold point with its slit
    nib_path = QPainterPath()
    nib_path.moveTo(0, 0)
    nib_path.cubicTo(L * 0.04, -w * 0.25, L * 0.08, -w * 0.62, L * 0.12, -w * 0.6)
    nib_path.lineTo(L * 0.12, w * 0.6)
    nib_path.cubicTo(L * 0.08, w * 0.62, L * 0.04, w * 0.25, 0, 0)
    p.setBrush(gold(w * 0.6))
    p.drawPath(nib_path)
    p.setPen(QPen(QColor(60, 40, 10, 200), max(0.6, w * 0.08)))
    p.drawLine(QPointF(L * 0.005, 0), QPointF(L * 0.07, 0))
    p.setPen(Qt.PenStyle.NoPen)
    # grip section, narrowing towards the nib
    grip = QPainterPath()
    grip.moveTo(L * 0.11, -w * 0.62)
    grip.lineTo(L * 0.25, -w * 0.86)
    grip.lineTo(L * 0.25, w * 0.86)
    grip.lineTo(L * 0.11, w * 0.62)
    grip.closeSubpath()
    p.setBrush(lacquer(w * 0.86))
    p.drawPath(grip)
    # barrel and cap, with gold rings
    p.setBrush(lacquer(w))
    p.drawRect(QRectF(L * 0.26, -w * 0.94, L * 0.37, w * 1.88))
    p.drawRoundedRect(QRectF(L * 0.645, -w, L * 0.355, 2 * w), w * 0.9, w * 0.9)
    p.setBrush(gold(w))
    p.drawRect(QRectF(L * 0.245, -w * 0.9, L * 0.018, w * 1.8))
    p.drawRect(QRectF(L * 0.628, -w * 1.02, L * 0.024, w * 2.04))
    # the clip along the top of the cap
    p.setBrush(gold(w * 0.3))
    p.drawRoundedRect(QRectF(L * 0.70, -w * 0.98, L * 0.27, w * 0.36), w * 0.15, w * 0.15)
    p.drawEllipse(QPointF(L * 0.71, -w * 0.8), w * 0.24, w * 0.24)
    p.restore()


def _pen_rect(nib, tail, width):
    return QRectF(nib, tail).normalized().adjusted(-width - 14, -width - 14, width + 22, width + 22)


class Sketch(QObject):
    changed = pyqtSignal(QRectF)  # this part of the scene needs repainting

    def __init__(self, notify):
        super().__init__()
        self.notify = notify
        self.path = Path(config.get("sketch_file")).expanduser()
        self.held = False  # up in your hand
        self.t = 0.0  # 0 = lying on the leather, 1 = held up
        self.hover = False
        self.pen_at = None  # where the pen's nib is while you hold the pad
        self._texture = _paper()
        self._rub = QBrush(self._texture)
        self._rub.setTransform(QTransform.fromScale(2, 2))
        self._shadow = _shadow()
        self._binding = self._render_binding()
        self.page = self._blank()
        self._drawn = False  # something is on the page that a new page should keep
        try:
            if self.path.exists():
                img = QImage(str(self.path))
                if not img.isNull():
                    self.page = img.scaled(int(PAPER.width()), int(PAPER.height())).convertToFormat(QImage.Format.Format_RGB32)
                    self._drawn = True
        except OSError:
            pass
        self._base = None  # the page as it was when picked up; strokes since then can be undone
        self._base_drawn = False
        self._strokes = []  # (erase, points) for each stroke, or (None, None) where the page was cleared
        self._stroke = None
        self._status = HINT
        self._flat = _flat_corners()
        self._up = _held_corners()
        self._last = self.bounds()
        self._save_timer = QTimer(self, singleShot=True, interval=800, timeout=self.save)
        self._anim = QTimer(self, interval=16, timeout=self._step)

    def _blank(self):
        img = QImage(int(PAPER.width()), int(PAPER.height()), QImage.Format.Format_RGB32)
        p = QPainter(img)
        p.fillRect(QRectF(img.rect()), self._rub)
        p.end()
        return img

    # -- geometry ------------------------------------------------------------
    def corners(self):
        e = _ease(self.t)
        return [f + (u - f) * e for f, u in zip(self._flat, self._up)]

    def transform(self):
        """Pad pixels -> scene."""
        out = QTransform()
        QTransform.quadToQuad(QPolygonF(QRectF(0, 0, PAD_W, PAD_H)), QPolygonF(self.corners()), out)
        return out

    def _pen_ends(self):
        if self.t < 0.34:  # lying on the pad, until it is picked up
            t = desk.surface_transform()
            return t.map(PEN_NIB_WORLD), t.map(PEN_TAIL_WORLD), 11.0
        if self.held and self.t > 0.98 and self.pen_at is not None:
            return self.pen_at, self.pen_at + HELD_PEN, 17.0
        return None

    def bounds(self):
        top = QPolygonF(self.corners())
        r = top.boundingRect().adjusted(-30, -30, 60, 60 + THICK)
        pen = self._pen_ends()
        return r.united(_pen_rect(*pen)) if pen else r

    def covers(self, rect):
        """Whether rect lies wholly on the pad held up in front of everything."""
        if not self.held or self.t != 1:
            return False
        pad = QPolygonF(self.corners())
        return all(pad.containsPoint(c, Qt.FillRule.OddEvenFill)
                   for c in (rect.topLeft(), rect.topRight(), rect.bottomLeft(), rect.bottomRight()))

    def tag_point(self):
        c = self._flat
        return _mid(c[0], c[1])

    def contains(self, pt):
        """On the pad or its pen while they lie on the leather."""
        if self.t > 0 or self.held:
            return False
        top = QPolygonF(self._flat)
        base = QPolygonF([c + QPointF(0, THICK) for c in self._flat])
        if top.containsPoint(pt, Qt.FillRule.OddEvenFill) or base.containsPoint(pt, Qt.FillRule.OddEvenFill):
            return True
        nib, tail, w = self._pen_ends()
        d = tail - nib
        L = math.hypot(d.x(), d.y())
        q = pt - nib
        along = (q.x() * d.x() + q.y() * d.y()) / L
        across = abs(q.x() * d.y() - q.y() * d.x()) / L
        return 0 <= along <= L and across <= w

    def to_pad(self, pt):
        inv, ok = self.transform().inverted()
        return inv.map(pt) if ok else QPointF(-1, -1)

    def part_at(self, pt):
        """What of the held pad is under the pointer: 'close', 'new', 'page', 'pad', or None."""
        if not self.held:
            return None
        q = self.to_pad(pt)
        if not QRectF(0, 0, PAD_W, PAD_H).contains(q):
            return None
        if CLOSE.contains(q):
            return "close"
        if NEW_PAGE.contains(q):
            return "new"
        return "page" if PAPER.contains(q) else "pad"

    # -- picking it up and putting it down -------------------------------------
    def lift(self):
        if self.held:
            return
        self.held = True
        self._base = self.page.copy()
        self._base_drawn = self._drawn
        self._strokes = []
        self._status = HINT
        self._anim.start()

    def put_down(self):
        if not self.held:
            return
        self.end()
        if self._save_timer.isActive():
            self.save()
        self.point_at(None)
        self.held = False
        self._base = None  # undo only reaches back to when it was picked up
        self._strokes = []
        self._anim.start()

    def flush(self):
        if self._save_timer.isActive():
            self.save()

    def _step(self):
        target = 1.0 if self.held else 0.0
        self.t += (target - self.t) * 0.2
        if abs(target - self.t) < 0.004:
            self.t = target
            self._anim.stop()
        self._repaint()

    def _repaint(self, rect=None):
        """Repaint rect, or everything the pad covered last time and covers now."""
        if rect is None:
            now = self.bounds()
            rect, self._last = self._last.united(now), now
        self.changed.emit(rect)

    def set_hover(self, on):
        if on != self.hover:
            self.hover = on
            self._repaint()

    def point_at(self, pt):
        """Move the pen in your hand to pt, or take it off the page (None)."""
        if pt == self.pen_at:
            return
        old = self._pen_ends() if self.pen_at is not None else None
        self.pen_at = pt if self.held else None
        new = self._pen_ends() if self.pen_at is not None else None
        rects = [_pen_rect(*ends) for ends in (old, new) if ends]
        if rects:
            self._repaint(rects[0].united(rects[-1]))

    # -- drawing ---------------------------------------------------------------
    def _to_page(self, pt):
        return self.to_pad(pt) - PAPER.topLeft()

    def _pen(self, erase):
        if erase:
            return QPen(self._rub, RUB_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        return QPen(INK, INK_W, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)

    @staticmethod
    def _piece(pts, k):
        """The part of a stroke that its point k completes: strokes are smoothed through the midpoints.
        k == len(pts) is the last bit, out to the final point."""
        path = QPainterPath()
        if k == len(pts):
            path.moveTo(_mid(pts[-2], pts[-1]) if len(pts) > 1 else pts[0])
            path.lineTo(pts[-1])
        elif k == 1:
            path.moveTo(pts[0])
            path.lineTo(_mid(pts[0], pts[1]))
        else:
            path.moveTo(_mid(pts[k - 2], pts[k - 1]))
            path.quadTo(pts[k - 1], _mid(pts[k - 1], pts[k]))
        return path

    def _draw(self, erase, paint_fn, area):
        p = QPainter(self.page)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(self._pen(erase))
        paint_fn(p)
        p.end()
        w = (RUB_W if erase else INK_W) / 2 + 3
        pad_rect = area.translated(PAPER.topLeft()).adjusted(-w, -w, w, w)
        self._repaint(self.transform().mapRect(pad_rect))

    def begin(self, pt, erase=False):
        q = self._to_page(pt)
        self._stroke = (erase, [q])
        self._draw(erase, lambda p: p.drawPoint(q), QRectF(q, q))

    def extend(self, pt):
        self.point_at(pt)
        if self._stroke is None:
            return
        erase, pts = self._stroke
        q = self._to_page(pt)
        if (q - pts[-1]).manhattanLength() < 1.5:
            return
        pts.append(q)
        piece = self._piece(pts, len(pts) - 1)
        self._draw(erase, lambda p: p.drawPath(piece), piece.boundingRect())

    def end(self):
        if self._stroke is None:
            return
        erase, pts = self._stroke
        self._stroke = None
        if len(pts) > 1:
            piece = self._piece(pts, len(pts))
            self._draw(erase, lambda p: p.drawPath(piece), piece.boundingRect())
        self._strokes.append((erase, pts))
        self._drawn = self._drawn or not erase
        self._save_timer.start()

    def undo(self):
        if not self._strokes or self._base is None:
            return
        self._strokes.pop()
        self.page = self._base.copy()
        p = QPainter(self.page)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._drawn = self._base_drawn
        for erase, pts in self._strokes:
            if pts is None:
                p.fillRect(QRectF(self.page.rect()), self._rub)
                self._drawn = False
                continue
            self._drawn = self._drawn or not erase
            p.setPen(self._pen(erase))
            p.drawPoint(pts[0])
            if len(pts) > 1:
                for k in range(1, len(pts) + 1):
                    p.drawPath(self._piece(pts, k))
        p.end()
        self._save_timer.start()
        self._repaint(self.bounds())

    def clear(self):
        """Rub out the whole page. Ctrl+Z brings it back, as far as an undo would."""
        self.end()
        p = QPainter(self.page)
        p.fillRect(QRectF(self.page.rect()), self._rub)
        p.end()
        self._strokes.append((None, None))
        self._drawn = False
        self._save_timer.start()
        self._repaint(self.bounds())

    def new_page(self):
        """Turn to a clean page. A page with a drawing on it is kept in a Sketches folder first."""
        self.end()
        self._save_timer.stop()
        if self._drawn:
            folder = self.path.parent / "Sketches"
            kept = folder / time.strftime("sketch-%Y-%m-%d-%H%M%S.png")
            try:
                folder.mkdir(parents=True, exist_ok=True)
                ok = self.page.save(str(kept), "PNG")
            except OSError:
                ok = False
            if not ok:
                self._status = f"Couldn't keep the old page in {self._shown(folder)}"
                self._repaint(self.bounds())
                return
            self.notify(f"The old page was kept in {self._shown(folder)}")
            try:
                self.path.unlink(missing_ok=True)  # a blank page isn't worth a file
            except OSError:
                pass
        self.page = self._blank()
        self._drawn = False
        self._base = self.page.copy() if self.held else None
        self._strokes = []
        self._status = HINT
        self._repaint(self.bounds())

    @staticmethod
    def _shown(path):
        home = str(Path.home())
        return "~" + str(path)[len(home):] if str(path).startswith(home) else str(path)

    def save(self):
        self._save_timer.stop()
        if not self._drawn:  # a blank page isn't worth a file
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                pass
            self._status = "Page cleared"
            self._repaint(self.bounds())
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            ok = self.page.save(str(self.path), "PNG")
        except OSError:
            ok = False
        self._status = ("Saved to " if ok else "Couldn't save ") + self._shown(self.path)
        self._repaint(self.bounds())

    # -- painting --------------------------------------------------------------
    def paint(self, p: QPainter):
        e = _ease(self.t)
        top = self.corners()
        tr = self.transform()
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setPen(Qt.PenStyle.NoPen)
        # shadow: tight on the leather, softer and further away once lifted
        p.save()
        p.setTransform(tr, True)
        p.setOpacity(0.75 - 0.25 * e)
        grow = 40 + 50 * e
        p.drawImage(QRectF(14 + 30 * e - grow, 16 + 34 * e - grow, PAD_W + 2 * grow, PAD_H + 2 * grow), self._shadow)
        p.restore()
        # the edges of the stack, which flatten away as it turns to face you
        thick = THICK * (1 - e)
        if thick > 0.3:
            base = [c + QPointF(0, thick) for c in top]
            for i in range(4):
                j = (i + 1) % 4
                g = QLinearGradient(top[i], base[i])
                g.setColorAt(0, QColor(236, 232, 222))
                g.setColorAt(0.7, QColor(206, 200, 188))
                g.setColorAt(0.72, QColor(46, 44, 42))
                g.setColorAt(1, QColor(30, 28, 26))
                p.setBrush(g)
                p.drawPolygon(QPolygonF([base[i], base[j], top[j], top[i]]))
        p.setTransform(tr, True)
        p.setBrush(QColor(54, 52, 49))  # the grey board behind the paper
        p.drawRect(QRectF(0, 0, PAD_W, PAD_H))
        p.drawImage(PAPER, self.page)
        p.setPen(QPen(QColor(0, 0, 0, 50), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(PAPER)
        p.drawImage(QPointF(BINDING.left(), BINDING.top()), self._binding)
        if self.held and self.t == 1:  # text is slow to draw in perspective, so it waits until the pad is up
            self._paint_controls(p)
        p.restore()
        pen = self._pen_ends()
        if pen:
            p.save()
            if 0 < self.t < 0.34:  # the pen lying on the pad fades as you pick it up
                p.setOpacity(1 - self.t * 3)
            lift = QPointF(0, -3) if self.hover and self.t == 0 else QPointF(0, 0)
            nib, tail, w = pen
            paint_pen(p, nib + lift, tail + lift, w, QPointF(7, 5) - lift * 1.5)
            p.restore()

    @staticmethod
    def _render_binding():
        """Holes punched along the top, and the wire coil through them over the top edge, drawn once
        (curves are slow to draw in perspective)."""
        img = QImage(int(BINDING.width()), int(BINDING.height()), QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(-BINDING.topLeft())
        x = PAPER.left() + 22
        p.setPen(Qt.PenStyle.NoPen)
        while x < PAPER.right() - 14:
            p.setBrush(QColor(30, 28, 26))
            p.drawEllipse(QPointF(x, HOLE_Y), 7, 6)
            back = QPainterPath()
            back.moveTo(x + 9, -10)
            back.cubicTo(x + 16, -6, x + 17, 8, x + 15, 14)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(60, 62, 68), 4, cap=Qt.PenCapStyle.RoundCap))
            p.drawPath(back)
            front = QPainterPath()
            front.moveTo(x, HOLE_Y + 2)
            front.cubicTo(x - 3, HOLE_Y - 30, x + 1, -14, x + 9, -10)
            p.setPen(QPen(QColor(40, 42, 46), 7, cap=Qt.PenCapStyle.RoundCap))
            p.drawPath(front)
            p.setPen(QPen(QColor(196, 200, 208), 3.5, cap=Qt.PenCapStyle.RoundCap))
            p.drawPath(front)
            p.setPen(Qt.PenStyle.NoPen)
            x += COIL_STEP
        p.end()
        return img

    def _paint_controls(self, p):
        p.setPen(QColor(110, 96, 80))
        font = QFont("C059")
        font.setPixelSize(50)
        p.setFont(font)
        p.drawText(CLOSE, Qt.AlignmentFlag.AlignCenter, "×")
        font.setPixelSize(30)
        font.setItalic(True)
        p.setFont(font)
        p.drawText(NEW_PAGE, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, "New page")
        font.setPixelSize(25)
        p.setFont(font)
        p.setPen(QColor(120, 106, 90, 200))
        status = QFontMetrics(font).elidedText(self._status, Qt.TextElideMode.ElideLeft, int(STATUS.width()))
        p.drawText(STATUS, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, status)
