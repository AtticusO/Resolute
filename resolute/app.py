"""The desk window: scales the desk scene to the screen, tilts the view into open drawers, handles input."""

import shutil
import subprocess
import threading
import time
from types import SimpleNamespace

from PyQt6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer
from PyQt6.QtGui import QAction, QColor, QFont, QFontMetrics, QPainter, QPen, QPixmap, QRadialGradient
from PyQt6.QtWidgets import QMenu, QWidget

from . import audio, clock, config, desk, lamp, note, pencup, windows
from .drawers import DocumentsDrawer, FilesDrawer, ProgramsDrawer
from .gauges import Gauge
from .globe import Globe
from .radio import Radio
from .startmenu import StartMenu
from .taskslots import TaskSlots
from .system import Stats, open_browser, open_terminal, open_url

FRAME_MS = 33
DEVICE_MENU_STYLE = """
QMenu { background: #efe4c8; border: 4px solid #6b3418; padding: 4px; font-family: 'C059'; font-size: 14px; color: #3a2a1c; }
QMenu::item { padding: 5px 22px 5px 26px; }
QMenu::item:selected { background: #c9a55a; }
QMenu::item:disabled { color: #7a5a3a; font-style: italic; }
QMenu::separator { height: 1px; background: #c8b088; margin: 4px 8px; }
"""


def _gb(n):
    return n / 1024 ** 3


