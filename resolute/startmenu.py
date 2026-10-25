"""The start menu that opens from the red power button."""

import configparser
import getpass
import os
import shutil
import socket
from pathlib import Path

from PyQt6.QtCore import QMimeData, QPoint, QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QDrag, QIcon
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
                             QMessageBox, QPushButton, QVBoxLayout, QWidget)

from . import system

CATEGORY_ORDER = ["All", "Accessories", "Office", "Internet", "Development", "Graphics",
                  "Multimedia", "Security Tools", "System", "Settings", "Other"]

STYLE = """
#StartMenu {
    background: #efe4c8;
    border: 7px solid #6b3418;
    border-radius: 12px;
}
#Header { background: #5a2a12; border-top-left-radius: 5px; border-top-right-radius: 5px; }
#Title { color: #f3d98f; font-family: 'C059'; font-size: 22px; font-weight: bold; letter-spacing: 4px; }
#Subtitle { color: #e8d4b0; font-family: 'C059'; font-size: 12px; font-style: italic; }
QLineEdit {
    background: #fbf6e8; border: 1px solid #a8885a; border-radius: 4px;
    padding: 6px 8px; font-family: 'C059'; font-size: 14px; color: #3a2a1c;
}
QListWidget {
    background: transparent; border: none; outline: none;
    font-family: 'C059'; font-size: 14px; color: #3a2a1c;
}
QListWidget::item { padding: 5px 6px; border-radius: 4px; }
QListWidget::item:hover { background: #e2cf9e; }
QListWidget::item:selected { background: #c9a55a; color: #2a1a0c; }
#Categories { border-right: 1px solid #c8b088; }
#Footer { border-top: 1px solid #c8b088; }
#Footer QPushButton {
    background: #e6d6ae; border: 1px solid #a8885a; border-radius: 4px;
    padding: 6px 10px; font-family: 'C059'; font-size: 13px; color: #3a2a1c;
}
#Footer QPushButton:hover { background: #d9c08a; }
#Footer QPushButton#Danger { background: #b5281c; color: #fbeee6; border-color: #7a140c; }
#Footer QPushButton#Danger:hover { background: #d23422; }
#Footer QPushButton#Quiet { background: transparent; border: none; color: #7a5a3a; font-style: italic; }
"""


class AppEntry:
    def __init__(self, path, name, comment, icon, category, keywords, wm_class="", exec_name=""):
        self.path = path
        self.wm_class = wm_class
        self.exec_name = exec_name
        self.name = name
        self.comment = comment
        self.icon = icon
        self.category = category
        self.search = " ".join((name, comment, keywords, path.stem)).lower()


def _category(cats):
    if any(c.startswith("kali-") or c.startswith("X-Kali") for c in cats):
        return "Security Tools"
    if {"Settings", "DesktopSettings", "X-XFCE-SettingsDialog", "HardwareSettings"} & cats:
        return "Settings"
    for names, label in ((("Office",), "Office"), (("Network", "WebBrowser"), "Internet"),
                         (("Development",), "Development"), (("Graphics",), "Graphics"),
                         (("AudioVideo", "Audio", "Video"), "Multimedia"), (("System",), "System"),
                         (("Utility", "Accessories", "TextEditor"), "Accessories")):
        if set(names) & cats:
            return label
    return "Other"


def _parse(path):
    """Read a launcher (.desktop) file: its [Desktop Entry] section, or None if it can't be read."""
    cp = configparser.ConfigParser(interpolation=None, strict=False)
    cp.optionxform = str
    try:
        cp.read(path, encoding="utf-8")
        return cp["Desktop Entry"]
    except (configparser.Error, KeyError, UnicodeDecodeError, OSError):
        return None


def _entry(path, e):
    cats = {c for c in e.get("Categories", "").split(";") if c}
    exec_words = e.get("Exec", "").split()
    return AppEntry(path, e.get("Name", path.stem), e.get("Comment", ""),
                    e.get("Icon", ""), _category(cats), e.get("Keywords", ""),
                    e.get("StartupWMClass", ""), os.path.basename(exec_words[0]) if exec_words else "")


def desktop_entry(path):
    """The application a launcher file starts, or None if it isn't an application launcher."""
    e = _parse(path)
    if e is None or e.get("Type") != "Application":
        return None
    return _entry(Path(path), e)


