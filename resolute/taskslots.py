"""Open programs, shown as cards standing in the upright letter slots at the back of the desk."""

from types import SimpleNamespace

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPen

from . import desk, windows
from .startmenu import icon_for_window

CARD_H = 150
ICON = 26


class TaskSlots:
    def __init__(self):
        self.windows = []
        self.scroll = 0
        self.hover = None  # window id
        self._icons = {}
        self.tag = SimpleNamespace(cx=0, cy=0, r=0, detail="")

    def set_windows(self, wins):
        self.windows = wins
        self.scroll = max(0, min(self.scroll, len(wins) - desk.N_SLOTS))
        if self.hover not in {w.wid for w in wins}:
            self.hover = None

    def visible(self):
        return list(enumerate(self.windows[self.scroll:self.scroll + desk.N_SLOTS]))

    def card_rect(self, i, w):
        sw = desk.SLOTS.width() / desk.N_SLOTS
        x = desk.SLOTS.left() + i * sw
        lift = 16 if w.active and not w.minimized else (-22 if w.minimized else 0)
        if w.wid == self.hover:
            lift += 6
        return QRectF(x + 5, desk.SLOTS.bottom() - CARD_H - lift, sw - 9, CARD_H + lift)

    def window_at(self, pt):
        for i, w in self.visible():
            if self.card_rect(i, w).contains(pt):
                return w
        return None

    def tag_for(self, w):
        i = next(i for i, v in self.visible() if v is w)
        r = self.card_rect(i, w)
        self.tag.cx, self.tag.cy, self.tag.r = r.center().x(), r.top() + 14, 14
        state = " (minimised)" if w.minimized else ""
        self.tag.detail = (w.title or w.wm_class or "Untitled window") + state
        return self.tag

    def click(self, w):
        if w.active and not w.minimized:
            windows.minimize(w.wid)
        else:
            windows.activate(w.wid)

    def wheel(self, steps):
        new = max(0, min(len(self.windows) - desk.N_SLOTS, self.scroll + steps))
        changed = new != self.scroll
        self.scroll = new
        return changed

    def damage_rect(self):
        return desk.SLOTS.adjusted(-4, -60, 4, 4)

    def _icon(self, w):
        """Icons are rendered to a pixmap once; drawing a themed (often SVG) icon every frame is slow."""
        key = (w.wm_instance, w.wm_class)
        if key not in self._icons:
            self._icons[key] = icon_for_window(*key).pixmap(ICON * 2, ICON * 2)
        return self._icons[key]

    def paint(self, p: QPainter):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setClipRect(desk.SLOTS.adjusted(0, -60, 0, 0))
        for i, w in self.visible():
            self._paint_card(p, self.card_rect(i, w), w)
        if len(self.windows) > desk.N_SLOTS:
            font = QFont("C059")
            font.setPixelSize(11)
            font.setItalic(True)
            p.setFont(font)
            p.setPen(QColor(230, 200, 150))
            last = min(len(self.windows), self.scroll + desk.N_SLOTS)
            p.drawText(QRectF(desk.SLOTS.left(), desk.SLOTS.top() + 2, desk.SLOTS.width() - 6, 14),
                       Qt.AlignmentFlag.AlignRight, f"scroll • {self.scroll + 1}–{last} of {len(self.windows)}")
        p.restore()

    def _paint_card(self, p, r, w):
        hover = w.wid == self.hover
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRect(r.translated(2, 3))
        g = QLinearGradient(r.topLeft(), r.topRight())
        base = QColor(240, 230, 204) if not w.minimized else QColor(196, 184, 156)
        if hover:
            base = base.lighter(106)
        g.setColorAt(0, base)
        g.setColorAt(1, base.darker(118))
        p.setPen(QPen(QColor(120, 100, 70), 0.8))
        p.setBrush(g)
        p.drawRect(r)
        if w.active and not w.minimized:  # brass top edge marks the window in front
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(desk.BRASS)
            p.drawRect(QRectF(r.left(), r.top(), r.width(), 4))
        icon_rect = QRectF(r.center().x() - ICON / 2, r.top() + 9, ICON, ICON)
        p.setOpacity(0.55 if w.minimized else 1.0)
        p.drawPixmap(icon_rect, self._icon(w), QRectF(self._icon(w).rect()))
        # title runs up the card like the spine of a book
        font = QFont("C059")
        font.setPixelSize(11)
        p.setFont(font)
        length = r.height() - ICON - 24
        text = QFontMetrics(font).elidedText(w.title or w.wm_class, Qt.TextElideMode.ElideRight, int(length))
        p.save()
        p.translate(r.center().x(), r.bottom() - 6)
        p.rotate(-90)
        p.setPen(QColor(50, 36, 24))
        p.drawText(QRectF(0, -8, length, 16), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        p.restore()
        p.setOpacity(1.0)
