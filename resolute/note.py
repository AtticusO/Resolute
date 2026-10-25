"""The inkwell and quill, and the sheet of note paper it lays on the writing pad.

The sheet lies flat on the pad in perspective. Behind it is a real text editor (an off-screen
QPlainTextEdit): the desk forwards keys and clicks to it, draws its contents onto the paper, and
whatever is written is saved to a plain text file.
"""

import math
from pathlib import Path

import numpy as np
from PyQt6.QtCore import QEvent, QObject, QPoint, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QFontMetricsF, QImage, QLinearGradient, QMouseEvent,
                         QPainter, QPainterPath, QPen, QPolygonF, QRadialGradient, QTransform)
from PyQt6.QtWidgets import QApplication, QPlainTextEdit, QWidget

from . import config, desk
from .textures import _value_noise

# --- the inkwell on the desk ----------------------------------------------------------

CX = 1404.0
BASE_Y = 482.0
BOTTLE_W = 64.0
BOTTLE_H = 42.0
NECK_W = 26.0
NECK_H = 11.0
TOP_Y = BASE_Y - BOTTLE_H - NECK_H
QUILL_ANGLE = 22.0  # degrees from vertical, leaning right
QUILL_LEN = 178.0

# The sheet, in the flat desk-top coordinates of desk.SURFACE_WORLD: a card-sized page on the pad.
PAPER_WORLD = QRectF(905, 548, 330, 350)
PAPER_ANGLE = -1.0  # set down just slightly askew
UPRIGHT = 0.45  # 0 = lying fully flat in the desk's perspective, 1 = facing the viewer; in between reads better
IMG_W, IMG_H = 660, 700  # resolution the page is drawn at before it is laid onto the desk


def bounds():
    return QRectF(CX - 50, TOP_Y - QUILL_LEN - 20, 160, BOTTLE_H + NECK_H + QUILL_LEN + 30)


def contains(pt):
    if QRectF(CX - BOTTLE_W / 2 - 3, TOP_Y - 2, BOTTLE_W + 6, BOTTLE_H + NECK_H + 6).contains(pt):
        return True
    # a band around the quill
    a = math.radians(QUILL_ANGLE)
    d = pt - QPointF(CX, TOP_Y)
    along = -d.y() * math.cos(a) + d.x() * math.sin(a)
    across = d.x() * math.cos(a) + d.y() * math.sin(a)
    return 0 <= along <= QUILL_LEN + 10 and abs(across) <= 16


def paint_shadow(p):
    g = QRadialGradient(QPointF(CX + 8, BASE_Y + 2), BOTTLE_W)
    g.setColorAt(0, QColor(0, 0, 0, 170))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.translate(0, (BASE_Y + 2) * (1 - 0.25))
    p.scale(1, 0.25)
    p.setBrush(g)
    p.drawEllipse(QPointF(CX + 8, BASE_Y + 2), BOTTLE_W * 0.95, BOTTLE_W * 0.95)
    p.restore()


