"""A Tiffany-style stained glass desk lamp (after lamp_inspo*.jpeg). Clicking it opens the start menu.

The lamp is rendered per pixel with numpy, like the globe: the shade is a surface of revolution
covered in irregular hand-cut glass (a Voronoi pattern) joined by bronze lead lines, and the base
is a turned bronze lathe profile. Both are lit by the room lamp rather than shining themselves.
"""

import math

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QRadialGradient, QTransform

from .textures import _value_noise

CX = 262.0
SHADE_TOP = 344.0
SHADE_H = 158.0
SHADE_W = 256.0
RIM_CURVE = 14.0  # the bottom rim bows towards us
BASE_Y = 706.0
BOUNDS = QRectF(CX - 140, SHADE_TOP - 40, 280, BASE_Y - SHADE_TOP + 52)

# The constants above lay the lamp out at full size; it stands on the desk smaller and further back.
SCALE = 0.75
PLACE = QPointF(280, 628)  # where the centre of the foot touches the desk
TO_SCENE = QTransform().translate(PLACE.x(), PLACE.y()).scale(SCALE, SCALE).translate(-CX, -BASE_Y)
TO_LAYOUT = TO_SCENE.inverted()[0]
SCENE_BOUNDS = TO_SCENE.mapRect(BOUNDS)

_LIGHT = np.array([-0.45, -0.55, 0.70])  # room lamp: upper left, in front (y points down)
_LIGHT /= np.linalg.norm(_LIGHT)
_HALF = _LIGHT + np.array([0.0, 0.0, 1.0])
_HALF /= np.linalg.norm(_HALF)

# turned bronze profile of the stand and the finial: (scene y, radius)
_STAND = [(500, 11), (512, 9), (522, 6), (540, 7), (556, 12), (566, 12), (578, 8), (612, 7.5), (626, 13),
          (636, 13), (646, 9), (656, 11), (666, 17), (678, 28), (690, 46), (699, 62), (704, 68), (706, 66)]
_FINIAL = [(306, 0.5), (312, 3), (318, 2.5), (324, 6), (330, 4), (336, 9), (342, 15), (346, 16)]

_images = {}
_mask = None
_scale = None


def _half_width(v):
    v = np.minimum(v, 1.0)
    return SHADE_W / 2 * (0.12 + 0.88 * np.sqrt(np.clip(1 - (1 - v) ** 2, 0, 1)))


def _half_width_slope(v):
    v = np.clip(v, 0.0, 0.999)
    return SHADE_W / 2 * 0.88 * (1 - v) / np.sqrt(np.clip(1 - (1 - v) ** 2, 1e-4, 1))


def bounds():
    return SCENE_BOUNDS


def tag_point():
    """Where the hover label should hang from, in scene coordinates."""
    return TO_SCENE.map(QPointF(CX, SHADE_TOP + 20))


def menu_anchor():
    """Just right of the shade's rim, where the start menu opens."""
    return TO_SCENE.map(QPointF(CX + SHADE_W / 2, SHADE_TOP + SHADE_H))


def contains(pt):
    """Pixel-accurate hit test against the rendered lamp."""
    pt = TO_LAYOUT.map(pt)
    if _mask is None or not BOUNDS.contains(pt):
        return False
    h, w = _mask.shape
    j = int((pt.x() - BOUNDS.left()) / BOUNDS.width() * w)
    i = int((pt.y() - BOUNDS.top()) / BOUNDS.height() * h)
    return 0 <= i < h and 0 <= j < w and bool(_mask[i, j])


def paint_shadow(p):
    """Contact shadow under the foot; drawn in the static layer."""
    g = QRadialGradient(QPointF(CX + 10, BASE_Y + 2), 100)
    g.setColorAt(0, QColor(0, 0, 0, 180))
    g.setColorAt(1, QColor(0, 0, 0, 0))
    p.save()
    p.setTransform(TO_SCENE, True)
    p.setPen(Qt.PenStyle.NoPen)
    p.translate(0, (BASE_Y + 2) * (1 - 0.28))
    p.scale(1, 0.28)
    p.setBrush(g)
    p.drawEllipse(QPointF(CX + 10, BASE_Y + 2), 104, 104)
    p.restore()


