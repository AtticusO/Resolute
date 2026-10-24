"""Surface textures.

Wood and leather come from photographed CC0 materials in assets/ (see assets/CREDITS.md).
Each one is lit once at start-up with its own normal and roughness maps, so pores and grain
pick up the lamp the way a satin finish does. Felt and wallpaper are still generated with numpy.
"""

from pathlib import Path

import numpy as np
from PyQt6.QtGui import QImage, QPixmap

ASSETS = Path(__file__).parent / "assets"

# Lamp direction in normal-map space (+x right, +y up, +z out of the surface): upper left.
_LIGHT = np.array([-0.45, 0.5, 0.75])
_LIGHT /= np.linalg.norm(_LIGHT)
_HALF = _LIGHT + np.array([0.0, 0.0, 1.0])
_HALF /= np.linalg.norm(_HALF)

_cache = {}


def _value_noise(h, w, cells_y, cells_x, rng):
    """Smooth, tileable 2D value noise in [0, 1] (the random grid wraps at the edges)."""
    grid = rng.random((cells_y, cells_x))
    ys = np.linspace(0, cells_y, h, endpoint=False)
    xs = np.linspace(0, cells_x, w, endpoint=False)
    y0 = ys.astype(int)
    x0 = xs.astype(int)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    fy = fy * fy * (3 - 2 * fy)
    fx = fx * fx * (3 - 2 * fx)
    y1 = (y0 + 1) % cells_y
    x1 = (x0 + 1) % cells_x
    a = grid[y0][:, x0]
    b = grid[y0][:, x1]
    c = grid[y1][:, x0]
    d = grid[y1][:, x1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def _to_pixmap(rgb):
    rgb = np.ascontiguousarray(np.clip(rgb, 0, 255).astype(np.uint8))
    h, w, _ = rgb.shape
    img = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
    return QPixmap.fromImage(img)


def _read(path):
    """Load an image as a float RGB array in [0, 1]."""
    img = QImage(str(path)).convertToFormat(QImage.Format.Format_RGB888)
    if img.isNull():
        raise FileNotFoundError(path)
    ptr = img.constBits()
    ptr.setsize(img.bytesPerLine() * img.height())
    arr = np.frombuffer(ptr, np.uint8).reshape(img.height(), img.bytesPerLine())
    return arr[:, :img.width() * 3].reshape(img.height(), img.width(), 3).astype(np.float32) / 255.0


def _material(name, tint=(1.0, 1.0, 1.0), brightness=1.0, relief=0.6, sheen=0.12):
    """Light a photographed material with its own normal and roughness maps.

    relief: how strongly the lamp picks out pores and grain (0 = flat photo).
    sheen:  strength of the satin highlight where the finish is smooth.
    """
    key = ("material", name, tint, brightness, relief, sheen)
    if key not in _cache:
        color = _read(ASSETS / f"{name}_color.jpg")
        normal = _read(ASSETS / f"{name}_normal.jpg") * 2 - 1
        rough = _read(ASSETS / f"{name}_roughness.jpg")[..., 0]
        normal[..., :2] *= relief
        normal /= np.linalg.norm(normal, axis=2, keepdims=True)
        diffuse = np.clip(normal @ _LIGHT, 0, 1) / _LIGHT[2]  # 1.0 on a flat patch
        spec = (1 - rough) ** 2 * np.clip(normal @ _HALF, 0, 1) ** 24 * sheen
        rgb = color * np.array(tint) * brightness * diffuse[..., None] + spec[..., None] * np.array([1.0, 0.9, 0.78])
        _cache[key] = rgb * 255
    return _cache[key]


def _pixmap(key, rgb, vertical=False):
    k = (key, vertical)
    if k not in _cache:
        _cache[k] = _to_pixmap(np.rot90(rgb) if vertical else rgb)
    return _cache[k]


# Dark walnut for the whole desk, warmed slightly towards the reddish tone of desk_inspo.jpg.
_DESK = dict(tint=(1.1, 0.96, 0.9), brightness=1.05)


def desk_wood(vertical=False):
    """The desk's main wood: drawer fronts, frame, sides, organiser."""
    return _pixmap("desk_wood", _material("desk_wood", **_DESK), vertical)


def desk_top():
    """The writing surface: same boards, with a little less relief since it is seen at a low angle."""
    return _pixmap("desk_top", _material("desk_wood", relief=0.4, sheen=0.08, **_DESK))


def desk_wood_dark(vertical=False):
    """Shadowed interior wood for the back of the roll-top and the drawer boxes."""
    return _pixmap("desk_wood_dark", _material("desk_wood", tint=_DESK["tint"], brightness=0.45, sheen=0.04), vertical)


def stand_wood():
    """Lighter, plainer wood for the gauge stand so it reads as a separate object."""
    return _pixmap("stand_wood", _material("stand_wood", tint=(1.18, 0.98, 0.84), brightness=1.35, sheen=0.1))


def leather():
    """Oxblood leather for the writing pad."""
    return _pixmap("leather", _material("leather", tint=(1.0, 0.6, 0.56), brightness=0.82, relief=0.8, sheen=0.06))


def wallpaper():
    """Dark green study wallpaper with a faint vertical stripe."""
    if "wall" not in _cache:
        rng = np.random.default_rng(5)
        h, w = 512, 512
        n = _value_noise(h, w, 8, 8, rng)
        x = np.arange(w)[None, :].astype(float)
        stripe = (np.sin(x * 2 * np.pi / 64) * 0.5 + 0.5) ** 8
        t = np.clip(0.55 * n + 0.25 * stripe, 0, 1)[..., None]
        dark = np.array((14, 26, 22), float)
        light = np.array((30, 48, 40), float)
        rgb = dark * (1 - t) + light * t
        _cache["wall"] = _to_pixmap(np.broadcast_to(rgb, (h, w, 3)))
    return _cache["wall"]


def felt():
    """Green baize drawer lining."""
    if "felt" not in _cache:
        rng = np.random.default_rng(9)
        h, w = 256, 256
        t = (0.6 * _value_noise(h, w, 128, 128, rng) + 0.4 * _value_noise(h, w, 8, 8, rng))[..., None]
        dark = np.array((22, 52, 34), float)
        light = np.array((44, 86, 58), float)
        _cache["felt"] = _to_pixmap(dark * (1 - t) + light * t)
    return _cache["felt"]
