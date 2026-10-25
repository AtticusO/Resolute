"""Drawers that slide out towards the viewer and hold clickable items."""

import json
import math
import os
import shutil
import shlex
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (QColor, QFont, QFontMetrics, QIcon, QLinearGradient, QPainter, QPainterPath,
                         QPen, QPolygonF, QRadialGradient)

from . import config, desk, startmenu, system, textures

SERIF = "C059"


class Item:
    def __init__(self, name, icon, action, kind=None):
        self.name = name
        self.icon = icon  # painter function(p, rect, kind)
        self.action = action
        self.kind = kind
        self.rect = QRectF()


class Drawer:
    def __init__(self, rect, style, label, depth):
        self.rect = rect
        self.style = style
        self.label = label
        self.depth = depth
        self.t = 0.0
        self.target = 0.0
        self.hover = 0.0
        self.hovered = False
        self.hover_item = None
        self.items = []
        self.pan = depth + 40  # how far the view tilts down to look into the drawer

    # -- state -----------------------------------------------------------
    @property
    def is_open(self):
        return self.target > 0

    def open(self):
        self.refresh()
        self.target = 1.0

    def close(self):
        self.target = 0.0
        self.hover_item = None

    def toggle(self):
        self.close() if self.is_open else self.open()

    def refresh(self):
        pass

    def step(self):
        moving = False
        diff = self.target - self.t
        if abs(diff) > 0.002:
            # ease-out on the way out, quicker on the way back in
            self.t += diff * (0.16 if diff > 0 else 0.24)
            moving = True
        else:
            self.t = self.target
        h_target = 1.0 if self.hovered else 0.0
        if abs(h_target - self.hover) > 0.01:
            self.hover += (h_target - self.hover) * 0.25
            moving = True
        else:
            self.hover = h_target
        return moving

    # -- geometry --------------------------------------------------------
    def front_rect(self):
        t = self._ease(self.t)
        grow = 1 + 0.05 * t  # closer to the viewer, so a little larger
        w, h = self.rect.width() * grow, self.rect.height() * grow
        cx = self.rect.center().x()
        top = self.rect.top() + self.depth * t
        return QRectF(cx - w / 2, top, w, h)

    def floor_polygon(self):
        f = self.front_rect()
        back_l, back_r = self.rect.left() + 8, self.rect.right() - 8
        return QPolygonF([QPointF(back_l + 12, self.rect.top() + 12), QPointF(back_r - 12, self.rect.top() + 12),
                          QPointF(f.right() - 22, f.top()), QPointF(f.left() + 22, f.top())])

    def floor_rect(self):
        """The usable floor area when fully open (items are laid out in here)."""
        return QRectF(self.rect.left() + 30, self.rect.top() + 16, self.rect.width() - 60, self.depth - 20)

    def damage_rect(self):
        """Canvas area this drawer can paint into."""
        r = QRectF(self.rect)
        r.setBottom(self.rect.bottom() + self.depth + self.rect.height() * 0.1 + 12)
        return r.adjusted(-30, -6, 30, 6)

    @staticmethod
    def _ease(t):
        return 1 - (1 - t) ** 2

    # -- input -----------------------------------------------------------
    def hit(self, pt):
        """Returns 'front', an Item, 'inside', or None."""
        if self.front_rect().contains(pt):
            return "front"
        if self.t > 0.9:
            for item in self.items:
                if item.rect.contains(pt):
                    return item
            if self.floor_polygon().containsPoint(pt, Qt.FillRule.OddEvenFill):
                return "inside"
        return None

    def wheel(self, steps):
        pass

    # -- painting --------------------------------------------------------
    def paint(self, p: QPainter):
        f = self.front_rect()
        if self.t > 0.002:
            self._paint_box(p, f)
        desk.drawer_front(p, f, self.style, self.label, self.hover)

    def _paint_box(self, p, f):
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        back_l, back_r, back_y = self.rect.left() + 8, self.rect.right() - 8, self.rect.top()
        # shadow the drawer box throws on what is below it
        sh = QRectF(f.left() - 4, f.top(), f.width() + 16, f.height() + 18)
        g = QLinearGradient(0, sh.top(), 0, sh.bottom())
        g.setColorAt(0, QColor(0, 0, 0, 160))
        g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setBrush(g)
        p.drawRect(sh.translated(4, 6))
        # side walls
        for left in (True, False):
            if left:
                wall = QPolygonF([QPointF(back_l, back_y), QPointF(back_l + 12, back_y + 12),
                                  QPointF(f.left() + 22, f.top()), QPointF(f.left() + 6, f.top())])
            else:
                wall = QPolygonF([QPointF(back_r, back_y), QPointF(back_r - 12, back_y + 12),
                                  QPointF(f.right() - 22, f.top()), QPointF(f.right() - 6, f.top())])
            p.setBrush(desk._tex(textures.desk_wood(vertical=True), 17))
            p.drawPolygon(wall)
            p.setBrush(QColor(0, 0, 0, 60 if left else 110))
            p.drawPolygon(wall)
        # back wall
        back = QPolygonF([QPointF(back_l, back_y), QPointF(back_r, back_y),
                          QPointF(back_r - 12, back_y + 12), QPointF(back_l + 12, back_y + 12)])
        p.setBrush(desk._tex(textures.desk_wood_dark()))
        p.drawPolygon(back)
        # floor
        floor = self.floor_polygon()
        p.setBrush(desk._tex(textures.felt()))
        p.drawPolygon(floor)
        fg = QLinearGradient(0, back_y, 0, f.top())
        fg.setColorAt(0, QColor(0, 0, 0, 170))
        fg.setColorAt(0.25, QColor(0, 0, 0, 70))
        fg.setColorAt(1, QColor(0, 0, 0, 20))
        p.setBrush(fg)
        p.drawPolygon(floor)
        # contents, clipped to the floor
        path = QPainterPath()
        path.addPolygon(floor)
        p.setClipPath(path)
        p.setOpacity(min(1.0, max(0.0, (self.t - 0.3) / 0.6)))
        self.paint_contents(p)
        p.restore()

    def paint_contents(self, p):
        for item in self.items:
            lifted = item is self.hover_item
            item.icon(p, item.rect.translated(0, -4 if lifted else 0), item.kind, lifted)
            _label(p, item, lifted)