def paint(p: QPainter, hover=False):
    img = _images.get(hover)
    if img is not None:
        p.save()
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(SCENE_BOUNDS, img)
        p.restore()


# --- rendering ----------------------------------------------------------------

def build(scale):
    """Render the lamp at device resolution (scene units * scale)."""
    global _mask, _scale
    scale *= SCALE  # the layout is drawn smaller than it is laid out
    if _scale == scale:
        return
    _scale = scale
    w = max(8, int(BOUNDS.width() * scale))
    h = max(8, int(BOUNDS.height() * scale))
    xs = BOUNDS.left() + (np.arange(w) + 0.5) / scale
    ys = BOUNDS.top() + (np.arange(h) + 0.5) / scale
    X, Y = np.meshgrid(xs, ys)

    base_rgb, base_a = _render_lathe(X, Y)
    for hover in (False, True):
        shade_rgb, shade_a = _render_shade(X, Y, glow=1.18 if hover else 1.0)
        rgb = shade_rgb * shade_a[..., None] + base_rgb * (base_a * (1 - shade_a))[..., None]
        alpha = shade_a + base_a * (1 - shade_a)
        rgba = np.zeros((h, w, 4), np.uint8)
        # premultiplied output
        rgba[..., :3] = np.clip(rgb * 255, 0, 255)
        rgba[..., 3] = np.clip(alpha * 255, 0, 255)
        _images[hover] = QImage(rgba.tobytes(), w, h, 4 * w, QImage.Format.Format_RGBA8888_Premultiplied).copy()
    _mask = (base_a + shade_a) > 0.5


def _profile(points, ys):
    py = np.array([q[0] for q in points], float)
    pr = np.array([q[1] for q in points], float)
    r = np.interp(ys, py, pr, left=0, right=0)
    # smooth the polyline so the turned shapes flow into each other
    k = np.exp(-np.linspace(-2, 2, 9) ** 2)
    k /= k.sum()
    return np.convolve(np.pad(r, 4, mode="edge"), k, mode="valid")


def _render_lathe(X, Y):
    """Turned bronze: the stand below the shade and the finial on top."""
    ys = Y[:, 0]
    step = ys[1] - ys[0] if len(ys) > 1 else 1.0
    r = np.maximum(_profile(_STAND, ys), _profile(_FINIAL, ys))
    dr = np.gradient(r, step)
    R = r[:, None]
    s = np.where(R > 0.3, (X - CX) / np.maximum(R, 1e-3), 2.0)
    inside = np.abs(s) < 1.0
    s = np.clip(s, -0.999, 0.999)
    theta = np.arcsin(s)
    # decorative ribs cast into the foot
    rib = np.where(Y > 662, 0.12 * np.sin(theta * 16), 0.0)
    slope = np.arctan(dr)[:, None]
    nx = np.sin(theta + rib) * np.cos(slope)
    ny = np.sin(slope) * np.ones_like(theta)
    nz = np.cos(theta + rib) * np.cos(slope)
    n = np.stack([nx, ny, nz], -1)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)
    rng = np.random.default_rng(4)
    patina = _value_noise(*X.shape, 24, 12, rng)
    grime = _value_noise(*X.shape, 90, 30, rng)
    bronze = np.array([0.42, 0.28, 0.14])
    green = np.array([0.20, 0.22, 0.14])
    albedo = bronze * (1 - 0.45 * patina[..., None]) + green * 0.35 * patina[..., None] ** 2
    albedo *= (0.85 + 0.3 * grime)[..., None]
    # matte, low-contrast shading to match the flatter brass and bronze fittings elsewhere on the desk
    diffuse = np.clip(n @ _LIGHT, 0, 1)
    rgb = albedo * (0.75 + 0.55 * diffuse)[..., None]
    rgb += (np.clip(n @ _HALF, 0, 1) ** 6 * 0.08)[..., None] * np.array([1.0, 0.86, 0.66])
    # soft silhouette
    edge = np.clip((1 - np.abs(s)) * R * _scale * 0.8, 0, 1)
    return rgb, inside * edge


