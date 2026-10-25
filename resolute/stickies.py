"""A pad of sticky notes in front of the lamp, and the notes peeled off it.

Drag from the pad and a note comes away in your hand; let go and it is stuck down where you
dropped it: flat on the desk top (in the desk's perspective) or upright on the organiser.
Double-click a note to write on it. Like the quill's page, the writing is done by an off-screen
QPlainTextEdit that the desk forwards keys and clicks to and draws onto the note.
"""

import json
import math
import random

import numpy as np
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QImage, QLinearGradient, QMouseEvent, QPainter,
                         QPainterPath, QPen, QPolygonF, QRadialGradient, QTransform)
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from . import config, desk
from .textures import _value_noise

SAVED = config.CONFIG_PATH.parent / "stickies.json"

# The pad, in the flat desk-top coordinates of desk.SURFACE_WORLD: just in front of the lamp's foot.
PAD_CENTER = QPointF(345, 762)
PAD_ANGLE = -7.0
NOTE = 150.0  # side of a note on the desk top, in desk-top units
THICKNESS = 15.0  # height of the stack, in scene pixels
WALL_SIZE = 104.0  # side of a note stuck on the organiser, in scene pixels (it is further away)
WALL_LOW = 350.0  # notes on the organiser stay above the radio and gauge stand standing in front of it
BACK_ROW = 500.0  # notes on the desk top stay in front of the objects along the back
UPRIGHT = 0.3  # as for the quill's page: tip the top edge a little towards the viewer so writing reads
IMG = 300  # resolution a note is drawn at before it is laid onto the desk
TEXT_RECT = QRectF(24, 30, IMG - 48, IMG - 52)
FONT_SIZES = (64, 56, 48, 41, 35, 30, 26, 22)
INK = QColor(28, 34, 72)

YELLOW = (252, 232, 112)

_surface = None


def _surface_t():
    global _surface
    if _surface is None:
        _surface = (desk.surface_transform(), desk.surface_transform().inverted()[0])
    return _surface


def _paper():
    """Canary paper with faint fibres, a slightly glossier adhesive strip and a lifting bottom edge."""
    rng = np.random.default_rng(7)
    n = _value_noise(IMG, IMG, 60, 60, rng) * 0.5 + _value_noise(IMG, IMG, 8, 8, rng) * 0.5
    shade = (1 - 0.06 * n)[..., None]
    rgb = np.clip(np.array(YELLOW, float) * shade, 0, 255).astype(np.uint8)
    img = QImage(np.ascontiguousarray(rgb).data, IMG, IMG, 3 * IMG, QImage.Format.Format_RGB888)
    img = img.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
    p = QPainter(img)
    g = QLinearGradient(0, 0, 0, 44)
    g.setColorAt(0, QColor(255, 255, 255, 34))
    g.setColorAt(1, QColor(255, 255, 255, 0))
    p.fillRect(QRectF(0, 0, IMG, 44), g)
    g = QLinearGradient(0, IMG * 0.7, 0, IMG)  # the free end curls up off the surface a little
    g.setColorAt(0, QColor(0, 0, 0, 0))
    g.setColorAt(1, QColor(120, 80, 0, 40))
    p.fillRect(QRectF(0, IMG * 0.7, IMG, IMG * 0.3), g)
    p.end()
    return img


def _fit_font(text):
    font = QFont("Z003")
    font.setBold(True)
    for size in FONT_SIZES:
        font.setPixelSize(size)
        h = QFontMetrics(font).boundingRect(TEXT_RECT.toRect(), Qt.TextFlag.TextWordWrap, text or " ").height()
        if h <= TEXT_RECT.height():
            break
    return font


def _scale_at(x, y):
    """Scene size of a note held at this point: smaller towards the back of the desk."""
    if y <= desk.SURFACE_BACK_Y:
        return WALL_SIZE
    t, inv = _surface_t()
    w = inv.map(QPointF(x, min(y, desk.SURFACE_FRONT_Y)))
    a, b = t.map(w - QPointF(NOTE / 2, 0)), t.map(w + QPointF(NOTE / 2, 0))
    return max(WALL_SIZE, b.x() - a.x())