def load_applications():
    desktop_env = {d for d in os.environ.get("XDG_CURRENT_DESKTOP", "XFCE").split(":") if d}
    seen = {}
    for base in system._application_dirs():
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.desktop")):
            file_id = str(path.relative_to(base)).replace("/", "-")
            if file_id in seen:  # earlier directories take priority
                continue
            seen[file_id] = None
            e = _parse(path)
            if e is None:
                continue
            if e.get("Type") != "Application" or e.get("NoDisplay") == "true" or e.get("Hidden") == "true":
                continue
            only = {s for s in e.get("OnlyShowIn", "").split(";") if s}
            never = {s for s in e.get("NotShowIn", "").split(";") if s}
            if (only and not only & desktop_env) or never & desktop_env:
                continue
            try_exec = e.get("TryExec")
            if try_exec and not shutil.which(try_exec):
                continue
            seen[file_id] = _entry(path, e)
    apps = [a for a in seen.values() if a]
    apps.sort(key=lambda a: a.name.lower())
    return apps


def icon_for_window(wm_instance, wm_class, _index={}):
    """Find a program window's icon via the launcher entry that started it."""
    if not _index:
        for app in load_applications():
            for key in (app.wm_class, app.path.stem, app.exec_name, app.name):
                if key and app.icon:
                    _index.setdefault(key.lower(), app.icon)
        _index[""] = ""
    for key in (wm_class, wm_instance):
        k = key.lower()
        name = _index.get(k) or _index.get(k.split(".")[-1]) or _index.get(k.split("-")[0])
        if name:
            return icon_named(name)
    for key in (wm_instance, wm_class):
        icon = QIcon.fromTheme(key.lower())
        if key and not icon.isNull():
            return icon
    return QIcon.fromTheme("application-x-executable")


def icon_named(name):
    if not name:
        return QIcon.fromTheme("application-x-executable")
    if os.path.isabs(name):
        return QIcon(name)
    icon = QIcon.fromTheme(name)
    return icon if not icon.isNull() else QIcon.fromTheme("application-x-executable")


class _AppList(QListWidget):
    """The application list. Entries can be dragged out onto the desk as launcher files."""

    def mimeTypes(self):
        return ["text/uri-list"]

    def mimeData(self, items):
        data = QMimeData()
        data.setUrls([QUrl.fromLocalFile(it.data(Qt.ItemDataRole.UserRole)) for it in items])
        return data

    def startDrag(self, actions):
        item = self.currentItem()
        if item is None:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([item]))
        drag.setPixmap(item.icon().pixmap(48, 48))  # carry just the icon, not the whole highlighted row
        drag.setHotSpot(QPoint(24, 24))
        drag.exec(Qt.DropAction.CopyAction)  # a copy, so the entry stays in the list