def _render_shade(X, Y, glow=1.0):
    # invert the shade mapping: scene point -> (u across the dome, v from crown to rim)
    v = (Y - SHADE_TOP) / SHADE_H
    u = np.zeros_like(v)
    for _ in range(5):
        hw = _half_width(np.clip(v, 0, 1))
        u = (X - CX) / hw
        v = (Y - SHADE_TOP - RIM_CURVE * np.clip(v, 0, 1) ** 2 * (1 - np.clip(u, -1, 1) ** 2)) / SHADE_H
    inside = (v >= 0) & (v <= 1) & (np.abs(u) <= 1)
    u = np.clip(u, -0.9999, 0.9999)
    vc = np.clip(v, 0, 1)
    theta = np.arcsin(u)

    # surface normal of the dome
    hw = _half_width(vc)
    dhw = _half_width_slope(vc)
    d_theta = np.stack([hw * np.cos(theta), np.zeros_like(theta), -hw * np.sin(theta)], -1)
    d_v = np.stack([dhw * np.sin(theta), np.full_like(theta, SHADE_H), dhw * np.cos(theta)], -1)
    n = np.cross(d_theta, d_v)
    n *= np.sign(n[..., 2:3] + 1e-9)
    n /= np.linalg.norm(n, axis=-1, keepdims=True)

    # irregular glass pieces: Voronoi cells over (around, down) coordinates
    gx = theta * 9.5
    gy = vc * 13.0
    color, lead, cell_rand = _voronoi_glass(gx, gy, theta, vc)

    rng = np.random.default_rng(11)
    shape = X.shape
    streak = _value_noise(*shape, 18, 90, rng)  # long streaks in the glass
    milk = _value_noise(*shape, 10, 14, rng)  # opalescent cloudiness
    seeds = _value_noise(*shape, 60, 60, rng)  # tiny bubbles and texture
    texture = 0.82 + 0.28 * streak + 0.08 * seeds
    glass = color * texture[..., None]
    glass = glass * (1 - 0.14 * milk[..., None]) + 0.14 * milk[..., None] * np.array([0.96, 0.90, 0.78])

    lam = np.clip(n @ _LIGHT, 0, 1)
    nh = np.clip(n @ _HALF, 0, 1)
    fresnel = (1 - np.clip(n[..., 2], 0, 1)) ** 3
    # backlit: a bulb inside makes the glass glow, brightest low down in the middle of the shade
    inner = np.clip(vc, 0, 1) ** 1.4 * (1 - 0.45 * np.abs(u))
    through = (0.78 + 0.42 * inner + 0.14 * streak) * glow
    # glass barely scatters light, so most of the room lamp shows up as a crisp reflection
    rgb = glass * (through + 0.10 * lam)[..., None]
    rgb *= (1 - 0.25 * fresnel)[..., None]  # the dome darkens slightly as it curves away

    # lead came: dark patinated bronze with its own sheen, plus a solid rim band and crown ring
    lead = np.maximum(lead, (vc > 0.975) * 1.0)
    lead = np.maximum(lead, (vc < 0.035) * 1.0)
    lead_rgb = np.array([0.20, 0.14, 0.08]) * (0.7 + 0.5 * lam)[..., None]
    rgb = rgb * (1 - lead[..., None]) + lead_rgb * lead[..., None]

    # anti-aliased silhouette
    px = 1.0 / _scale
    edge_u = np.clip((1 - np.abs(u)) * hw / px * 0.9, 0, 1)
    edge_v = np.clip(np.minimum(v, 1 - v) * SHADE_H / px * 0.9, 0, 1)
    alpha = inside * edge_u * edge_v
    return rgb, alpha


def _hash(ix, iy, k):
    h = np.sin(ix * 127.1 + iy * 311.7 + k * 74.7) * 43758.5453
    return h - np.floor(h)


