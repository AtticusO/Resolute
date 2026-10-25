"""Books standing in the organiser's pigeon holes, one per application.

Right-click a pigeon hole to put an application on it. Each one becomes a cloth-bound book seen
spine-on, coloured after the application's icon, with its name running down the spine above the
logo. Click the book to start the application.
"""

import colorsys
import json
import zlib
from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QLinearGradient, QPainter, QPainterPath, QPen

from . import config, desk, startmenu, system

SAVED = config.CONFIG_PATH.parent / "shelves.json"
CUBBIES = [i for i, c in enumerate(desk.CUBBIES) if c != desk.MAIL_CUBBY]  # the envelope has its own
SIDE = 8  # gap between a pigeon hole's wall and the first book
GILT = QColor(222, 184, 96)
_front = None


def _radio_front():
    global _front
    if _front is None:
        from . import radio
        _front = radio.front_path()
    return _front


def _cloth(pixmap, name):
    """A deep book-cloth colour taken from the logo, so each book is recognisable at a glance."""
    img = pixmap.toImage()
    r = g = b = n = 0
    step = max(1, img.width() // 24)
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if c.alpha() < 128:
                continue
            sat = max(c.red(), c.green(), c.blue()) - min(c.red(), c.green(), c.blue())
            weight = 1 + sat / 32  # colourful pixels count for more than white or grey ones
            r, g, b, n = r + c.red() * weight, g + c.green() * weight, b + c.blue() * weight, n + weight
    if n:
        h, s, _ = colorsys.rgb_to_hsv(r / n / 255, g / n / 255, b / n / 255)
    else:
        h, s = (zlib.crc32(name.encode()) % 360) / 360, 0.5
    if s < 0.15:  # a grey logo: give it a traditional dark cloth instead
        h, s = [(0.0, 0.55), (0.33, 0.45), (0.6, 0.5), (0.08, 0.6)][zlib.crc32(name.encode()) % 4]
    rr, gg, bb = colorsys.hsv_to_rgb(h, min(0.75, max(0.4, s)), 0.42)
    return QColor(int(rr * 255), int(gg * 255), int(bb * 255))


class Book:
    def __init__(self, path, entry):
        self.path = path
        self.name = entry.name
        self.pixmap = startmenu.icon_named(entry.icon).pixmap(64, 64)
        self.color = _cloth(self.pixmap, self.name)
        seed = zlib.crc32(str(path).encode())
        self.width = 26 + seed % 9  # books of slightly different thicknesses and heights
        self.height = 100 + (seed >> 8) % 24
        self.rect = QRectF()
        # the shelves share the gauges' hover-tag code, so a book carries the same fields
        self.cx = self.cy = 0.0
        self.r = 0.0
        self.detail = f"Open {self.name}"


class Shelves:
    def __init__(self, notify):
        self.notify = notify
        self.books = {i: [] for i in CUBBIES}
        self.hover = None
        try:
            saved = json.loads(SAVED.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        for key, paths in saved.items() if isinstance(saved, dict) else ():
            try:
                index = int(key)
            except ValueError:
                continue
            if index not in self.books:
                continue
            for path in paths:
                book = self._book(Path(path))
                if book:
                    self.books[index].append(book)
        for index in self.books:
            self._layout(index)

    @staticmethod
    def _book(path):
        entry = startmenu.desktop_entry(path)
        return Book(path, entry) if entry else None

    # -- finding ---------------------------------------------------------------
    def cubby_at(self, pt):
        for i in CUBBIES:
            if desk.CUBBIES[i].contains(pt):
                return i
        return None

    def book_at(self, pt):
        for books in self.books.values():
            for b in books:
                if b.rect.adjusted(0, -6, 0, 0).contains(pt):
                    return b
        return None

    def cubby_of(self, book):
        return next(i for i, books in self.books.items() if book in books)

    def has_room(self, index, book=None):
        used = sum(b.width + 2 for b in self.books[index])
        return used + (book.width if book else 34) <= desk.CUBBIES[index].width() - 2 * SIDE

    def damage_rect(self, index):
        return desk.CUBBIES[index].adjusted(-4, -10, 4, 4)

    # -- changing --------------------------------------------------------------
    def add(self, index, path):
        path = Path(path)
        if any(b.path == path for b in self.books[index]):
            self.notify("That application is already in this pigeon hole")
            return False
        book = self._book(path)
        if book is None:
            self.notify(f"Couldn't read {path.name}")
            return False
        if not self.has_room(index, book):
            self.notify("There's no room left in this pigeon hole")
            return False
        self.books[index].append(book)
        self._layout(index)
        self._save()
        return True

    def remove(self, book):
        index = self.cubby_of(book)
        self.books[index].remove(book)
        if self.hover is book:
            self.hover = None
        self._layout(index)
        self._save()
        return index

    def launch(self, book):
        if not system.launch_desktop_file(book.path):
            self.notify(f"Couldn't start {book.name}")

    def _layout(self, index):
        cell = desk.CUBBIES[index]
        x = cell.left() + SIDE
        for b in self.books[index]:
            h = min(b.height, cell.height() - 18)
            b.rect = QRectF(x, cell.bottom() - h, b.width, h)
            b.cx, b.cy, b.r = b.rect.center().x(), b.rect.top() + 30, 30
            x += b.width + 2

    def _save(self):
        data = {str(i): [str(b.path) for b in books] for i, books in self.books.items() if books}
        try:
            SAVED.parent.mkdir(parents=True, exist_ok=True)
            SAVED.write_text(json.dumps(data, indent=1), encoding="utf-8")
        except OSError as e:
            self.notify(f"Couldn't save the pigeon holes: {e.strerror or e}")

    # -- drawing ---------------------------------------------------------------
    def paint(self, p, dirty):
        for index, books in self.books.items():
            if books and dirty.intersects(self.damage_rect(index)):
                p.save()
                clip = QPainterPath()
                clip.addRect(desk.CUBBIES[index])
                p.setClipPath(clip.subtracted(_radio_front()))  # the radio and its aerial stand in front
                for b in books:
                    self._paint_book(p, b, b is self.hover)
                p.restore()

    def _paint_book(self, p, b, lifted):
        r = b.rect.translated(0, -5 if lifted else 0)  # tipped up a little, ready to be pulled out
        p.save()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        # shadow on the back of the pigeon hole and on the next book along
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRoundedRect(r.translated(4, 2), 2, 2)
        # rounded cloth spine: lit from the lamp on the left
        base = b.color.lighter(118) if lifted else b.color
        g = QLinearGradient(r.left(), 0, r.right(), 0)
        g.setColorAt(0, base.darker(150))
        g.setColorAt(0.3, base.lighter(130))
        g.setColorAt(0.55, base)
        g.setColorAt(1, base.darker(190))
        p.setBrush(g)
        p.drawRoundedRect(r, 2.5, 2.5)
        # gilt bands at head and tail
        p.setPen(QPen(GILT, 1.2))
        for y in (r.top() + 6, r.top() + 9, r.bottom() - 6, r.bottom() - 9):
            p.drawLine(QPointF(r.left() + 2, y), QPointF(r.right() - 2, y))
        # the logo at the foot of the spine, on a small gilt-edged label
        size = r.width() - 8
        logo = QRectF(r.center().x() - size / 2, r.bottom() - 14 - size, size, size)
        p.setPen(QPen(GILT, 1))
        p.setBrush(QColor(0, 0, 0, 60))
        p.drawRoundedRect(logo.adjusted(-1.5, -1.5, 1.5, 1.5), 2, 2)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawPixmap(logo.adjusted(1, 1, -1, -1), b.pixmap, QRectF(b.pixmap.rect()))
        # the name above it, running down the spine
        top, bottom = r.top() + 14, logo.top() - 6
        length = bottom - top
        font = QFont("C059")
        font.setBold(True)
        for size in range(min(12, int(r.width() * 0.45)), 7, -1):  # smaller lettering before cutting the name short
            font.setPixelSize(size)
            if QFontMetrics(font).horizontalAdvance(b.name) <= length:
                break
        p.setFont(font)
        text = QFontMetrics(font).elidedText(b.name, Qt.TextElideMode.ElideRight, int(length))
        p.translate(r.center().x(), top)
        p.rotate(90)
        box = QRectF(0, -r.width() / 2, length, r.width())
        p.setPen(QColor(0, 0, 0, 150))
        p.drawText(box.translated(0.8, 0.8), Qt.AlignmentFlag.AlignCenter, text)
        p.setPen(GILT.lighter(112) if lifted else GILT)
        p.drawText(box, Qt.AlignmentFlag.AlignCenter, text)
        p.restore()