class StartMenu(QFrame):
    quit_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("StartMenu")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setStyleSheet(STYLE)
        self.setFixedSize(640, 560)
        self.apps = []
        self._icons = {}

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        header = QWidget(objectName="Header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(18, 12, 18, 10)
        hl.setSpacing(0)
        hl.addWidget(QLabel("RESOLUTE", objectName="Title"))
        hl.addWidget(QLabel(f"{getpass.getuser()} at {socket.gethostname()}", objectName="Subtitle"))
        outer.addWidget(header)

        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 8)
        body.setSpacing(10)
        self.search = QLineEdit(placeholderText="Search applications…")
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._launch_first)
        body.addWidget(self.search)

        lists = QHBoxLayout()
        lists.setSpacing(8)
        self.categories = QListWidget(objectName="Categories")
        self.categories.setFixedWidth(160)
        self.categories.currentRowChanged.connect(lambda _: self._filter())
        self.app_list = _AppList()
        self.app_list.setIconSize(QSize(22, 22))
        self.app_list.setDragEnabled(True)
        self.app_list.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.app_list.itemActivated.connect(self._launch_item)
        self.app_list.itemClicked.connect(self._launch_item)
        lists.addWidget(self.categories)
        lists.addWidget(self.app_list, 1)
        body.addLayout(lists, 1)
        outer.addLayout(body, 1)

        footer = QWidget(objectName="Footer")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 10, 14, 12)
        fl.setSpacing(8)
        quit_btn = QPushButton("Close desk", objectName="Quiet")
        quit_btn.clicked.connect(self._quit_desk)
        fl.addWidget(quit_btn)
        fl.addStretch(1)
        for label, action, confirm, name in (
                ("Lock", system.lock, None, None),
                ("Sleep", system.suspend, None, None),
                ("Log Out", system.logout, "Log out of this session?", None),
                ("Restart", system.reboot, "Restart the computer?", None),
                ("Shut Down", system.poweroff, "Shut down the computer?", "Danger")):
            btn = QPushButton(label)
            if name:
                btn.setObjectName(name)
            btn.clicked.connect(lambda _, a=action, c=confirm, l=label: self._power(a, c, l))
            fl.addWidget(btn)
        outer.addWidget(footer)

    # -- behaviour ---------------------------------------------------------
    def popup_at(self, global_pos):
        self.apps = load_applications()
        present = {a.category for a in self.apps}
        self.categories.blockSignals(True)
        self.categories.clear()
        for cat in CATEGORY_ORDER:
            if cat == "All" or cat in present:
                self.categories.addItem(cat)
        self.categories.setCurrentRow(0)
        self.categories.blockSignals(False)
        self.search.clear()
        self._filter()
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = global_pos.x(), global_pos.y() - self.height()
        if screen:
            x = max(screen.left(), min(x, screen.right() - self.width()))
            y = max(screen.top(), min(y, screen.bottom() - self.height()))
        self.move(x, y)
        self.show()
        self.search.setFocus()

    def _filter(self):
        text = self.search.text().strip().lower()
        item = self.categories.currentItem()
        cat = item.text() if item else "All"
        self.app_list.clear()
        for app in self.apps:
            if text:
                if not all(word in app.search for word in text.split()):
                    continue
            elif cat != "All" and app.category != cat:
                continue
            if app.icon not in self._icons:
                self._icons[app.icon] = icon_named(app.icon)
            it = QListWidgetItem(self._icons[app.icon], app.name)
            it.setToolTip(app.comment)
            it.setData(Qt.ItemDataRole.UserRole, str(app.path))
            self.app_list.addItem(it)

    def _launch_item(self, item):
        system.launch_desktop_file(Path(item.data(Qt.ItemDataRole.UserRole)))
        self.hide()

    def _launch_first(self):
        if self.app_list.count():
            self._launch_item(self.app_list.item(0))

    def _confirm(self, question, label):
        box = QMessageBox(QMessageBox.Icon.Question, label, question,
                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        box.setStyleSheet("QMessageBox { background: #efe4c8; } QLabel { font-family: 'C059'; font-size: 15px; color: #3a2a1c; }")
        box.button(QMessageBox.StandardButton.Yes).setText(label)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _power(self, action, confirm, label):
        self.hide()
        if confirm is None or self._confirm(confirm, label):
            action()

    def _quit_desk(self):
        self.hide()
        if self._confirm("Close the Resolute desk? Your open programs stay running.", "Close desk"):
            self.quit_requested.emit()


class AppPicker(QFrame):
    """A small pop-up list of the installed applications to choose one from."""
    picked = pyqtSignal(str)  # the launcher file of the chosen application

    def __init__(self, title, parent=None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setObjectName("StartMenu")
        self.setStyleSheet(STYLE)
        self.setFixedSize(380, 480)
        self.apps = []
        self._icons = {}
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        header = QWidget(objectName="Header")
        hl = QVBoxLayout(header)
        hl.setContentsMargins(16, 10, 16, 8)
        self.title = QLabel(title, objectName="Subtitle")
        hl.addWidget(self.title)
        outer.addWidget(header)
        body = QVBoxLayout()
        body.setContentsMargins(12, 10, 12, 12)
        body.setSpacing(8)
        self.search = QLineEdit(placeholderText="Search applications…")
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(self._pick_first)
        body.addWidget(self.search)
        self.app_list = QListWidget()
        self.app_list.setIconSize(QSize(22, 22))
        self.app_list.itemActivated.connect(self._pick)
        self.app_list.itemClicked.connect(self._pick)
        body.addWidget(self.app_list, 1)
        outer.addLayout(body, 1)

    def popup_at(self, global_pos, title=None):
        if title:
            self.title.setText(title)
        self.apps = load_applications()
        self.search.clear()
        self._filter()
        screen = self.screen().availableGeometry() if self.screen() else None
        x, y = global_pos.x(), global_pos.y()
        if screen:
            x = max(screen.left(), min(x, screen.right() - self.width()))
            y = max(screen.top(), min(y, screen.bottom() - self.height()))
        self.move(x, y)
        self.show()
        self.search.setFocus()

    def _filter(self):
        text = self.search.text().strip().lower()
        self.app_list.clear()
        for app in self.apps:
            if text and not all(word in app.search for word in text.split()):
                continue
            if app.icon not in self._icons:
                self._icons[app.icon] = icon_named(app.icon)
            it = QListWidgetItem(self._icons[app.icon], app.name)
            it.setToolTip(app.comment)
            it.setData(Qt.ItemDataRole.UserRole, str(app.path))
            self.app_list.addItem(it)

    def _pick(self, item):
        self.hide()
        self.picked.emit(item.data(Qt.ItemDataRole.UserRole))

    def _pick_first(self):
        if self.app_list.count():
            self._pick(self.app_list.item(0))