def _voronoi_glass(gx, gy, theta, v):
    """Nearest-seed search on a jittered grid; returns piece colour, lead mask and a per-piece random."""
    cx = np.floor(gx)
    cy = np.floor(gy)
    best = np.full(gx.shape, 1e9)
    second = np.full(gx.shape, 1e9)
    seed_x = np.zeros_like(gx)
    seed_y = np.zeros_like(gy)
    for oy in (-1, 0, 1):
        for ox in (-1, 0, 1):
            ix, iy = cx + ox, cy + oy
            sx = ix + 0.15 + 0.7 * _hash(ix, iy, 1)
            sy = iy + 0.15 + 0.7 * _hash(ix, iy, 2)
            d = np.hypot(gx - sx, (gy - sy) * 1.1)
            closer = d < best
            second = np.where(closer, best, np.minimum(second, d))
            seed_x = np.where(closer, sx, seed_x)
            seed_y = np.where(closer, sy, seed_y)
            best = np.where(closer, d, best)
    # lead lines where the two nearest seeds are almost equally close
    width = 0.07
    lead = np.clip((width - (second - best)) / 0.03, 0, 1)
    rand = _hash(np.floor(seed_x * 7.3), np.floor(seed_y * 5.1), 3)
    color = _design(seed_x / 9.5, seed_y / 13.0, rand)
    return color, lead, rand


def _design(theta, v, rand):
    """The pattern, sampled at each piece's seed: red blossoms and green leaves on blue, violet and green glass."""
    period = math.pi / 3  # six blossoms around the shade
    phase = (theta + period / 2) % period - period / 2
    dx = phase * (0.45 + 0.55 * v) * 3.2
    dy = (v - 0.58) * 1.0
    d_flower = np.hypot(dx, dy)
    # background: cobalt blue, violet and sea-green pieces, lighter near the crown, deeper towards the rim
    t = np.clip((v - 0.1) / 0.75, 0, 1)[..., None]
    blue = np.array([0.40, 0.54, 0.92]) * (1 - t) + np.array([0.16, 0.26, 0.74]) * t
    violet = np.array([0.62, 0.44, 0.86]) * (1 - t) + np.array([0.40, 0.18, 0.66]) * t
    green = np.array([0.40, 0.74, 0.52]) * (1 - t) + np.array([0.14, 0.50, 0.32]) * t
    col = np.where((rand > 0.62)[..., None], violet, np.where((rand > 0.34)[..., None], blue, green))
    # leaves either side of each blossom
    for side in (-1, 1):
        lx = dx - side * 0.23
        ly = dy + 0.07 * side - lx * side * 0.6
        leaf = (lx / 0.14) ** 2 + (ly / 0.06) ** 2 < 1
        col = np.where(leaf[..., None], np.where((rand > 0.5)[..., None], [0.16, 0.52, 0.22], [0.34, 0.68, 0.30]), col)
    # vine running around the shade under the blossoms
    vine = np.abs(v - (0.74 + 0.04 * np.sin(theta * 12))) < 0.028
    col = np.where(vine[..., None], [0.12, 0.40, 0.18], col)
    petals = d_flower < 0.15
    col = np.where(petals[..., None], np.where((rand > 0.45)[..., None], [0.80, 0.08, 0.14], [0.94, 0.24, 0.26]), col)
    heart = d_flower < 0.045
    col = np.where(heart[..., None], [0.98, 0.48, 0.58], col)
    # crown and border
    col = np.where((v < 0.1)[..., None], [0.36, 0.16, 0.50], col)
    border = v > 0.86
    col = np.where(border[..., None], np.where((rand > 0.66)[..., None], [0.62, 0.06, 0.12],
                                              np.where((rand > 0.33)[..., None], [0.10, 0.44, 0.24], [0.14, 0.18, 0.56])), col)
    # every piece of glass is a little different
    jitter = (0.86 + 0.26 * rand)[..., None]
    return np.clip(col * jitter, 0, 1)