def paint_inkwell(p: QPainter, lift=0.0):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    neck = QRectF(CX - NECK_W / 2, TOP_Y, NECK_W, NECK_H)
    # quill first: its lower end disappears into the bottle
    _paint_quill(p, QPointF(CX + 2, TOP_Y + 6 - lift * 10))
    # bottle: thick square glass with bevelled shoulders, nearly full of ink
    body = QPainterPath()
    l, r, t, b = CX - BOTTLE_W / 2, CX + BOTTLE_W / 2, BASE_Y - BOTTLE_H, BASE_Y
    body.moveTo(l + 4, b)
    body.lineTo(l, b - 6)
    body.lineTo(l, t + 12)
    body.quadTo(l + 2, t + 2, l + 18, t)
    body.lineTo(r - 18, t)
    body.quadTo(r - 2, t + 2, r, t + 12)
    body.lineTo(r, b - 6)
    body.lineTo(r - 4, b)
    body.closeSubpath()
    glass = QLinearGradient(l, 0, r, 0)
    glass.setColorAt(0, QColor(30, 40, 58, 235))
    glass.setColorAt(0.3, QColor(70, 86, 110, 220))
    glass.setColorAt(0.55, QColor(24, 30, 46, 240))
    glass.setColorAt(1, QColor(12, 14, 22, 250))
    p.setPen(QPen(QColor(150, 170, 190, 120), 1))
    p.setBrush(glass)
    p.drawPath(body)
    # the ink inside, a little below the shoulder
    ink = QRectF(l + 4, t + 9, BOTTLE_W - 8, BOTTLE_H - 15)
    g = QLinearGradient(ink.topLeft(), ink.bottomLeft())
    g.setColorAt(0, QColor(18, 22, 60))
    g.setColorAt(1, QColor(6, 6, 16))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(ink, 4, 4)
    # thick-glass highlights
    p.setBrush(QColor(255, 255, 255, 55))
    p.drawRoundedRect(QRectF(l + 5, t + 6, 5, BOTTLE_H - 14), 2, 2)
    p.setBrush(QColor(255, 255, 255, 28))
    p.drawRoundedRect(QRectF(r - 12, t + 10, 3, BOTTLE_H - 20), 1.5, 1.5)
    # brass collar
    g = QLinearGradient(neck.topLeft(), neck.topRight())
    g.setColorAt(0, desk.BRASS_DARK)
    g.setColorAt(0.35, desk.BRASS_LIGHT)
    g.setColorAt(1, desk.BRASS_DARK)
    p.setBrush(g)
    p.drawRect(neck)
    p.drawEllipse(QRectF(neck.left(), neck.bottom() - 3, neck.width(), 6))
    p.setBrush(QColor(8, 6, 14))
    p.drawEllipse(QRectF(neck.left() + 3, neck.top() - 3, neck.width() - 6, 6))
    p.restore()