def _label(p, item, lifted):
    r = item.rect
    box = QRectF(r.left() - 6, r.bottom() - 22, r.width() + 12, 20)
    font = QFont(SERIF)
    font.setPixelSize(12)
    p.setFont(font)
    text = QFontMetrics(font).elidedText(item.name, Qt.TextElideMode.ElideMiddle, int(box.width()))
    p.setPen(QColor(0, 0, 0, 140))
    p.drawText(box.translated(1, 1), Qt.AlignmentFlag.AlignCenter, text)
    p.setPen(QColor(255, 240, 210) if lifted else QColor(240, 224, 196))
    p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)


# --- icons ----------------------------------------------------------------------

EXT_COLORS = {
    "doc": (40, 80, 160), "docx": (40, 80, 160), "odt": (40, 80, 160), "rtf": (40, 80, 160),
    "ppt": (200, 90, 30), "pptx": (200, 90, 30), "odp": (200, 90, 30),
    "xls": (30, 120, 60), "xlsx": (30, 120, 60), "ods": (30, 120, 60), "csv": (30, 120, 60),
    "pdf": (170, 30, 30),
    "png": (110, 60, 140), "jpg": (110, 60, 140), "jpeg": (110, 60, 140), "gif": (110, 60, 140), "svg": (110, 60, 140),
    "zip": (110, 90, 60), "gz": (110, 90, 60), "tar": (110, 90, 60), "7z": (110, 90, 60),
}


def _shadow(p, path, lifted):
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 110 if lifted else 80))
    p.drawPath(path.translated(3, 6 if lifted else 3))


def paper_icon(p, rect, ext, lifted):
    icon = QRectF(rect.center().x() - 26, rect.top() + 6, 52, 66)
    fold = 14
    path = QPainterPath()
    path.moveTo(icon.topLeft())
    path.lineTo(icon.right() - fold, icon.top())
    path.lineTo(icon.right(), icon.top() + fold)
    path.lineTo(icon.bottomRight())
    path.lineTo(icon.bottomLeft())
    path.closeSubpath()
    _shadow(p, path, lifted)
    g = QLinearGradient(icon.topLeft(), icon.bottomRight())
    g.setColorAt(0, QColor(248, 242, 226))
    g.setColorAt(1, QColor(222, 212, 188))
    p.setPen(QPen(QColor(150, 136, 110), 0.8))
    p.setBrush(g)
    p.drawPath(path)
    corner = QPainterPath()
    corner.moveTo(icon.right() - fold, icon.top())
    corner.lineTo(icon.right() - fold, icon.top() + fold)
    corner.lineTo(icon.right(), icon.top() + fold)
    corner.closeSubpath()
    p.setBrush(QColor(200, 188, 160))
    p.drawPath(corner)
    # ruled text lines
    p.setPen(QPen(QColor(120, 110, 100, 150), 1))
    for i in range(5):
        y = icon.top() + 22 + i * 6
        p.drawLine(QPointF(icon.left() + 7, y), QPointF(icon.right() - (7 if i < 4 else 20), y))
    if ext:
        band = QRectF(icon.left() - 4, icon.bottom() - 20, icon.width() * 0.75, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(*EXT_COLORS.get(ext, (90, 80, 70))))
        p.drawRect(band)
        font = QFont("DejaVu Sans")
        font.setPixelSize(9)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(250, 245, 235))
        p.drawText(band, Qt.AlignmentFlag.AlignCenter, ext.upper()[:4])