class DeskWindow(QWidget):
    def __init__(self, windowed=False):
        super().__init__()
        self.setWindowTitle("Resolute")
        if not windowed:
            self.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.windowed = windowed

        self.gauges = [
            Gauge(c, desk.GAUGE_RADIUS, title, sub, lo, hi, major, minors, red, lamp)
            for c, (title, sub, lo, hi, major, minors, red, lamp) in zip(desk.GAUGE_CENTERS, (
                ("CPU", "per cent load", 0, 100, 20, 4, 85, False),
                ("RAM", "per cent used", 0, 100, 20, 4, 85, False),
                ("TEMP", "degrees celsius", 20, 100, 20, 4, 85, True),
                ("DISK", "per cent full", 0, 100, 20, 4, 90, False),
            ))
        ]
        self.globe = Globe(desk.GLOBE_CENTER, desk.GLOBE_RADIUS)
        self.documents = DocumentsDrawer(self.notify)
        self.programs = ProgramsDrawer(self.notify)
        self.files = FilesDrawer(self.notify)
        self.drawers = [self.files, self.documents, self.programs]
        env = desk.envelope_rect()
        # the envelope shares the gauges' hover-tag code, so it carries the same fields
        self.mail = SimpleNamespace(cx=env.center().x(), cy=env.center().y(), r=env.height() / 2, detail="Open Gmail")
        self.mail_hover = 0.0
        self.mail_hovered = False
        self.menu = StartMenu()
        self.menu.quit_requested.connect(self.close)
        self.radio = Radio()
        self.clock = clock.Clock()
        self._last_second = -1
        self.slots = TaskSlots()
        self.knob_drag = None  # (part, start y, start volume, moved)
        self._audio_hold = 0.0  # ignore polled volume briefly after the user turns a knob
        self._last_knob_send = 0.0

        self.stats = Stats()
        self.lamp_hover = False
        self.cup_hover = 0.0
        self.cup_hovered = False
        self.cup_tag = SimpleNamespace(cx=pencup.CX, cy=pencup.TOP_Y - 60, r=60, detail="Open a terminal")
        self.ink_hover = 0.0
        self.ink_hovered = False
        self.ink_tag = SimpleNamespace(cx=note.CX + 30, cy=note.TOP_Y - 70, r=60, detail="Write a note")
        self.note = note.Note()
        self.note.changed.connect(lambda: self.update(self.to_widget(self.note.bounds())))
        self._note_drag = False
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.lamp_tag = SimpleNamespace(cx=lamp.tag_point().x(), cy=lamp.tag_point().y(), r=24, detail="Start menu")
        self.globe_flash = 0
        self.toast = None
        self.toast_ticks = 0
        self.hover_gauge = None
        self.cam = 0.0  # scene y at the top of the screen; grows as we look down into a drawer

        self._static = None
        self._scale, self._offset = 1.0, QPointF()

        self.stats_timer = QTimer(self, timeout=self.poll_stats)
        self.stats_timer.start(config.get("stats_interval_ms"))
        self.anim_timer = QTimer(self, timeout=self.tick)
        self.anim_timer.start(FRAME_MS)
        self.poll_stats()

        # windows and audio are read with external tools, so poll them off the UI thread
        self._own_wid = int(self.winId())
        self._polled = None
        self._poke = threading.Event()
        self._stop = threading.Event()
        threading.Thread(target=self._poll_loop, daemon=True).start()

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self._polled = (windows.list_windows(exclude={self._own_wid}), audio.read_state())
            except Exception as e:  # never let a tool hiccup kill the poller
                print(f"resolute: polling failed: {e}")
            self._poke.wait(1.0)
            self._poke.clear()

    def closeEvent(self, event):
        self._stop.set()
        self._poke.set()
        super().closeEvent(event)

    # -- coordinates -------------------------------------------------------
    def _fit(self):
        s = min(self.width() / desk.W, self.height() / desk.H)
        self._scale = s
        self._offset = QPointF((self.width() - desk.W * s) / 2, (self.height() - desk.H * s) / 2)

    def to_canvas(self, pos):
        return QPointF((pos.x() - self._offset.x()) / self._scale,
                       (pos.y() - self._offset.y()) / self._scale + self.cam)

    def to_widget(self, rect: QRectF, fixed=False):
        """Scene rect -> widget pixels. fixed=True for overlays that stay put while the view tilts."""
        top = rect.top() - (0 if fixed else self.cam)
        r = QRectF(rect.left() * self._scale + self._offset.x(), top * self._scale + self._offset.y(),
                   rect.width() * self._scale, rect.height() * self._scale)
        return r.toAlignedRect().adjusted(-2, -2, 2, 2)

    # -- rendering ---------------------------------------------------------
    def resizeEvent(self, event):
        self._fit()
        self._static = None
        super().resizeEvent(event)

    def _build_static(self):
        dpr = self.devicePixelRatioF()
        height = self._offset.y() * 2 + desk.SCENE_H * self._scale
        pm = QPixmap(int(self.width() * dpr), int(height * dpr) + 1)
        pm.setDevicePixelRatio(dpr)
        pm.fill(QColor(18, 30, 25))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.translate(self._offset)
        p.scale(self._scale, self._scale)
        desk.paint_static(p, self.gauges, self.globe)
        p.end()
        self._static = pm
        self.globe.build(self._scale * dpr)
        lamp.build(self._scale * dpr)
        # the lamp-light vignette never changes, so render it once
        vig = QPixmap(int(desk.W * self._scale * dpr), int(desk.H * self._scale * dpr))
        vig.fill(Qt.GlobalColor.transparent)
        vp = QPainter(vig)
        vp.scale(self._scale * dpr, self._scale * dpr)
        self._paint_vignette(vp)
        vp.end()
        self._vignette = vig

    def paintEvent(self, event):
        if self._static is None:
            self._build_static()
        p = QPainter(self)
        p.drawPixmap(QRectF(event.rect()), self._static, self._src(event.rect()))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.translate(self._offset)
        p.scale(self._scale, self._scale)
        p.translate(0, -self.cam)
        # only draw the parts that overlap the area being repainted (most frames it is just the globe)
        r = event.rect()
        dirty = QRectF((r.x() - self._offset.x()) / self._scale, (r.y() - self._offset.y()) / self._scale + self.cam,
                       r.width() / self._scale, r.height() / self._scale)

        def needs(rect):
            return dirty.intersects(rect)
        if needs(self._gauge_area()):
            for g in self.gauges:
                g.paint_dynamic(p)
        if needs(self._globe_rect()):
            self.globe.paint_dynamic(p)
        if self.globe_flash:
            p.save()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(255, 240, 200, 6 * self.globe_flash))
            p.drawEllipse(QPointF(*desk.GLOBE_CENTER), desk.GLOBE_RADIUS * 1.3, desk.GLOBE_RADIUS * 1.3)
            p.restore()
        if needs(pencup.bounds()):
            pencup.paint(p, self.cup_hover)
        if needs(note.bounds()):
            note.paint_inkwell(p, self.ink_hover)
        if needs(lamp.bounds()):
            lamp.paint(p, self.lamp_hover)
        if needs(desk.MAIL_CUBBY):
            desk.paint_envelope(p, self.mail_hover)
        if needs(self.slots.damage_rect()):
            self.slots.paint(p)
        if needs(self.radio.damage_rect()):
            self.radio.paint(p)
        if needs(self.clock.damage_rect()):
            self.clock.paint(p)
        # closed drawers first so an open one always lies on top
        for d in sorted(self.drawers, key=lambda d: d.t):
            if needs(d.damage_rect()):
                d.paint(p)
        if needs(self.note.bounds()):
            self.note.paint(p)
        # overlays fixed to the screen
        p.translate(0, self.cam)
        p.drawPixmap(QRectF(0, 0, desk.W, desk.H), self._vignette, QRectF(self._vignette.rect()))
        if self.hover_gauge:
            self._paint_gauge_tag(p, self.hover_gauge)
        if self.toast:
            self._paint_toast(p)
        p.end()

    def _src(self, rect: QRect):
        dpr = self._static.devicePixelRatio()
        y = rect.y() + self.cam * self._scale
        return QRectF(rect.x() * dpr, y * dpr, rect.width() * dpr, rect.height() * dpr)

    def _paint_vignette(self, p):
        """Lamplight falls off towards the corners of what you can see."""
        v = QRadialGradient(QPointF(desk.W * 0.45, desk.H * 0.42), desk.W * 0.64)
        v.setColorAt(0.55, QColor(0, 0, 0, 0))
        v.setColorAt(1, QColor(0, 0, 0, 175))
        p.fillRect(QRectF(0, 0, desk.W, desk.H), v)
        warm = QRadialGradient(QPointF(desk.W * 0.4, desk.H * 0.45), desk.W * 0.5)
        warm.setColorAt(0, QColor(255, 180, 90, 22))
        warm.setColorAt(1, QColor(255, 180, 90, 0))
        p.fillRect(QRectF(0, 0, desk.W, desk.H), warm)

    def _gauge_tag_rect(self, g):
        return QRectF(g.cx - 120, g.cy - self.cam - g.r - 46, 240, 34)

    def _paint_gauge_tag(self, p, g):
        r = self._gauge_tag_rect(g)
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 110))
        p.drawRoundedRect(r.translated(2, 3), 4, 4)
        p.setBrush(QColor(240, 230, 204))
        p.setPen(QPen(QColor(150, 110, 60), 1))
        p.drawRoundedRect(r, 4, 4)
        font = QFont("C059")
        font.setPixelSize(14)
        p.setFont(font)
        p.setPen(QColor(50, 34, 22))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, g.detail)
        p.restore()

    def _toast_rect(self):
        return QRectF(desk.W / 2 - 420, 1012, 840, 46)

    def _paint_toast(self, p):
        r = self._toast_rect()
        p.save()
        p.setOpacity(min(1.0, self.toast_ticks / 10))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 100))
        p.drawRoundedRect(r.translated(3, 4), 4, 4)
        p.setBrush(QColor(240, 230, 204))
        p.drawRoundedRect(r, 4, 4)
        font = QFont("C059")
        font.setPixelSize(16)
        font.setItalic(True)
        p.setFont(font)
        p.setPen(QColor(60, 40, 26))
        text = QFontMetrics(font).elidedText(self.toast, Qt.TextElideMode.ElideRight, int(r.width() - 30))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)
        p.restore()

    # -- updates -----------------------------------------------------------
    def notify(self, message):
        self.toast = message
        self.toast_ticks = 150  # about five seconds
        self.update(self.to_widget(self._toast_rect().adjusted(-4, -4, 8, 8), fixed=True))

    def _gauge_area(self):
        return desk.GAUGE_STAND.adjusted(-12, -24, 12, 24)

    def poll_stats(self):
        cpu = self.stats.cpu()
        ram, ram_used, ram_total = self.stats.ram()
        temp = self.stats.temperature()
        disk, disk_used, disk_total = self.stats.disk()
        self.gauges[0].set_target(cpu, f"{cpu:.0f}%", f"Processor load: {cpu:.0f}%")
        self.gauges[1].set_target(ram, f"{_gb(ram_used):.1f}/{_gb(ram_total):.0f}G",
                                  f"Memory: {_gb(ram_used):.1f} of {_gb(ram_total):.1f} GB used")
        self.gauges[2].set_target(temp, "--\u00b0C" if temp is None else f"{temp:.0f}\u00b0C",
                                  "No temperature sensor found" if temp is None else f"CPU temperature: {temp:.0f}\u00b0C")
        self.gauges[3].set_target(disk, f"{_gb(disk_used):.0f}/{_gb(disk_total):.0f}G",
                                  f"Storage: {_gb(disk_used):.0f} of {_gb(disk_total):.0f} GB used ({disk:.0f}%)")
        self.update(self.to_widget(self._gauge_area()))
        if self.hover_gauge:
            self.update(self.to_widget(self._gauge_tag_rect(self.hover_gauge), fixed=True))

    def tick(self):
        second = int(time.time())
        if second != self._last_second:  # the seconds hand ticks; the battery is checked every 30 s
            if second // 30 != self._last_second // 30:
                self.clock.poll()
            else:
                self.clock.update_tags()
            self._last_second = second
            self.update(self.to_widget(self.clock.damage_rect()))
        if self._polled is not None:
            wins, state = self._polled
            self._polled = None
            self.slots.set_windows(wins)
            self.update(self.to_widget(self.slots.damage_rect()))
            if time.monotonic() > self._audio_hold:
                self.radio.state = state
                self.radio.update_tags()
                self.update(self.to_widget(self.radio.damage_rect()))
        cam_target = max(d.pan * d.target for d in self.drawers)
        if abs(cam_target - self.cam) > 0.5:
            self.cam += (cam_target - self.cam) * 0.14
            self.update()
        elif self.cam != cam_target:
            self.cam = cam_target
            self.update()
        target = 1.0 if self.mail_hovered else 0.0
        if abs(target - self.mail_hover) > 0.01:
            self.mail_hover += (target - self.mail_hover) * 0.25
            self.update(self.to_widget(desk.MAIL_CUBBY.adjusted(-10, -10, 10, 10)))
        elif self.mail_hover != target:
            self.mail_hover = target
            self.update(self.to_widget(desk.MAIL_CUBBY.adjusted(-10, -10, 10, 10)))
        target = 1.0 if self.ink_hovered else 0.0
        if abs(target - self.ink_hover) > 0.01:
            self.ink_hover += (target - self.ink_hover) * 0.25
            self.update(self.to_widget(note.bounds()))
        elif self.ink_hover != target:
            self.ink_hover = target
            self.update(self.to_widget(note.bounds()))
        target = 1.0 if self.cup_hovered else 0.0
        if abs(target - self.cup_hover) > 0.01:
            self.cup_hover += (target - self.cup_hover) * 0.25
            self.update(self.to_widget(pencup.bounds()))
        elif self.cup_hover != target:
            self.cup_hover = target
            self.update(self.to_widget(pencup.bounds()))
        if any([g.step() for g in self.gauges]):
            self.update(self.to_widget(self._gauge_area()))
        self.globe.step()
        if self.globe_flash:
            self.globe_flash -= 1
        self.update(self.to_widget(self._globe_rect()))
        for d in self.drawers:
            if d.step():
                self.update(self.to_widget(d.damage_rect()))
        if self.toast_ticks:
            self.toast_ticks -= 1
            if self.toast_ticks < 10:
                self.update(self.to_widget(self._toast_rect().adjusted(-4, -4, 8, 8), fixed=True))
            if not self.toast_ticks:
                self.toast = None

    # -- input -------------------------------------------------------------
    def _target_at(self, pt):
        if self.note.on_page(pt):
            return "page", None
        # an open drawer covers what is beneath it
        for d in sorted(self.drawers, key=lambda d: -d.t):
            hit = d.hit(pt)
            if hit is not None:
                return d, hit
        if lamp.contains(pt):
            return "lamp", self.lamp_tag
        if pencup.contains(pt):
            return "cup", self.cup_tag
        if note.contains(pt):
            return "ink", self.ink_tag
        if self.globe.contains(pt):
            return "globe", None
        if desk.envelope_contains(pt):
            return "mail", self.mail
        w = self.slots.window_at(pt)
        if w:
            return "slot", w
        if self.radio.contains(pt):
            return "radio", self.radio.part_at(pt)
        if clock.contains(pt):
            return "clock", self.clock.tags[clock.part_at(pt)]
        for g in self.gauges:
            if g.contains(pt):
                return "gauge", g
        return None, None

    def mouseMoveEvent(self, event):
        pt = self.to_canvas(event.position())
        if self._note_drag:
            self.note.mouse("move", pt)
            return
        if self.knob_drag:
            self._drag_knob(pt)
            return
        target, hit = self._target_at(pt)
        part = hit if target == "radio" else None
        if part != self.radio.hover:
            self.radio.hover = part
            self.update(self.to_widget(self.radio.damage_rect()))
        wid = hit.wid if target == "slot" else None
        if wid != self.slots.hover:
            self.slots.hover = wid
            self.update(self.to_widget(self.slots.damage_rect()))
        lamp_hover = target == "lamp"
        if lamp_hover != self.lamp_hover:
            self.lamp_hover = lamp_hover
            self.update(self.to_widget(lamp.bounds()))
        self.cup_hovered = target == "cup"
        self.ink_hovered = target == "ink"
        self.globe.hover = target == "globe"
        self.mail_hovered = target == "mail"
        if target in ("gauge", "mail", "lamp", "cup", "ink", "clock"):
            gauge = hit
        elif target == "slot":
            gauge = self.slots.tag_for(hit)
        elif part:
            gauge = self.radio.tags[part]
        else:
            gauge = None
        if gauge is not self.hover_gauge:
            for g in (self.hover_gauge, gauge):
                if g:
                    self.update(self.to_widget(self._gauge_tag_rect(g).adjusted(-4, -4, 6, 6), fixed=True))
            self.hover_gauge = gauge
        for d in self.drawers:
            d.hovered = d is target and hit == "front"
            item = hit if d is target and hasattr(hit, "action") else None
            if item is not d.hover_item:
                d.hover_item = item
                self.update(self.to_widget(d.damage_rect()))
        if target == "page":
            self.setCursor(Qt.CursorShape.IBeamCursor)
            return
        clickable = target in ("lamp", "cup", "ink", "globe", "mail", "slot") or part or (target in self.drawers and hit != "inside")
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)

    def leaveEvent(self, event):
        self.lamp_hover = False
        self.cup_hovered = False
        self.ink_hovered = False
        self.update(self.to_widget(lamp.bounds()))
        self.globe.hover = False
        self.mail_hovered = False
        self.radio.hover = None
        self.slots.hover = None
        self.update(self.to_widget(self.radio.damage_rect()))
        self.update(self.to_widget(self.slots.damage_rect()))
        if self.hover_gauge:
            self.update(self.to_widget(self._gauge_tag_rect(self.hover_gauge).adjusted(-4, -4, 6, 6), fixed=True))
            self.hover_gauge = None
        for d in self.drawers:
            d.hovered = False

    def _globe_rect(self):
        r = desk.GLOBE_RADIUS
        cx, cy = desk.GLOBE_CENTER
        return QRectF(cx - r * 1.4, cy - r * 1.4, r * 2.8, r * 2.6)



    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.to_canvas(event.position())
        target, hit = self._target_at(pt)
        if target == "page":
            self._note_drag = self.note.mouse("press", pt)
            return
        if target == "radio" and hit in ("volume", "input"):
            dev = self._knob_device(hit)
            if dev:
                self.knob_drag = [hit, pt.y(), dev.volume, False]

    def mouseReleaseEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = self.to_canvas(event.position())
        if self._note_drag:
            self._note_drag = False
            self.note.mouse("release", pt)
            return
        if self.knob_drag:
            part, _, _, moved = self.knob_drag
            self.knob_drag = None
            if moved:  # make sure the last position of the drag is the one that sticks
                self._set_volume(part, self._knob_device(part).volume)
            else:
                self._toggle_mute(part)
            return
        target, hit = self._target_at(pt)
        if target == "lamp":
            self._close_drawers()
            anchor = self.mapToGlobal(self.to_widget(QRectF(lamp.menu_anchor(), lamp.menu_anchor())).topLeft())
            self.menu.popup_at(anchor)
        elif target == "ink":
            self.toggle_note()
        elif target == "cup":
            if not open_terminal():
                self.notify("Couldn't find a terminal program to open")
        elif target == "slot":
            self.slots.click(hit)
            self._poke.set()
        elif target == "radio":
            if hit == "dial":
                self._device_menu()
        elif target == "mail":
            if not open_url(config.get("mail_url")):
                self.notify("Couldn't open the browser for Gmail")
        elif target == "globe":
            self.globe.speed = 6.0
            self.globe_flash = 10
            if not open_browser():
                self.notify("Couldn't find a web browser to open")
        elif target in self.drawers:
            if hit == "front":
                self.note.put_away()
                for d in self.drawers:
                    if d is not target:
                        d.close()
                target.toggle()
            elif hasattr(hit, "action"):
                hit.action()
                if target is self.programs:
                    target.close()
                self.update(self.to_widget(target.damage_rect()))
        else:
            self._close_drawers()
            self.note.put_away()

    def wheelEvent(self, event):
        pt = self.to_canvas(event.position())
        target, hit = self._target_at(pt)
        step = -1 if event.angleDelta().y() > 0 else 1
        if target == "page":
            self.note.wheel(step)
        elif target == "radio" and hit in ("volume", "input"):
            dev = self._knob_device(hit)
            if dev:
                self._set_volume(hit, dev.volume - step * 5)
        elif target == "slot" and self.slots.wheel(step):
            self.update(self.to_widget(self.slots.damage_rect()))
        elif target in self.drawers and target.is_open:
            target.wheel(-1 if event.angleDelta().y() > 0 else 1)
            self.update(self.to_widget(target.damage_rect()))

    def keyPressEvent(self, event):
        if self.note.visible:  # typing goes onto the page
            self.note.key(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self._close_drawers()

    def focusNextPrevChild(self, forward):
        return False  # let Tab reach the note instead of moving focus

    def _close_drawers(self):
        for d in self.drawers:
            d.close()

    # -- note paper ----------------------------------------------------------
    def toggle_note(self):
        if self.note.visible:
            self.note.put_away()
            return
        self._close_drawers()
        self.note.open_note()
        self.activateWindow()
        self.setFocus()

    # -- radio -------------------------------------------------------------
    def _knob_device(self, part):
        s = self.radio.state
        if not s:
            return None
        return s.sink if part == "volume" else s.source

    def _set_volume(self, part, volume, force=True):
        dev = self._knob_device(part)
        if not dev:
            return
        dev.volume = max(0, min(100, int(round(volume))))
        self._audio_hold = time.monotonic() + 2.0
        now = time.monotonic()
        if force or now - self._last_knob_send > 0.06:  # don't flood pactl while dragging
            self._last_knob_send = now
            audio.set_volume("sink" if part == "volume" else "source", dev.volume)
        self.radio.update_tags()
        self.update(self.to_widget(self.radio.damage_rect()))
        if self.hover_gauge is self.radio.tags[part]:
            self.update(self.to_widget(self._gauge_tag_rect(self.hover_gauge).adjusted(-4, -4, 6, 6), fixed=True))

    def _drag_knob(self, pt):
        part, y0, v0, moved = self.knob_drag
        delta = (y0 - pt.y()) / 1.5  # drag up to turn it up
        if not moved and abs(delta) < 2:
            return
        self.knob_drag[3] = True
        self._set_volume(part, v0 + delta, force=False)

    def _toggle_mute(self, part):
        dev = self._knob_device(part)
        if not dev:
            self.notify("No speakers found" if part == "volume" else "No microphone found")
            return
        dev.muted = not dev.muted
        self._audio_hold = time.monotonic() + 2.0
        audio.set_mute("sink" if part == "volume" else "source", dev.muted)
        self.radio.update_tags()
        self.update(self.to_widget(self.radio.damage_rect()))
        if self.hover_gauge is self.radio.tags[part]:
            self.update(self.to_widget(self._gauge_tag_rect(self.hover_gauge).adjusted(-4, -4, 6, 6), fixed=True))

    def _device_menu(self):
        s = self.radio.state
        if not s or not s.available:
            self.notify("No audio devices found")
            return
        menu = QMenu(self)
        menu.setStyleSheet(DEVICE_MENU_STYLE)
        for kind, title, devices, current in (("sink", "Speakers", s.sinks, s.sink),
                                             ("source", "Microphone", s.sources, s.source)):
            header = menu.addAction(title)
            header.setEnabled(False)
            for dev in devices:
                act = QAction(dev.description, menu, checkable=True)
                act.setChecked(current is not None and dev.name == current.name)
                act.triggered.connect(lambda _, k=kind, n=dev.name: self._choose_device(k, n))
                menu.addAction(act)
            menu.addSeparator()
        anchor = self.to_widget(QRectF(desk.RADIO.left(), desk.RADIO.bottom(), 1, 1)).topLeft()
        menu.popup(self.mapToGlobal(anchor))

    def _choose_device(self, kind, name):
        audio.set_default(kind, name)
        self._poke.set()

    # -- desktop integration -------------------------------------------------
    def make_desktop_window(self):
        """Mark the window as the desktop so the window manager keeps it beneath everything."""
        if not shutil.which("xprop"):
            return
        subprocess.run(["xprop", "-id", str(int(self.winId())), "-f", "_NET_WM_WINDOW_TYPE", "32a",
                        "-set", "_NET_WM_WINDOW_TYPE", "_NET_WM_WINDOW_TYPE_DESKTOP"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