def _paint_quill(p, base):
    p.save()
    p.translate(base)
    p.rotate(QUILL_ANGLE)
    L = QUILL_LEN
    # vane: two curved halves along the upper part of the shaft
    for side in (-1, 1):
        vane = QPainterPath()
        vane.moveTo(0, -L * 0.30)
        width = 17 if side > 0 else 11
        vane.cubicTo(side * width, -L * 0.45, side * width * 1.1, -L * 0.8, side * 3, -L)
        vane.lineTo(0, -L)
        vane.closeSubpath()
        g = QLinearGradient(QPointF(0, -L * 0.3), QPointF(0, -L))
        g.setColorAt(0, QColor(214, 204, 186))
        g.setColorAt(0.6, QColor(246, 240, 228))
        g.setColorAt(1, QColor(190, 176, 150))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(g)
        p.drawPath(vane)
        # barbs
        p.setPen(QPen(QColor(150, 136, 112, 110), 0.7))
        for i in range(26):
            t = 0.32 + 0.66 * i / 25
            y = -L * t
            span = width * math.sin(math.pi * (t - 0.3) / 0.72) * (1.0 if side > 0 else 0.9)
            p.drawLine(QPointF(0, y), QPointF(side * span, y - 7))
    # a few split barbs give it a used, natural look
    p.setPen(QPen(QColor(90, 80, 66, 120), 0.8))
    p.drawLine(QPointF(0, -L * 0.62), QPointF(14, -L * 0.70))
    p.drawLine(QPointF(0, -L * 0.48), QPointF(-9, -L * 0.53))
    # shaft
    p.setPen(QPen(QColor(232, 220, 196), 2.2, cap=Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(0, 6), QPointF(0, -L + 2))
    p.setPen(QPen(QColor(150, 130, 100), 0.8))
    p.drawLine(QPointF(0.8, 6), QPointF(0.8, -L * 0.3))
    p.restore()


# --- the note paper -------------------------------------------------------------------

def _paper_texture(w, h):
    """Cream laid paper with faint fibres."""
    rng = np.random.default_rng(21)
    n = _value_noise(h, w, max(2, h // 3), max(2, w // 3), rng) * 0.6 + _value_noise(h, w, 6, 6, rng) * 0.4
    laid = (np.sin(np.arange(h) * 2 * np.pi / 3.2) * 0.5 + 0.5)[:, None] * 0.03
    t = np.clip(n * 0.12 + laid, 0, 1)[..., None]
    base = np.array([246, 238, 218], float)
    rgb = np.ascontiguousarray(np.clip(base * (1 - t), 0, 255).astype(np.uint8))
    return QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


class _RuledEdit(QPlainTextEdit):
    """A transparent editor that draws ruled lines lined up with the text."""

    def paintEvent(self, event):
        p = QPainter(self.viewport())
        fm = QFontMetricsF(self.font())
        step = fm.lineSpacing()
        offset = self.contentOffset().y() + self.document().documentMargin() + fm.ascent() + fm.descent() * 0.6
        y = offset % step
        p.setPen(QPen(QColor(120, 150, 190, 90), 3.5))  # thick enough to survive being shrunk onto the desk
        while y < self.viewport().height():
            p.drawLine(0, int(y), self.viewport().width(), int(y))
            y += step
        p.end()
        super().paintEvent(event)


class Note(QObject):
    """The page on the writing pad and the hidden editor behind it."""
    changed = pyqtSignal()  # the page needs repainting
    closed = pyqtSignal()

    MARGIN = 74  # left margin on the page, past the red line
    TOP = 64
    BOTTOM = 56

    def __init__(self):
        super().__init__()
        self.default_path = Path(config.get("note_file")).expanduser()  # the quill's own note
        self.path = self.default_path
        self.visible = False
        self.t = 0.0  # 0 = put away, 1 = lying on the pad
        self.image = None
        self._texture = _paper_texture(IMG_W, IMG_H)
        self._caret_on = True
        self._status = ""
        self._pressed = False

        # the editor lives in a window that is never shown on screen
        self.host = QWidget()
        self.host.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
        self.host.resize(IMG_W, IMG_H)
        self.edit = _RuledEdit(self.host)
        self.edit.setFrameStyle(0)
        self.edit.setStyleSheet("QPlainTextEdit { background: transparent; color: #1e2a5a;"
                                " selection-background-color: rgba(120, 150, 210, 110); selection-color: #1e2a5a; }")
        self.edit.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.edit.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        font = QFont("Z003")
        font.setPixelSize(52)
        self.edit.setFont(font)
        self.edit.setGeometry(self.MARGIN, self.TOP, IMG_W - self.MARGIN - 30, IMG_H - self.TOP - self.BOTTOM)
        self.edit.viewport().setAutoFillBackground(False)
        self.host.show()  # needed so the editor lays out; WA_DontShowOnScreen keeps it invisible
        self.edit.textChanged.connect(self._on_text)
        self.edit.cursorPositionChanged.connect(self._restart_caret)
        self.edit.updateRequest.connect(lambda *_: self._render())
        self._save_timer = QTimer(self, singleShot=True, interval=600, timeout=self.save)
        self._blink = QTimer(self, interval=530, timeout=self._toggle_caret)
        self._anim = QTimer(self, interval=16, timeout=self._step)

    # -- geometry ------------------------------------------------------------
    def page_transform(self):
        """Page pixels -> scene, through the desk top's perspective."""
        slide = (1 - self._ease(self.t)) * 160  # slides in from the front of the pad
        c = PAPER_WORLD.center()
        t = QTransform()
        t.translate(c.x(), c.y() + slide)
        t.rotate(PAPER_ANGLE)
        t.translate(-PAPER_WORLD.width() / 2, -PAPER_WORLD.height() / 2)
        t.scale(PAPER_WORLD.width() / IMG_W, PAPER_WORLD.height() / IMG_H)
        flat = (t * desk.surface_transform()).map(QPolygonF(QRectF(0, 0, IMG_W, IMG_H)))
        # ease the perspective: keep the bottom edge on the pad, bring the top towards facing the viewer
        tl, tr, br, bl = flat[0], flat[1], flat[2], flat[3]
        width = math.hypot(br.x() - bl.x(), br.y() - bl.y())
        height = width * IMG_H / IMG_W * 0.8
        up_l, up_r = QPointF(bl.x(), bl.y() - height), QPointF(br.x(), br.y() - height)
        quad = QPolygonF([tl + (up_l - tl) * UPRIGHT, tr + (up_r - tr) * UPRIGHT, br, bl])
        out = QTransform()
        QTransform.quadToQuad(QPolygonF(QRectF(0, 0, IMG_W, IMG_H)), quad, out)
        return out

    def scene_polygon(self):
        return self.page_transform().map(QPolygonF(QRectF(0, 0, IMG_W, IMG_H)))

    def bounds(self):
        return self.scene_polygon().boundingRect().adjusted(-30, -30, 40, 50)

    def to_page(self, scene_pt):
        inv, ok = self.page_transform().inverted()
        return inv.map(scene_pt) if ok else QPointF(-1, -1)

    def on_page(self, scene_pt):
        p = self.to_page(scene_pt)
        return self.visible and 0 <= p.x() <= IMG_W and 0 <= p.y() <= IMG_H

    def _close_rect(self):
        return QRectF(IMG_W - 66, 8, 56, 56)

    @staticmethod
    def _ease(t):
        return 1 - (1 - t) ** 3

    # -- opening and closing -------------------------------------------------
    def open_note(self, path=None):
        """Lay a page on the pad: the quill's note, or a text file. Returns False if the file isn't plain text."""
        path = Path(path) if path else self.default_path
        error = None
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        except UnicodeDecodeError:
            return False
        except OSError as e:
            if path != self.default_path:
                return False  # never offer a blank page that would be saved over a file we couldn't read
            text, error = "", f"Couldn't read {path}: {e.strerror}"
        if self.visible and self._save_timer.isActive():  # finish writing the page that is already out
            self.save()
        self.path = path
        if error:
            self._status = error
        else:
            self._show_path()
        self.edit.blockSignals(True)
        self.edit.setPlainText(text)
        self.edit.blockSignals(False)
        cursor = self.edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        self.edit.setTextCursor(cursor)
        self.edit.ensureCursorVisible()
        self.visible = True
        self._blink.start()
        self._anim.start()
        self._render()
        return True

    def put_away(self):
        if not self.visible:
            return
        if self._save_timer.isActive():
            self.save()
        self.visible = False
        self._blink.stop()
        self._anim.start()
        self.closed.emit()

    def _step(self):
        target = 1.0 if self.visible else 0.0
        self.t += (target - self.t) * 0.22
        if abs(target - self.t) < 0.004:
            self.t = target
            self._anim.stop()
        self.changed.emit()

    # -- input from the desk -------------------------------------------------
    def key(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.put_away()
            return
        QApplication.sendEvent(self.edit, event)

    def mouse(self, kind, scene_pt, button=Qt.MouseButton.LeftButton, buttons=Qt.MouseButton.LeftButton):
        """Forward a press/move/release on the page to the editor. Returns False if it missed the page."""
        page = self.to_page(scene_pt)
        if kind == "press":
            if self._close_rect().contains(page):
                self.put_away()
                return True
            if not (0 <= page.x() <= IMG_W and 0 <= page.y() <= IMG_H):
                return False
            self._pressed = True
        elif not self._pressed:
            return False
        if kind == "release":
            self._pressed = False
        local = page - QPointF(self.edit.x() + self.edit.viewport().x(), self.edit.y() + self.edit.viewport().y())
        etype = {"press": QEvent.Type.MouseButtonPress, "move": QEvent.Type.MouseMove,
                 "release": QEvent.Type.MouseButtonRelease}[kind]
        ev = QMouseEvent(etype, local, local, button if kind != "move" else Qt.MouseButton.NoButton,
                         buttons if kind != "release" else Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier)
        QApplication.sendEvent(self.edit.viewport(), ev)
        self._restart_caret()
        return True

    def wheel(self, steps):
        bar = self.edit.verticalScrollBar()
        bar.setValue(bar.value() + steps * 2)

    # -- file ----------------------------------------------------------------
    def _on_text(self):
        self._status = "Writing…"
        self._save_timer.start()
        self._render()

    def save(self):
        self._save_timer.stop()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(self.edit.toPlainText(), encoding="utf-8")
            self._show_path("Saved to ")
        except OSError as e:
            self._status = f"Couldn't save {self.path}: {e.strerror}"
        self._render()

    def _show_path(self, prefix=""):
        home = str(Path.home())
        shown = "~" + str(self.path)[len(home):] if str(self.path).startswith(home) else str(self.path)
        self._status = prefix + shown

    # -- drawing -------------------------------------------------------------
    def _restart_caret(self):
        self._caret_on = True
        if self.visible:
            self._blink.start()
        self._render()

    def _toggle_caret(self):
        self._caret_on = not self._caret_on
        self._render()

    def _render(self):
        """Draw the page (paper, ruling, text, caret) into an image that the desk lays onto the pad."""
        img = QImage(self._texture)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        g = QLinearGradient(0, 0, IMG_W, IMG_H)
        g.setColorAt(0, QColor(255, 255, 255, 30))
        g.setColorAt(0.6, QColor(0, 0, 0, 0))
        g.setColorAt(1, QColor(60, 40, 10, 34))
        p.fillRect(img.rect(), g)
        p.setPen(QPen(QColor(200, 80, 80, 130), 2.4))
        p.drawLine(QPointF(self.MARGIN - 12, 0), QPointF(self.MARGIN - 12, IMG_H))
        self.edit.render(p, QPoint(self.edit.x(), self.edit.y()), flags=QWidget.RenderFlag.DrawChildren)
        if self.visible and self._caret_on:
            r = self.edit.cursorRect()
            x = self.edit.x() + self.edit.viewport().x() + r.x() + 1
            y = self.edit.y() + self.edit.viewport().y() + r.y()
            p.setPen(QPen(QColor(30, 40, 90), 3))
            p.drawLine(QPointF(x, y + 4), QPointF(x, y + r.height() - 2))
        # close mark and save status
        font = QFont("C059")
        font.setPixelSize(44)
        p.setFont(font)
        p.setPen(QColor(110, 74, 42))
        p.drawText(self._close_rect(), Qt.AlignmentFlag.AlignCenter, "×")
        font.setPixelSize(22)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(QColor(100, 80, 60, 190))
        status = QFontMetrics(font).elidedText(self._status, Qt.TextElideMode.ElideLeft, IMG_W - self.MARGIN - 30)
        p.drawText(QRectF(self.MARGIN, IMG_H - self.BOTTOM + 10, IMG_W - self.MARGIN - 30, 36),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, status)
        p.end()
        self.image = img
        self.changed.emit()

    def paint(self, p: QPainter):
        """Lay the page onto the writing pad, with its shadow on the leather."""
        if self.t <= 0.002 or self.image is None:
            return
        p.save()
        p.setOpacity(min(1.0, self.t * 1.6))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setTransform(self.page_transform(), True)
        p.setPen(Qt.PenStyle.NoPen)
        for i, a in enumerate((70, 44, 24, 12)):  # soft shadow, offset away from the lamp
            p.setBrush(QColor(0, 0, 0, a))
            p.drawRoundedRect(QRectF(10 - i * 6, 14 - i * 6, IMG_W + i * 12, IMG_H + i * 12), 10, 10)
        p.drawImage(QRectF(0, 0, IMG_W, IMG_H), self.image)
        p.setPen(QPen(QColor(150, 130, 100, 140), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(QRectF(0, 0, IMG_W, IMG_H))
        p.restore()