class Sticky:
    def __init__(self, mode, x, y, angle, text=""):
        self.mode = mode  # "desk": (x, y) in desk-top units; "wall": scene pixels on the organiser
        self.x, self.y = x, y
        self.angle = angle
        self.text = text
        self.image = None

    def transform(self):
        """Note pixels -> scene."""
        if self.mode == "wall":
            t = QTransform()
            t.translate(self.x, self.y)
            t.rotate(self.angle)
            t.scale(WALL_SIZE / IMG, WALL_SIZE / IMG)
            t.translate(-IMG / 2, -IMG / 2)
            return t
        t = QTransform()
        t.translate(self.x, self.y)
        t.rotate(self.angle)
        t.translate(-NOTE / 2, -NOTE / 2)
        t.scale(NOTE / IMG, NOTE / IMG)
        flat = (t * _surface_t()[0]).map(QPolygonF(QRectF(0, 0, IMG, IMG)))
        tl, tr, br, bl = flat[0], flat[1], flat[2], flat[3]
        height = math.hypot(br.x() - bl.x(), br.y() - bl.y()) * 0.8
        up_l, up_r = QPointF(bl.x(), bl.y() - height), QPointF(br.x(), br.y() - height)
        quad = QPolygonF([tl + (up_l - tl) * UPRIGHT, tr + (up_r - tr) * UPRIGHT, br, bl])
        out = QTransform()
        QTransform.quadToQuad(QPolygonF(QRectF(0, 0, IMG, IMG)), quad, out)
        return out

    def polygon(self):
        return self.transform().map(QPolygonF(QRectF(0, 0, IMG, IMG)))

    def bounds(self):
        return self.polygon().boundingRect().adjusted(-14, -14, 26, 30)

    def contains(self, pt):
        return self.polygon().containsPoint(pt, Qt.FillRule.OddEvenFill)

    def to_note(self, scene_pt):
        inv, ok = self.transform().inverted()
        return inv.map(scene_pt) if ok else QPointF(-1, -1)

    def center(self):
        return self.polygon().boundingRect().center()


class Held:
    """A note in the hand, facing the viewer, while it is dragged."""

    def __init__(self, sticky, pos):
        self.sticky = sticky
        self.pos = pos

    def transform(self):
        size = _scale_at(self.pos.x(), self.pos.y()) * 1.05  # a little nearer: it is lifted off the desk
        t = QTransform()
        t.translate(self.pos.x(), self.pos.y())
        t.rotate(self.sticky.angle + 3)
        t.scale(size / IMG, size / IMG)
        t.translate(-IMG / 2, -IMG / 2)
        return t

    def bounds(self):
        return self.transform().map(QPolygonF(QRectF(0, 0, IMG, IMG))).boundingRect().adjusted(-20, -20, 40, 50)


# --- the pad ------------------------------------------------------------------------------

def _pad_faces():
    t = _surface_t()[0]
    m = QTransform()
    m.translate(PAD_CENTER.x(), PAD_CENTER.y())
    m.rotate(PAD_ANGLE)
    corners = [m.map(QPointF(x, y)) for x, y in ((-NOTE / 2, -NOTE / 2), (NOTE / 2, -NOTE / 2),
                                                  (NOTE / 2, NOTE / 2), (-NOTE / 2, NOTE / 2))]
    base = [t.map(c) for c in corners]
    top = [b - QPointF(0, THICKNESS) for b in base]
    return base, top


def pad_bounds():
    base, top = _pad_faces()
    return QPolygonF(base + top).boundingRect().adjusted(-30, -40, 40, 30)


def pad_contains(pt):
    base, top = _pad_faces()
    path = QPainterPath()
    path.addPolygon(QPolygonF(top))
    path.addPolygon(QPolygonF(base))
    path.setFillRule(Qt.FillRule.WindingFill)
    for i in range(4):  # the sides of the stack
        j = (i + 1) % 4
        path.addPolygon(QPolygonF([base[i], base[j], top[j], top[i]]))
    return path.contains(pt)


def pad_tag_point():
    base, top = _pad_faces()
    return QPolygonF(top).boundingRect().center()