def folder_icon(p, rect, kind, lifted):
    icon = QRectF(rect.center().x() - 34, rect.top() + 12, 68, 56)
    back = QPainterPath()
    back.moveTo(icon.left(), icon.top() + 8)
    back.lineTo(icon.left() + 4, icon.top())
    back.lineTo(icon.left() + 26, icon.top())
    back.lineTo(icon.left() + 30, icon.top() + 8)
    back.lineTo(icon.right(), icon.top() + 8)
    back.lineTo(icon.bottomRight())
    back.lineTo(icon.bottomLeft())
    back.closeSubpath()
    _shadow(p, back, lifted)
    p.setPen(QPen(QColor(130, 96, 40), 0.8))
    p.setBrush(QColor(196, 156, 86))
    p.drawPath(back)
    # a sheet of paper peeking out
    p.setBrush(QColor(244, 238, 222))
    p.drawRect(QRectF(icon.left() + 6, icon.top() + 12, icon.width() - 12, 20))
    front = QPainterPath()
    front.moveTo(icon.left(), icon.top() + 18)
    front.lineTo(icon.right(), icon.top() + 18)
    front.lineTo(icon.right() - 2, icon.bottom())
    front.lineTo(icon.left() + 2, icon.bottom())
    front.closeSubpath()
    g = QLinearGradient(icon.topLeft(), icon.bottomLeft())
    g.setColorAt(0, QColor(232, 196, 124))
    g.setColorAt(1, QColor(204, 162, 92))
    p.setBrush(g)
    p.drawPath(front)
    if kind == "up":
        p.setPen(QPen(QColor(110, 70, 20), 3, cap=Qt.PenCapStyle.RoundCap, join=Qt.PenJoinStyle.RoundJoin))
        c = QPointF(icon.center().x(), icon.top() + 38)
        p.drawLine(c + QPointF(0, 10), c + QPointF(0, -8))
        p.drawPolyline(QPolygonF([c + QPointF(-8, 0), c + QPointF(0, -9), c + QPointF(8, 0)]))


def notepad_icon(p, rect, kind, lifted):
    """Writing pad and fountain pen: the text editor."""
    pad = QRectF(rect.center().x() - 42, rect.top() + 8, 84, 104)
    path = QPainterPath()
    path.addRect(pad)
    _shadow(p, path, lifted)
    p.setPen(QPen(QColor(150, 136, 110), 0.8))
    p.setBrush(QColor(246, 238, 214))
    p.drawRect(pad)
    p.setBrush(QColor(120, 30, 24))
    p.drawRect(QRectF(pad.left(), pad.top(), pad.width(), 12))
    p.setPen(QPen(QColor(120, 140, 170, 160), 1))
    for i in range(8):
        y = pad.top() + 24 + i * 10
        p.drawLine(QPointF(pad.left() + 6, y), QPointF(pad.right() - 6, y))
    p.setPen(QPen(QColor(200, 80, 80, 140), 1))
    p.drawLine(QPointF(pad.left() + 16, pad.top() + 12), QPointF(pad.left() + 16, pad.bottom()))
    # handwriting squiggle
    p.setPen(QPen(QColor(30, 40, 90, 200), 1.3))
    ink = QPainterPath()
    ink.moveTo(pad.left() + 20, pad.top() + 31)
    for i in range(14):
        ink.quadTo(pad.left() + 23 + i * 4, pad.top() + 25 + (i % 2) * 8, pad.left() + 25 + i * 4, pad.top() + 31)
    p.drawPath(ink)
    # pen lying diagonally across the pad
    p.save()
    p.translate(pad.center().x() + 10, pad.center().y() + 14)
    p.rotate(-38)
    body = QPainterPath()
    body.addRoundedRect(QRectF(-48, -6, 76, 12), 6, 6)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(0, 0, 0, 80))
    p.drawPath(body.translated(3, 5))
    g = QLinearGradient(0, -6, 0, 6)
    g.setColorAt(0, QColor(70, 70, 80))
    g.setColorAt(0.4, QColor(20, 20, 24))
    g.setColorAt(1, QColor(5, 5, 8))
    p.setBrush(g)
    p.drawPath(body)
    p.setBrush(desk.BRASS)
    p.drawRect(QRectF(-14, -6, 4, 12))
    nib = QPainterPath()
    nib.moveTo(28, -5)
    nib.lineTo(46, 0)
    nib.lineTo(28, 5)
    nib.closeSubpath()
    p.setBrush(desk.BRASS_LIGHT)
    p.drawPath(nib)
    p.restore()