def paint_pad(p: QPainter, hover=0.0):
    base, top = _pad_faces()
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    # contact shadow, thrown away from the lamp
    c = QPolygonF(base).boundingRect().center()
    g = QRadialGradient(c + QPointF(10, 4), QPolygonF(base).boundingRect().width() * 0.75)
    g.setColorAt(0, QColor(0, 0, 0, 150))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.setBrush(g)
    p.drawPolygon(QPolygonF([b + QPointF(8, 4) for b in base]))
    p.drawPolygon(QPolygonF([b + QPointF(4, 2) for b in base]))
    # the stack's sides: the edges of many sheets
    for i in range(4):
        j = (i + 1) % 4
        side = QPolygonF([base[i], base[j], top[j], top[i]])
        edge = base[j] - base[i]
        facing = edge.x() > 0  # its outward normal points down the screen, towards us
        g = QLinearGradient(top[i], base[i])
        light = 1.0 if facing else 0.75
        for k in range(10):
            col = QColor(int(236 * light), int(210 * light), int(90 * light)) if k % 2 else \
                QColor(int(250 * light), int(228 * light), int(118 * light))
            g.setColorAt(k / 10, col)
            g.setColorAt((k + 1) / 10 - 0.001, col)
        g.setColorAt(1, QColor(int(200 * light), int(170 * light), int(60 * light)))
        p.setBrush(g)
        p.drawPolygon(side)
    # the top sheet
    g = QLinearGradient(top[0], top[2])
    g.setColorAt(0, QColor(255, 240, 128))
    g.setColorAt(1, QColor(242, 218, 96))
    p.setBrush(g)
    p.drawPolygon(QPolygonF(top))
    p.setBrush(QColor(255, 255, 255, 30))  # the adhesive strip along the back
    p.drawPolygon(QPolygonF([top[0], top[1], top[1] + (top[2] - top[1]) * 0.2, top[0] + (top[3] - top[0]) * 0.2]))
    # the front corner of the top sheet lifts under the pointer, inviting a pull
    curl = 0.25 + 0.75 * hover
    corner = top[2]
    a = corner + (top[3] - corner) * (0.2 + 0.12 * curl)
    b = corner + (top[1] - corner) * (0.2 + 0.12 * curl)
    mid = (a + b) / 2
    flap_tip = corner + (mid - corner) * (2.0 * curl) - QPointF(0, 10 * curl)
    p.setBrush(QColor(0, 0, 0, int(50 + 40 * hover)))
    p.drawPolygon(QPolygonF([a, b, flap_tip + QPointF(3, 4)]))
    p.setBrush(QColor(250, 226, 104))
    p.drawPolygon(QPolygonF([a, b, corner]))  # the sheet beneath
    g = QLinearGradient(mid, flap_tip)
    g.setColorAt(0, QColor(232, 208, 92))
    g.setColorAt(1, QColor(255, 246, 170))
    p.setBrush(g)
    p.drawPolygon(QPolygonF([a, b, flap_tip]))
    p.restore()


# --- the notes ----------------------------------------------------------------------------

class Stickies(QObject):
    """The placed notes, the one being dragged, and the editor used to write on them."""
    changed = pyqtSignal(QRectF)  # a scene area needs repainting
    desk_changed = pyqtSignal()  # the notes lying on the desk top (part of the desk's static layer) changed

    def __init__(self):
        super().__init__()
        self.notes = []
        self.held = None
        self.editing = None
        self._paper = _paper()
        self._caret_on = True
        self._pressed = False
        self.error = None
        try:
            saved = json.loads(SAVED.read_text(encoding="utf-8"))
            for n in saved:
                self.notes.append(Sticky(n["mode"], float(n["x"]), float(n["y"]), float(n["angle"]), str(n.get("text", ""))))
        except FileNotFoundError:
            pass
        except (OSError, ValueError, KeyError, TypeError) as e:
            self.error = f"Couldn't read the sticky notes in {SAVED}: {e}"

        self.host = QWidget()
        self.host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.host.resize(IMG, IMG)
        self.edit = QPlainTextEdit(self.host)
        self.edit.setFrameStyle(0)
        self.edit.document().setDocumentMargin(0)
        self.edit.setStyleSheet("QPlainTextEdit { background: transparent; color: #1c2248;"
                                " selection-background-color: rgba(230, 150, 40, 120); selection-color: #1c2248; }")
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setGeometry(TEXT_RECT.toRect())
        self.edit.viewport().setAutoFillBackground(False)
        self.host.show()  # needed so the editor lays out; WA_DontShowOnScreen keeps it invisible
        self.edit.textChanged.connect(self._on_text)
        self.edit.cursorPositionChanged.connect(self._restart_caret)
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self.save)
        self._blink = QTimer(self, interval=530, timeout=self._toggle_caret)

    # -- finding notes ---------------------------------------------------------
    def note_at(self, pt):
        for n in reversed(self.notes):  # the topmost first
            if n.contains(pt):
                return n
        return None

    def bounds(self):
        r = QRectF()
        for n in self.notes:
            r = r.united(n.bounds())
        return r

    def _raise(self, note):
        self.notes.remove(note)
        self.notes.append(note)

    # -- dragging --------------------------------------------------------------
    def pick_up(self, note, pos):
        """Start carrying a note: a new one off the pad (note=None) or one already stuck down."""
        if note is None:
            note = Sticky("desk", 0, 0, random.uniform(-6, 6))
        else:
            if note is self.editing:
                self.finish_editing()
            self.changed.emit(note.bounds())
            self.notes.remove(note)
            if note.mode == "desk":
                self.desk_changed.emit()
        self.held = Held(note, pos)
        self._render(note)
        self.changed.emit(self.held.bounds())

    def carry(self, pos):
        old = self.held.bounds()
        self.held.pos = pos
        self.changed.emit(old.united(self.held.bounds()))

    def put_down(self):
        held, self.held = self.held, None
        note, c = held.sticky, held.pos
        self.changed.emit(held.bounds())
        x = min(max(c.x(), 70), desk.W - 70)
        if c.y() < desk.SURFACE_BACK_Y:  # stuck upright on the organiser
            o = desk.ORGANIZER
            note.mode, note.x, note.y = "wall", x, min(max(c.y(), o.top() + WALL_SIZE / 2), WALL_LOW - WALL_SIZE / 2)
        else:  # lying on the desk top
            w = _surface_t()[1].map(QPointF(x, min(c.y(), desk.SURFACE_FRONT_Y)))
            note.mode = "desk"
            note.x = min(max(w.x(), NOTE * 0.6), desk.SURFACE_WORLD.width() - NOTE * 0.6)
            note.y = min(max(w.y(), NOTE * 0.6), desk.SURFACE_WORLD.height() - NOTE * 0.6)
            # don't let it slide out of reach behind the radio, gauges and pen cup at the back
            while note.polygon().boundingRect().top() < BACK_ROW and note.y < desk.SURFACE_WORLD.height() - NOTE:
                note.y += 8
        self.notes.append(note)
        self._render(note)
        self.changed.emit(note.bounds())
        if note.mode == "desk":
            self.desk_changed.emit()
        self.save()
        return note

    def throw_away(self, note):
        if note is self.editing:
            self.finish_editing()
        self.notes.remove(note)
        self.changed.emit(note.bounds())
        if note.mode == "desk":
            self.desk_changed.emit()
        self.save()

    # -- writing ---------------------------------------------------------------
    def start_editing(self, note):
        if self.editing is not None:
            self.finish_editing()
        self._raise(note)
        self.editing = note
        self.edit.blockSignals(True)
        self.edit.setFont(_fit_font(note.text))
        self.edit.setPlainText(note.text)
        self.edit.blockSignals(False)
        cursor = self.edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.edit.setTextCursor(cursor)
        self.edit.ensureCursorVisible()
        self._blink.start()
        self._restart_caret()
        if note.mode == "desk":
            self.desk_changed.emit()  # it comes out of the static layer while it is written on

    def finish_editing(self):
        note, self.editing = self.editing, None
        if note is None:
            return
        self._blink.stop()
        self._pressed = False
        note.text = self.edit.toPlainText()
        self._render(note)
        if note.mode == "desk":
            self.desk_changed.emit()
        self.save()

    def key(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finish_editing()
            return
        QApplication.sendEvent(self.edit, event)

    def mouse(self, kind, scene_pt):
        """Forward a press/move/release on the note being written to its editor, to place the caret."""
        note = self.editing
        if note is None or (kind != "press" and not self._pressed):
            return False
        local = note.to_note(scene_pt)
        if kind == "press":
            if not (0 <= local.x() <= IMG and 0 <= local.y() <= IMG):
                return False
            self._pressed = True
        elif kind == "release":
            self._pressed = False
        local -= TEXT_RECT.topLeft()
        etype = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
                 "release": QEvent.Type.MouseButtonRelease}[kind]
        ev = QMouseEvent(etype, local, local, Qt.MouseButton.LeftButton if kind != "move" else Qt.MouseButton.NoButton,
                         Qt.MouseButton.LeftButton if kind != "release" else Qt.MouseButton.NoButton,
                         Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.edit.viewport(), ev)
        self._restart_caret()
        return True

    def _on_text(self):
        font = _fit_font(self.edit.toPlainText())
        if font.pixelSize() != self.edit.font().pixelSize():
            self.edit.setFont(font)
        if self.editing is not None:
            self.editing.text = self.edit.toPlainText()
        self._save_timer.start()
        self._restart_caret()

    def _restart_caret(self):
        self._caret_on = True
        if self.editing is not None:
            self._blink.start()
            self._render(self.editing)

    def _toggle_caret(self):
        self._caret_on = not self._caret_on
        if self.editing is not None:
            self._render(self.editing)

    def save(self):
        self._save_timer.stop()
        data = [{"mode": n.mode, "x": round(n.x, 1), "y": round(n.y, 1), "angle": round(n.angle, 1), "text": n.text}
                for n in self.notes]
        try:
            SAVED.parent.mkdir(parents=True, exist_ok=True)
            SAVED.write_text(json.dumps(data, indent=1), encoding="utf-8")
            self.error = None
        except OSError as e:
            self.error = f"Couldn't save the sticky notes: {e.strerror or e}"

    # -- drawing ---------------------------------------------------------------
    def _render(self, note):
        img = QImage(self._paper)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if note is self.editing:
            self.edit.render(p, QPoint(int(TEXT_RECT.x()), int(TEXT_RECT.y())), flags=QWidget.RenderFlag.DrawChildren)
            if self._caret_on:
                r = self.edit.cursorRect()
                x = TEXT_RECT.x() + self.edit.viewport().x() + r.x() + 1
                y = TEXT_RECT.y() + self.edit.viewport().y() + r.y()
                p.setPen(QPen(INK, 2.6))
                p.drawLine(QPointF(x, y + 3), QPointF(x, y + r.height() - 2))
            # a faint pencil outline shows the note is being written on
            p.setPen(QPen(QColor(150, 100, 10, 190), 4, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(QRectF(7, 7, IMG - 14, IMG - 14))
        elif note.text:
            p.setFont(_fit_font(note.text))
            p.setPen(INK)
            p.drawText(TEXT_RECT, Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, note.text)
        p.end()
        note.image = img
        if self.held is not None and self.held.sticky is note:
            self.changed.emit(self.held.bounds())
        elif note in self.notes:
            self.changed.emit(note.bounds())

    def _paint_note(self, p, note, transform, lift):
        if note.image is None:
            self._render(note)
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        poly = transform.map(QPolygonF(QRectF(0, 0, IMG, IMG)))
        p.setPen(Qt.PenStyle.NoPen)
        dx, dy = (12, 20) if lift else (3, 4)
        for i, a in enumerate((60, 34, 18) if lift else (70, 30)):
            p.setBrush(QColor(0, 0, 0, a))
            p.drawPolygon(QPolygonF([q + QPointF(dx + i * 2, dy + i * 2) for q in poly]))
        p.setTransform(transform, True)
        p.drawImage(QRectF(0, 0, IMG, IMG), note.image)
        p.setPen(QPen(QColor(190, 160, 50, 150), 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0, 0, IMG, IMG))
        p.restore()

    def paint(self, p, dirty):
        """The notes stuck on the organiser, and the one being written on."""
        for n in self.notes:
            if (n.mode == "wall" or n is self.editing) and dirty.intersects(n.bounds()):
                self._paint_note(p, n, n.transform(), False)

    def paint_on_desk(self, p):
        """The notes lying on the desk top, for the static layer: under everything standing on the desk."""
        for n in self.notes:
            if n.mode == "desk" and n is not self.editing:
                if n.image is None:
                    self._render(n)
                self._paint_note(p, n, n.transform(), False)

    def paint_held(self, p):
        if self.held is not None:
            self._paint_note(p, self.held.sticky, self.held.transform(), True)