def slides_icon(p, rect, kind, lifted):
    """A fanned stack of 35mm slides: the slideshow program."""
    c = QPointF(rect.center().x(), rect.top() + 58)
    tints = [(140, 170, 200), (220, 170, 90), (120, 160, 110)]
    for i, angle in enumerate((-16, -2, 12)):
        p.save()
        p.translate(c + QPointF((i - 1) * 16, 0))
        p.rotate(angle)
        frame = QRectF(-34, -34, 68, 68)
        path = QPainterPath()
        path.addRoundedRect(frame, 5, 5)
        if i == 0:
            _shadow(p, path, lifted)
        p.setPen(QPen(QColor(150, 140, 120), 0.8))
        p.setBrush(QColor(242, 236, 222))
        p.drawPath(path)
        window = QRectF(-22, -16, 44, 32)
        g = QLinearGradient(window.topLeft(), window.bottomLeft())
        g.setColorAt(0, QColor(*tints[i]))
        g.setColorAt(1, QColor(*tints[i]).darker(160))
        p.setBrush(g)
        p.drawRect(window)
        if i == 2:  # a little landscape on the top slide
            hill = QPainterPath()
            hill.moveTo(window.bottomLeft())
            hill.quadTo(window.left() + 14, window.top() + 10, window.center().x(), window.bottom() - 8)
            hill.quadTo(window.right() - 8, window.top() + 6, window.right(), window.bottom())
            hill.closeSubpath()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(60, 100, 50))
            p.drawPath(hill)
            p.setBrush(QColor(250, 220, 120))
            p.drawEllipse(QPointF(window.right() - 10, window.top() + 8), 4, 4)
        font = QFont("DejaVu Sans")
        font.setPixelSize(6)
        p.setFont(font)
        p.setPen(QColor(110, 100, 90))
        p.drawText(QRectF(-30, 20, 60, 10), Qt.AlignmentFlag.AlignCenter, f"SLIDE {i + 1}")
        p.restore()


_code_logo = None


def code_icon(p, rect, kind, lifted):
    """A clothbound notebook in VS Code's blue with the editor's logo set into the cover."""
    global _code_logo
    book = QRectF(rect.center().x() - 40, rect.top() + 10, 80, 100)
    path = QPainterPath()
    path.addRoundedRect(book, 4, 4)
    _shadow(p, path, lifted)
    # page edges showing along the right and bottom
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(236, 228, 206))
    p.drawRoundedRect(book.adjusted(4, 4, 3, 3), 3, 3)
    g = QLinearGradient(book.topLeft(), book.bottomRight())
    g.setColorAt(0, QColor(30, 120, 196))
    g.setColorAt(1, QColor(10, 62, 120))
    p.setBrush(g)
    p.drawRoundedRect(book, 4, 4)
    # darker spine and gold tooling
    p.setBrush(QColor(8, 40, 84))
    p.drawRect(QRectF(book.left(), book.top(), 12, book.height()))
    p.setPen(QPen(QColor(214, 176, 92, 200), 1.2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(book.adjusted(17, 6, -6, -6))
    for y in (book.top() + 14, book.bottom() - 14):
        p.drawLine(QPointF(book.left() + 2, y), QPointF(book.left() + 10, y))
    # the editor's own logo on a cream bookplate
    plate = QRectF(book.center().x() - 20, book.top() + 22, 46, 46)
    p.setPen(QPen(QColor(214, 176, 92), 1.2))
    p.setBrush(QColor(244, 238, 222))
    p.drawRoundedRect(plate, 4, 4)
    if _code_logo is None:
        _code_logo = QIcon.fromTheme("vscode").pixmap(96, 96)
    if not _code_logo.isNull():
        p.drawPixmap(plate.adjusted(6, 6, -6, -6), _code_logo, QRectF(_code_logo.rect()))
    font = QFont(SERIF)
    font.setPixelSize(11)
    font.setBold(True)
    p.setFont(font)
    p.setPen(QColor(226, 190, 104))
    p.drawText(QRectF(book.left() + 14, book.bottom() - 26, book.width() - 16, 14), Qt.AlignmentFlag.AlignCenter, "CODE")


def app_icon(p, rect, pixmap, lifted):
    """A cream card with brass corners carrying a program's own icon: an application dropped into the drawer."""
    card = QRectF(rect.center().x() - 42, rect.top() + 10, 84, 100)
    path = QPainterPath()
    path.addRoundedRect(card, 5, 5)
    _shadow(p, path, lifted)
    g = QLinearGradient(card.topLeft(), card.bottomRight())
    g.setColorAt(0, QColor(250, 244, 228))
    g.setColorAt(1, QColor(222, 208, 178))
    p.setPen(QPen(QColor(150, 120, 80), 1))
    p.setBrush(g)
    p.drawPath(path)
    p.setPen(QPen(QColor(170, 140, 96, 150), 0.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(card.adjusted(5, 5, -5, -5), 3, 3)
    # brass corner guards
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(desk.BRASS)
    for cx, cy, dx, dy in ((card.left(), card.top(), 1, 1), (card.right(), card.top(), -1, 1),
                           (card.left(), card.bottom(), 1, -1), (card.right(), card.bottom(), -1, -1)):
        p.drawPolygon(QPolygonF([QPointF(cx, cy), QPointF(cx + 14 * dx, cy), QPointF(cx, cy + 14 * dy)]))
    if pixmap is not None and not pixmap.isNull():
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(QRectF(card.center().x() - 28, card.top() + 16, 56, 56), pixmap, QRectF(pixmap.rect()))
    p.setPen(QPen(QColor(150, 120, 80, 160), 1))
    p.drawLine(QPointF(card.left() + 22, card.bottom() - 20), QPointF(card.right() - 22, card.bottom() - 20))


# --- the working drawers ----------------------------------------------------------

class DocumentsDrawer(Drawer):
    COLS, ROWS = 7, 2

    def __init__(self, notify, open_text=None):
        super().__init__(desk.CENTER_DRAWER, "center", "DOCUMENTS", 330)
        self.notify = notify
        self.open_text = open_text  # lays a .txt file on the writing pad instead of opening an editor
        self.root = Path(config.get("documents_dir"))
        self.cwd = self.root
        self.page = 0
        self.entries = []

    def refresh(self):
        self.entries = []
        try:
            children = list(self.cwd.iterdir())
        except OSError:
            children = []
            if not self.cwd.exists():
                self.notify(f"{self.cwd} does not exist")
        if not config.get("show_hidden_files"):
            children = [c for c in children if not c.name.startswith(".")]
        children.sort(key=lambda c: (not c.is_dir(), c.name.lower()))
        if self.cwd != self.root:
            self.entries.append(("..", self.cwd.parent, "up"))
        for c in children:
            self.entries.append((c.name, c, "dir" if c.is_dir() else "file"))
        per = self.COLS * self.ROWS
        self.page = min(self.page, max(0, (len(self.entries) - 1) // per))
        self._layout()

    def _layout(self):
        area = self.floor_rect().adjusted(0, 30, 0, -8)
        cw = area.width() / self.COLS
        rh = area.height() / self.ROWS
        per = self.COLS * self.ROWS
        self.items = []
        for i, (name, path, kind) in enumerate(self.entries[self.page * per:(self.page + 1) * per]):
            col, row = i % self.COLS, i // self.COLS
            if kind == "up":
                item = Item("Back", folder_icon, lambda p=path: self._enter(p), "up")
            elif kind == "dir":
                item = Item(name, folder_icon, lambda p=path: self._enter(p))
            else:
                ext = path.suffix.lstrip(".").lower()
                opener = self.open_text if ext == "txt" and self.open_text else system.open_path
                item = Item(name, paper_icon, lambda p=path, o=opener: o(p), ext)
            item.rect = QRectF(area.left() + col * cw + 4, area.top() + row * rh + 6, cw - 8, min(rh - 4, 100))
            self.items.append(item)

    def _enter(self, path):
        self.cwd = path
        self.page = 0
        self.refresh()

    def pages(self):
        per = self.COLS * self.ROWS
        return max(1, math.ceil(len(self.entries) / per))

    def wheel(self, steps):
        new = max(0, min(self.pages() - 1, self.page + steps))
        if new != self.page:
            self.page = new
            self._layout()

    def paint_contents(self, p):
        area = self.floor_rect()
        # paper tab showing where we are
        try:
            rel = self.cwd.relative_to(self.root)
            crumbs = [self.root.name or "Documents"] + list(rel.parts)
        except ValueError:
            crumbs = [str(self.cwd)]
        tab = QRectF(area.left(), area.top(), area.width() * 0.6, 22)
        p.setPen(QPen(QColor(150, 130, 100), 0.8))
        p.setBrush(QColor(236, 226, 200))
        p.drawRoundedRect(tab, 3, 3)
        font = QFont(SERIF)
        font.setPixelSize(13)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(QColor(60, 44, 30))
        text = QFontMetrics(font).elidedText("  ›  ".join(crumbs), Qt.TextElideMode.ElideLeft, int(tab.width() - 16))
        p.drawText(tab.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        if self.pages() > 1:
            font.setItalic(False)
            font.setPixelSize(12)
            p.setFont(font)
            p.setPen(QColor(240, 224, 196))
            p.drawText(QRectF(area.right() - 200, area.top(), 200, 22),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"scroll for more  •  {self.page + 1} / {self.pages()}")
        if not self.entries:
            font.setPixelSize(16)
            font.setItalic(True)
            p.setFont(font)
            p.setPen(QColor(240, 224, 196, 200))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, "This drawer is empty")
        super().paint_contents(p)


class ProgramsDrawer(Drawer):
    """The office programs, plus any applications dragged in from the start menu or a file manager."""
    COLS, ROWS = 4, 2
    SMALL = 0.8  # icons shrink once the drawer holds more than the three built-in programs
    SAVED = config.CONFIG_PATH.parent / "programs.json"

    def __init__(self, notify):
        super().__init__(desk.PROGRAMS_DRAWER, "knob", "PROGRAMS", 330)
        self.notify = notify
        self.builtin = [
            Item("Text Editor", notepad_icon, self._text_editor),
            Item("Slideshow", slides_icon, self._slideshow),
            Item("VS Code", code_icon, self._code),
        ]
        self.added = []
        self.page = 0
        self.scale = 1.0
        self.drop_hint = False
        try:
            saved = json.loads(self.SAVED.read_text())
        except (OSError, ValueError):
            saved = []
        for path in saved:
            item = self._program(Path(path))
            if item:
                self.added.append(item)
        self._layout()

    # -- dropped programs -----------------------------------------------------
    @staticmethod
    def droppable(mime):
        """The launcher files and programs among the dragged files."""
        paths = []
        for url in mime.urls() if mime.hasUrls() else ():
            if url.isLocalFile():
                path = Path(url.toLocalFile())
                if path.is_file() and (path.suffix == ".desktop" or os.access(path, os.X_OK)):
                    paths.append(path)
        return paths

    def _program(self, path):
        if path.suffix == ".desktop":
            entry = startmenu.desktop_entry(path)
            if entry is None:
                return None
            item = Item(entry.name, app_icon, lambda: self._launch(path), startmenu.icon_named(entry.icon).pixmap(112, 112))
        elif path.is_file() and os.access(path, os.X_OK):
            item = Item(path.name, app_icon, lambda: self._launch(path),
                        startmenu.icon_named("application-x-executable").pixmap(112, 112))
        else:
            return None
        item.path = path
        return item

    def _launch(self, path):
        ok = system.launch_desktop_file(path) if path.suffix == ".desktop" else system._spawn([str(path)])
        if not ok:
            self.notify(f"Couldn't start {path.name}")

    def add(self, paths):
        have = {str(i.path): i.name for i in self.added}
        names, already, rejected = [], [], []
        for path in paths:
            if str(path) in have:
                already.append(have[str(path)])
                continue
            item = self._program(path)
            if item is None:
                rejected.append(path.name)
                continue
            self.added.append(item)
            have[str(path)] = item.name
            names.append(item.name)
        if names:
            self._save()
            self._layout()
            self.page = self.pages() - 1  # show where they went
            self._layout()
        notes = []
        if names:
            notes.append(f"Added {names[0]} to the PROGRAMS drawer" if len(names) == 1
                         else f"Added {len(names)} programs to the PROGRAMS drawer")
        if already:
            notes.append(f"{', '.join(already)} {'is' if len(already) == 1 else 'are'} already in the drawer")
        if rejected:
            notes.append(f"{', '.join(rejected)} {'is not a program' if len(rejected) == 1 else 'are not programs'}")
        if notes:
            self.notify("; ".join(notes))

    def remove(self, item):
        self.added.remove(item)
        self._save()
        self._layout()
        self.notify(f"Took {item.name} out of the PROGRAMS drawer")

    def _save(self):
        try:
            self.SAVED.parent.mkdir(parents=True, exist_ok=True)
            self.SAVED.write_text(json.dumps([str(i.path) for i in self.added], indent=1))
        except OSError as e:
            self.notify(f"Couldn't save the PROGRAMS drawer: {e.strerror or e}")

    # -- layout ------------------------------------------------------------
    def pages(self):
        n = len(self.builtin) + len(self.added)
        return 1 if n <= 3 else math.ceil(n / (self.COLS * self.ROWS))

    def _layout(self):
        programs = self.builtin + self.added
        area = self.floor_rect()
        self.page = min(self.page, self.pages() - 1)
        if len(programs) <= 3:  # just the built-in programs: full size in one row
            self.scale = 1.0
            self.items = programs
            cell = area.width() / 3
            for i, item in enumerate(programs):
                item.rect = QRectF(area.left() + i * cell + 2, area.top() + 24, cell - 4, 142)
            return
        self.scale = self.SMALL
        per = self.COLS * self.ROWS
        self.items = programs[self.page * per:(self.page + 1) * per]
        cw = area.width() / self.COLS
        rh = (area.height() - 26) / self.ROWS
        for i, item in enumerate(self.items):
            col, row = i % self.COLS, i // self.COLS
            item.rect = QRectF(area.left() + col * cw + 2, area.top() + 4 + row * rh, cw - 4, rh - 6)

    def wheel(self, steps):
        new = max(0, min(self.pages() - 1, self.page + steps))
        if new != self.page:
            self.page = new
            self._layout()

    def paint_contents(self, p):
        area = self.floor_rect()
        for item in self.items:
            lifted = item is self.hover_item
            r = item.rect.translated(0, -4 if lifted else 0)
            if self.scale == 1.0:
                item.icon(p, r, item.kind, lifted)
            else:
                p.save()
                p.translate(r.center().x(), r.top())
                p.scale(self.scale, self.scale)
                w = r.width() / self.scale
                item.icon(p, QRectF(-w / 2, 0, w, r.height() / self.scale), item.kind, lifted)
                p.restore()
            _label(p, item, lifted)
        font = QFont(SERIF)
        font.setPixelSize(13)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(QColor(240, 224, 196, 190))
        foot = QRectF(area.left(), area.bottom() - 24, area.width(), 22)
        if len(self.items) == len(self.builtin) + len(self.added) == 3:
            p.drawText(foot.translated(0, -40), Qt.AlignmentFlag.AlignCenter,
                       "Drag programs here from the start menu or a file manager")
        elif self.pages() > 1:
            p.drawText(foot, Qt.AlignmentFlag.AlignCenter, f"scroll for more  \u2022  {self.page + 1} / {self.pages()}")
        if self.drop_hint:
            p.setPen(QPen(desk.BRASS_LIGHT, 2, Qt.PenStyle.DashLine))
            p.setBrush(QColor(255, 230, 160, 28))
            p.drawRoundedRect(area.adjusted(-4, -2, 4, 2), 8, 8)

    # -- the built-in programs ------------------------------------------------
    def _text_editor(self):
        if system.run_command(config.get("text_editor_command")):
            return
        if system.run_command(config.get("text_editor_fallback")):
            self.notify("LibreOffice Writer isn't installed, so a plain text editor was opened instead")
        else:
            self.notify("No text editor is installed: run  sudo apt install libreoffice-writer")

    def _slideshow(self):
        if not system.run_command(config.get("slideshow_command")):
            cmd = shlex.split(config.get("slideshow_command"))[0]
            missing = "" if shutil.which(cmd) else f" ({cmd} not found)"
            self.notify(f"The slideshow program couldn't start{missing}: run  sudo apt install libreoffice-impress")

    def _code(self):
        if not system.run_command(config.get("code_editor_command")):
            self.notify("VS Code couldn't start: is it installed? (set code_editor_command in the settings)")


class FilesDrawer(Drawer):
    """Hanging file folders, as in an office desk: the whole filesystem, one directory at a time."""
    ROW = 34
    TAB_W = 150

    def __init__(self, notify):
        super().__init__(desk.FILES_DRAWER, "knob", "FILES", 360)
        self.notify = notify
        self.cwd = Path(config.get("files_start_dir")).expanduser()
        self.scroll = 0
        self.entries = []
        self.up_item = None

    def refresh(self):
        try:
            children = list(self.cwd.iterdir())
        except OSError as e:
            self.notify(f"Can't open {self.cwd}: {e.strerror or e}")
            if self.cwd.parent != self.cwd:
                self.cwd = self.cwd.parent
                return self.refresh()
            children = []
        if not config.get("show_hidden_files"):
            children = [c for c in children if not c.name.startswith(".")]

        def is_dir(c):
            try:
                return c.is_dir()
            except OSError:
                return False
        self.entries = sorted(((c.name, c, is_dir(c)) for c in children), key=lambda e: (not e[2], e[0].lower()))
        self.scroll = min(self.scroll, max(0, len(self.entries) - self._visible_rows()))
        self._layout()

    def _rows_area(self):
        return self.floor_rect().adjusted(6, 40, -6, -6)

    def _visible_rows(self):
        return max(1, int((self._rows_area().height() - 30) // self.ROW) + 1)

    def _layout(self):
        area = self._rows_area()
        self.items = []
        if self.cwd.parent != self.cwd:
            fr = self.floor_rect()
            self.up_item = Item("Up", None, lambda: self._enter(self.cwd.parent), "up")
            self.up_item.rect = QRectF(fr.right() - 84, fr.top(), 84, 26)
            self.items.append(self.up_item)
        else:
            self.up_item = None
        for i, (name, path, is_dir) in enumerate(self.entries[self.scroll:self.scroll + self._visible_rows()]):
            if is_dir:
                item = Item(name, None, lambda p=path: self._enter(p), "dir")
            else:
                item = Item(name, None, lambda p=path: system.open_path(p), path.suffix.lstrip(".").lower())
            item.index = self.scroll + i
            item.rect = QRectF(area.left(), area.top() + i * self.ROW, area.width(), self.ROW)
            self.items.append(item)

    def _enter(self, path):
        self.cwd = path
        self.scroll = 0
        self.refresh()

    def wheel(self, steps):
        new = max(0, min(len(self.entries) - self._visible_rows(), self.scroll + steps * 2))
        if new != self.scroll:
            self.scroll = new
            self._layout()

    def paint_contents(self, p):
        fr = self.floor_rect()
        area = self._rows_area()
        # path label
        tab = QRectF(fr.left(), fr.top(), fr.width() - 94, 26)
        p.setPen(QPen(QColor(150, 130, 100), 0.8))
        p.setBrush(QColor(236, 226, 200))
        p.drawRoundedRect(tab, 3, 3)
        font = QFont(SERIF)
        font.setPixelSize(13)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(QColor(60, 44, 30))
        home = Path.home()
        shown = "~" + str(self.cwd)[len(str(home)):] if self.cwd == home or home in self.cwd.parents else str(self.cwd)
        text = QFontMetrics(font).elidedText(shown, Qt.TextElideMode.ElideLeft, int(tab.width() - 16))
        p.drawText(tab.adjusted(8, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        if self.up_item:
            r = self.up_item.rect
            lifted = self.hover_item is self.up_item
            p.setPen(QPen(desk.BRASS_DARK, 1))
            g = QLinearGradient(r.topLeft(), r.bottomLeft())
            g.setColorAt(0, desk.BRASS_LIGHT if lifted else desk.BRASS)
            g.setColorAt(1, desk.BRASS_DARK)
            p.setBrush(g)
            p.drawRoundedRect(r, 4, 4)
            font.setItalic(False)
            font.setBold(True)
            p.setFont(font)
            p.setPen(QColor(50, 30, 10))
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "▲  Up")
        # the two metal rails the folders hang from
        for x in (area.left() - 4, area.right() + 4):
            g = QLinearGradient(x - 3, 0, x + 3, 0)
            g.setColorAt(0, QColor(70, 70, 74))
            g.setColorAt(0.5, QColor(200, 200, 206))
            g.setColorAt(1, QColor(60, 60, 64))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(g)
            p.drawRect(QRectF(x - 3, area.top() - 6, 6, area.height() + 12))
        rows = [i for i in self.items if i is not self.up_item]
        if not rows:
            font.setPixelSize(16)
            font.setItalic(True)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor(240, 224, 196, 200))
            p.drawText(area, Qt.AlignmentFlag.AlignCenter, "This folder is empty")
        for item in rows:  # back to front, so each folder overlaps the one behind it
            self._paint_folder(p, item, item is self.hover_item)
        if len(self.entries) > self._visible_rows():
            last = min(len(self.entries), self.scroll + self._visible_rows())
            font.setPixelSize(12)
            font.setItalic(True)
            font.setBold(False)
            p.setFont(font)
            p.setPen(QColor(240, 224, 196))
            p.drawText(QRectF(fr.left(), fr.bottom() - 18, fr.width(), 18), Qt.AlignmentFlag.AlignRight,
                       f"scroll for more  •  {self.scroll + 1}–{last} of {len(self.entries)}")

    def _paint_folder(self, p, item, lifted):
        r = item.rect.translated(0, -7 if lifted else 0)
        folder = item.kind == "dir"
        if folder:  # manila hanging folder
            body, edge, ink = QColor(206, 166, 78), QColor(232, 196, 108), QColor(60, 40, 10)
        else:  # a loose sheet of paper
            body, edge, ink = QColor(226, 220, 204), QColor(246, 242, 230), QColor(50, 44, 36)
        if lifted:
            body, edge = body.lighter(112), edge.lighter(110)
        tab_w = self.TAB_W if folder else self.TAB_W - 20
        tab_x = r.left() + 10 + (item.index % 3) * (r.width() - tab_w - 20) / 2
        tab = QRectF(tab_x, r.top(), tab_w, 20)
        band_y = r.top() + 18
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # body hanging below the top edge (covered lower down by the folder in front)
        shade = QLinearGradient(0, band_y, 0, band_y + 46)
        shade.setColorAt(0, body)
        shade.setColorAt(1, body.darker(170))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shade)
        p.drawRect(QRectF(r.left() + 6, band_y, r.width() - 12, 46))
        # tab
        path = QPainterPath()
        path.addRoundedRect(tab, 4, 4)
        path.addRect(QRectF(tab.left(), tab.top() + 8, tab.width(), tab.height() - 8))
        p.setBrush(edge)
        p.drawPath(path.simplified())
        label_card = tab.adjusted(8, 3, -8, -3)
        p.setBrush(QColor(250, 248, 240) if folder else QColor(255, 255, 255))
        p.setPen(QPen(QColor(150, 130, 90), 0.6))
        p.drawRect(label_card)
        font = QFont(SERIF)
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(ink)
        name = item.name
        if not folder and item.kind:
            badge = QRectF(label_card.right() - 30, label_card.top() + 1, 29, label_card.height() - 2)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(*EXT_COLORS.get(item.kind, (90, 80, 70))))
            p.drawRect(badge)
            bf = QFont("DejaVu Sans")
            bf.setPixelSize(8)
            bf.setBold(True)
            p.setFont(bf)
            p.setPen(QColor(250, 245, 235))
            p.drawText(badge, Qt.AlignmentFlag.AlignCenter, item.kind.upper()[:4])
            p.setFont(font)
            p.setPen(ink)
            label_card.setRight(badge.left() - 2)
        text = QFontMetrics(font).elidedText(name, Qt.TextElideMode.ElideMiddle, int(label_card.width() - 6))
        p.drawText(label_card.adjusted(3, 0, -3, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)
        # folded top edge running the width of the drawer, with hooks onto the rails
        band = QRectF(r.left() - 4, band_y, r.width() + 8, 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(edge)
        p.drawRect(band)
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRect(QRectF(band.left(), band.bottom(), band.width(), 2))
        if folder:
            p.setBrush(QColor(90, 90, 96))
            for x in (band.left() - 3, band.right() - 3):
                p.drawRect(QRectF(x, band.top() - 1, 6, 5))
        p.restore()
