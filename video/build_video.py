#!/usr/bin/env python3
"""Synthesize the RD-03D stair-radar video: frames via PIL, encode via ffmpeg.

  build_video.py preview            -> PNG stills per shot into preview/
  build_video.py render <shotkey>   -> seg/<shotkey>.mp4 (video + narration)
  build_video.py concat             -> final.mp4
"""
import json, math, os, re, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from stl import mesh as stlmesh

VARIANT = os.environ.get("RD_VARIANT", "")          # "" = internal, "hackaday" = public
if VARIANT == "hackaday":
    from narration_hackaday import SHOTS
else:
    from narration import SHOTS
SUFFIX = ("_" + VARIANT) if VARIANT else ""

W, H, FPS = 1920, 1080, 30
LEAD = 0.6          # narration delay (s) at the start of each shot
TAIL = 0.9          # silence after narration
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/path/to/rd03d"
FFMPEG = "/opt/homebrew/bin/ffmpeg"
AUDIO_DIR = os.path.join(HERE, "audio" + SUFFIX)
SEG_DIR = os.path.join(HERE, "seg" + SUFFIX)
DUR = json.load(open(os.path.join(AUDIO_DIR, "durations.json")))
TEXT = {k: t for k, _, t in SHOTS}
TITLE = {k: n for k, n, _ in SHOTS}

BG = (18, 18, 18); FG = (221, 221, 221); DIM = (130, 130, 130); DIM2 = (70, 70, 70)
C1 = (0, 180, 255); C2 = (0, 220, 120); C3 = (255, 180, 40)
RED = (255, 107, 107); GREEN = (76, 212, 122); YEL = (255, 214, 10)
PANE = (30, 30, 30); PANE2 = (38, 38, 38)
CODE_FG = (212, 212, 212); CODE_CM = (106, 153, 85); CODE_KW = (86, 156, 214)
CODE_STR = (206, 145, 120); CODE_NUM = (181, 206, 168)
PLATE_COL = (165, 172, 185); SHELL_COL = (120, 165, 200)

HN = "/System/Library/Fonts/HelveticaNeue.ttc"
MENLO = "/System/Library/Fonts/Menlo.ttc"
_fc = {}
def font(size, bold=False, mono=False, light=False):
    key = (size, bold, mono, light)
    if key not in _fc:
        if mono:
            _fc[key] = ImageFont.truetype(MENLO, size, index=1 if bold else 0)
        else:
            idx = 1 if bold else (7 if light else 0)
            _fc[key] = ImageFont.truetype(HN, size, index=idx)
    return _fc[key]

# ----------------------------------------------------------------- helpers
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def lerp(a, b, u): return a + (b - a) * u
def ease(u): u = clamp(u); return u * u * (3 - 2 * u)
def seg(t, t0, t1): return ease((t - t0) / max(1e-6, (t1 - t0)))
def mix(c, d, u): return tuple(int(round(lerp(c[i], d[i], u))) for i in range(3))

def cue(key, sub, offset=0.0):
    """Approximate time at which the narration reaches `sub` (char-proportional)."""
    txt = TEXT[key]; i = txt.index(sub)
    return LEAD + DUR[key] * (i / len(txt)) + offset

def shot_len(key): return DUR[key] + LEAD + TAIL

def new_frame(): return Image.new("RGB", (W, H), BG)

def fade(img, t, dur, fin=0.7, fout=0.7):
    a = 1.0
    if t < fin: a = t / fin
    if t > dur - fout: a = min(a, (dur - t) / fout)
    a = clamp(a)
    if a >= 0.999: return img
    return Image.blend(Image.new("RGB", (W, H), BG), img, a)

def wrap(s, fnt, maxw):
    words = s.split(); lines = []; cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if fnt.getlength(trial) <= maxw or not cur: cur = trial
        else: lines.append(cur); cur = w
    if cur: lines.append(cur)
    return lines

def paragraph(d, xy, s, fnt, fill, maxw, lh=None):
    x, y = xy; lh = lh or int(fnt.size * 1.35)
    for ln in wrap(s, fnt, maxw):
        d.text((x, y), ln, font=fnt, fill=fill); y += lh
    return y

def caption(d, s, side="left"):
    f = font(24, light=True)
    if side == "left": d.text((40, H - 50), s, font=f, fill=DIM)
    else: d.text((W - 40 - f.getlength(s), H - 50), s, font=f, fill=DIM)

def chapter(d, key, t, n):
    """Lower-third chapter label for the first seconds of a shot."""
    if t > 5.5: return
    a = seg(t, 0.3, 1.0) * (1 - seg(t, 4.6, 5.4))
    if a <= 0: return
    col = mix(BG, FG, a); col2 = mix(BG, DIM, a)
    d.rectangle((40, 60, 46, 118), fill=mix(BG, C1, a))
    d.text((62, 56), "%d" % n, font=font(22, light=True), fill=col2)
    d.text((62, 80), TITLE[key], font=font(32, bold=True), fill=col)

def rrect(d, box, r, fill=None, outline=None, width=1):
    d.rounded_rectangle(box, radius=r, fill=fill, outline=outline, width=width)

def arrow(d, p0, p1, fill, width=3, head=12):
    d.line([p0, p1], fill=fill, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    for s in (+1, -1):
        q = (p1[0] - head * math.cos(ang + s * 0.45), p1[1] - head * math.sin(ang + s * 0.45))
        d.line([p1, q], fill=fill, width=width)

def dim_line(d, p0, p1, label, fill=DIM, fnt=None, offset=(0, -8)):
    fnt = fnt or font(22)
    d.line([p0, p1], fill=fill, width=2)
    for p in (p0, p1):
        if abs(p1[1] - p0[1]) < abs(p1[0] - p0[0]):
            d.line([(p[0], p[1] - 8), (p[0], p[1] + 8)], fill=fill, width=2)
        else:
            d.line([(p[0] - 8, p[1]), (p[0] + 8, p[1])], fill=fill, width=2)
    mx, my = (p0[0] + p1[0]) / 2 + offset[0], (p0[1] + p1[1]) / 2 + offset[1]
    tw = fnt.getlength(label)
    d.text((mx - tw / 2, my - fnt.size), label, font=fnt, fill=fill)

# ----------------------------------------------------------------- STL renderer
_meshes = {}
def load(name):
    if name not in _meshes:
        m = stlmesh.Mesh.from_file(os.path.join(ROOT, "case", name))
        _meshes[name] = m.vectors.astype(np.float64)
    return _meshes[name]

def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])
def view(az_deg, elev_deg):
    return rot_x(math.radians(elev_deg)) @ rot_x(-math.pi / 2) @ rot_z(math.radians(az_deg))

LIGHT = np.array([-0.45, 0.55, 1.0]); LIGHT /= np.linalg.norm(LIGHT)

def render_meshes(d, parts, R, scale, center, pivot=(0, 0, 0)):
    """parts: list of (tris(N,3,3) in model mm, colour, pre(3x3) or None, offset(3,)).
    colour is an RGB tuple for the whole part or an (N,3) per-triangle array."""
    allp = []; cols = []
    for tris, col, pre, off in parts:
        v = tris.reshape(-1, 3).astype(float)
        if pre is not None: v = v @ pre.T
        v = v + np.asarray(off, float)
        v = (v - np.asarray(pivot, float)) @ R.T
        v = v.reshape(-1, 3, 3)
        n = np.cross(v[:, 1] - v[:, 0], v[:, 2] - v[:, 0])
        ln = np.linalg.norm(n, axis=1); ok = ln > 1e-9
        n[ok] /= ln[ok][:, None]
        face = n[:, 2] > 0.0
        v = v[face]; n = n[face]
        shade = 0.32 + 0.68 * np.clip(n @ LIGHT, 0, 1)
        colarr = np.asarray(col, float)
        if colarr.ndim == 1: colarr = np.broadcast_to(colarr, (len(face), 3))
        colarr = colarr[face]
        allp.append(v); cols.append(shade[:, None] * colarr)
    if not allp: return
    v = np.concatenate(allp); c = np.concatenate(cols)
    order = np.argsort(v[:, :, 2].mean(axis=1))
    cx, cy = center
    sx = cx + v[:, :, 0] * scale; sy = cy - v[:, :, 1] * scale
    for i in order:
        col = tuple(int(x) for x in np.clip(c[i], 0, 255))
        d.polygon([(sx[i, 0], sy[i, 0]), (sx[i, 1], sy[i, 1]), (sx[i, 2], sy[i, 2])], fill=col, outline=col)

def project(pt, R, scale, center, pivot=(0, 0, 0), pre=None, off=(0, 0, 0)):
    p = np.asarray(pt, float)
    if pre is not None: p = pre @ p
    p = p + np.asarray(off, float)
    q = R @ (p - np.asarray(pivot, float))
    return (center[0] + q[0] * scale, center[1] - q[1] * scale)

def wire_box(d, R, scale, center, box, color, width=3, pivot=(0, 0, 0), pre=None, off=(0, 0, 0)):
    x0, x1, y0, y1, z0, z1 = box
    P = [project((x, y, z), R, scale, center, pivot, pre, off) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    idx = lambda i, j, k: i * 4 + j * 2 + k
    edges = []
    for i in (0, 1):
        for j in (0, 1):
            edges.append((idx(i, j, 0), idx(i, j, 1)))
            edges.append((idx(i, 0, j), idx(i, 1, j)))
            edges.append((idx(0, i, j), idx(1, i, j)))
    for a, b in edges: d.line([P[a], P[b]], fill=color, width=width)

def callout(d, anchor_px, text_px, label, color=FG, fnt=None, a=1.0, side=None):
    fnt = fnt or font(26)
    col = mix(BG, color, a); col2 = mix(BG, FG, a)
    ax, ay = anchor_px; tx, ty = text_px
    d.ellipse((ax - 6, ay - 6, ax + 6, ay + 6), outline=col, width=3)
    d.line([(ax, ay), (tx, ty)], fill=col, width=2)
    tw = fnt.getlength(label)
    left = (tx < ax) if side is None else (side == "left")
    if left:  # text to the left
        d.line([(tx, ty), (tx - tw - 10, ty)], fill=col, width=2)
        d.text((tx - tw - 10, ty - fnt.size - 6), label, font=fnt, fill=col2)
    else:
        d.line([(tx, ty), (tx + tw + 10, ty)], fill=col, width=2)
        d.text((tx + 10, ty - fnt.size - 6), label, font=fnt, fill=col2)

SHELL_FLIP = rot_x(math.pi)  # open side up

# ---- vendor board models (STEP -> npz via step_to_mesh.py), placed as 04_boards.py placed them
PCB_GREEN = (28, 96, 58); PCB_DARK = (34, 38, 44); GOLD = (205, 160, 70); SILVER = (190, 194, 200)
CONN_WHITE = (225, 225, 228); CHIP = (24, 24, 26)
_boards = {}
def load_board(name):
    """Returns (tris(N,3,3) in CASE frame mm, cols(N,3))."""
    if name in _boards: return _boards[name]
    z = np.load(os.path.join(HERE, "models", name + ".npz"))
    tris = z["tris"].astype(float); cols = z["cols"].astype(float)
    cen = tris.mean(axis=1)
    if name == "rd03d":
        # native: X width, Y thickness (+Y patch side, -Y connector), Z long axis. File is one colour.
        # rear components (y<0) light grey, PCB green, the one modelled IC on top dark
        cols = np.where((cen[:, 1:2] < -0.05), np.array(CONN_WHITE, float),
                np.where(cen[:, 1:2] > 1.62, np.array(CHIP, float), np.array(PCB_GREEN, float)))
        pre = rot_z(math.pi) @ rot_x(math.pi / 2)              # 04_boards: +90 about X, then 180 about Z
        cx, zmin = -11.5, 14.0 - 1.0 - 6.35                    # radarCx, intD - 1 mm - radarT
    else:
        # native: X long axis (USB at +X), Y thickness (components +Y), Z short axis.
        uncol = np.all(cols == 150, axis=1)
        ymin = tris[:, :, 1].min()
        pcb = uncol & (cen[:, 1] < ymin + 1.3)                 # the 0.8 mm board itself, bottom face through top face
        cols[pcb] = PCB_DARK
        cols[uncol & ~pcb] = SILVER
        # castellated pads run along both long edges (native Z extremes, board is not centred in Z) at PCB height: gold
        zc = (tris[:, :, 2].min() + tris[:, :, 2].max()) / 2
        pads = (np.abs(cen[:, 2] - zc) > 7.3) & (cen[:, 1] < ymin + 1.0)
        cols[pads] = GOLD
        pre = rot_x(math.pi / 2)
        cx, zmin = 8.0, 3.0                                     # xiaoCx, postH
    v = tris.reshape(-1, 3) @ pre.T
    lo, hi = v.min(0), v.max(0)
    off = np.array([cx - (lo[0] + hi[0]) / 2, 0.0 - (lo[1] + hi[1]) / 2, zmin - lo[2]])
    v = (v + off).reshape(-1, 3, 3)
    if name == "rd03d":
        # The vendor model carries no antenna patches. Add them from Ai-Thinker's dimension drawing
        # (44 x 15 mm board, "Front" view): 2x2 RX array at one end, centres 4.9 / 12.7 mm from that
        # end and 4.5 / 10.5 mm from the drawing's top edge; TX pair at 27.2 / 34.7 mm from the RX end,
        # 9.0 mm from the top edge; patches ~3.4 mm square on a cream substrate. The RX end is at +Y in
        # the case; the drawing's top edge is the side the 45-deg IC sits on, read from the mesh.
        chip = np.all(cols == np.array(CHIP, float), axis=1)
        ic_x = v[chip].reshape(-1, 3)[:, 0].mean() if chip.any() else -11.5
        sgn = 1.0 if ic_x > -11.5 else -1.0
        xw = lambda d_top: -11.5 + sgn * (7.55 - d_top)        # across the width, from the drawing's top edge
        yl = lambda d_end: 22.01 - d_end                        # along the length, from the RX end
        # Decals are painted INTO the PCB's top face (no separate coplanar layer, so nothing z-fights):
        # find the top-face triangles, subdivide them finely, and colour by centroid membership.
        pcb_top = np.sort(v[:, :, 2].ravel())[int(0.5 * v.size / 3)]  # a representative PCB-face height
        ztop = v[np.all(cols == np.array(PCB_GREEN, float), axis=1)][:, :, 2].max()
        top = np.all(np.abs(v[:, :, 2] - ztop) < 0.02, axis=1)
        tv, tc = subdivide(v[top], cols[top], max_edge=0.45)
        cen2 = tv.mean(axis=1)
        def inside(x0, x1, y0, y1):
            return (cen2[:, 0] >= min(x0, x1)) & (cen2[:, 0] <= max(x0, x1)) & (cen2[:, 1] >= min(y0, y1)) & (cen2[:, 1] <= max(y0, y1))
        for (x0, x1, y0, y1) in ((xw(1.5), xw(13.5), yl(16.5), yl(1.5)), (xw(5.5), xw(12.5), yl(38.5), yl(23.5))):
            tc[inside(x0, x1, y0, y1)] = (222, 206, 160)
        s = 1.7
        for d_end, d_top in ((4.9, 4.5), (12.7, 4.5), (4.9, 10.5), (12.7, 10.5), (27.2, 9.0), (34.7, 9.0)):
            px, py = xw(d_top), yl(d_end)
            tc[inside(px - s, px + s, py - s, py + s)] = GOLD
        rv, rc = subdivide(v[~top], cols[~top], max_edge=2.5)
        v = np.concatenate([rv, tv]); cols = np.concatenate([rc, tc])
    _boards[name] = (v, cols)
    return _boards[name]

def subdivide(tris, cols, max_edge=2.5):
    """Longest-edge bisection until every edge is under max_edge (slivers stay cheap)."""
    tris = np.asarray(tris, float); cols = np.asarray(cols, float)
    for _ in range(40):
        edges = np.linalg.norm(tris - np.roll(tris, -1, axis=1), axis=2)   # edge i = v[i] -> v[i+1]
        longest = edges.argmax(axis=1); e = edges[np.arange(len(tris)), longest]
        big = e > max_edge
        if not big.any(): break
        T = tris[big]; C = cols[big]; L = longest[big]
        i0 = L; i1 = (L + 1) % 3; i2 = (L + 2) % 3
        r = np.arange(len(T))
        a, b_, c_ = T[r, i0], T[r, i1], T[r, i2]
        m = (a + b_) / 2
        new = np.concatenate([np.stack([a, m, c_], 1), np.stack([m, b_, c_], 1)])
        tris = np.concatenate([tris[~big], new]); cols = np.concatenate([cols[~big], np.tile(C, (2, 1))])
    return tris, cols

def board_parts(lift=0.0):
    out = []
    for name in ("rd03d", "xiao"):
        tris, cols = load_board(name)
        out.append((tris, cols, None, (0, 0, lift)))
    return out

# ----------------------------------------------------------------- radar chart
RX_MM, RY_MM = 3000, 8000
HUD_H = 56
def chart_scale(): return min(W / (2 * RX_MM), (H - HUD_H) / RY_MM)
def to_px(x, y):
    s = chart_scale(); return (W / 2 + x * s, H - y * s)

def path_at(keys, t):
    """keys: [(t,x,y),...]; returns (x,y) or None when not present."""
    if t < keys[0][0] or t > keys[-1][0]: return None
    for (t0, x0, y0), (t1, x1, y1) in zip(keys, keys[1:]):
        if t0 <= t <= t1:
            u = (t - t0) / max(1e-6, t1 - t0)
            return (lerp(x0, x1, u), lerp(y0, y1, u))
    return None

def speed_at(keys, t):
    a = path_at(keys, t - 0.1); b = path_at(keys, t + 0.1)
    if a is None or b is None: return 0
    ra = math.hypot(*a); rb = math.hypot(*b)
    return int((rb - ra) / 0.2 / 10)  # cm/s radial

def draw_chart(img, t, tracks, light_on, hold_text=None, fw="b7bca03", frames=0):
    d = ImageDraw.Draw(img)
    s = chart_scale(); ox, oy = W / 2, H
    # range arcs
    for r in range(1, 9):
        rp = r * 1000 * s
        d.arc((ox - rp, oy - rp, ox + rp, oy + rp), 180, 360, fill=(52, 52, 52), width=2)
        d.text((ox + 8, oy - rp + 4), "%d m" % r, font=font(20), fill=(90, 90, 90))
    for sgn in (-1, 1):  # +/-60 deg fan
        ex = ox + sgn * RY_MM * s * math.sin(math.radians(60)); ey = oy - RY_MM * s * math.cos(math.radians(60))
        d.line([(ox, oy), (ex, ey)], fill=(60, 60, 60), width=2)
    d.line([(ox, oy), (ox, HUD_H)], fill=(40, 40, 40), width=1)
    # trails + targets
    cols = [C1, C2, C3]; hud_t = []
    for i, keys in enumerate(tracks):
        for k in range(22, 0, -1):
            tp = t - k / 11.0
            p = path_at(keys, tp)
            if p is None: continue
            a = 1 - k / 23.0
            px, py = to_px(*p)
            d.ellipse((px - 4, py - 4, px + 4, py + 4), fill=mix(BG, cols[i], a * 0.8))
        p = path_at(keys, t)
        if p is None:
            hud_t.append("T%d: ---" % (i + 1)); continue
        px, py = to_px(*p)
        d.ellipse((px - 9, py - 9, px + 9, py + 9), fill=cols[i])
        d.ellipse((px - 16, py - 16, px + 16, py + 16), outline=mix(BG, cols[i], 0.5), width=2)
        v = speed_at(keys, t)
        d.text((px + 18, py - 30), "x=%d y=%d" % (int(p[0]), int(p[1])), font=font(20, mono=True), fill=cols[i])
        hud_t.append("T%d: x=%d y=%d v=%d cm/s" % (i + 1, int(p[0]), int(p[1]), v))
    # HUD
    d.rectangle((0, 0, W, HUD_H), fill=BG)
    d.text((12, 8), "connected", font=font(22, bold=True), fill=GREEN)
    d.text((140, 8), "  |  ".join(hud_t), font=font(22), fill=FG)
    d.text((12, 32), "frames=%d  dropped=0  bad=0" % frames, font=font(20), fill=DIM)
    d.text((W - 160, 32), "fw " + fw, font=font(20), fill=DIM)
    # light indicator
    bx, by = W - 420, H - 150
    rrect(d, (bx, by, bx + 380, by + 100), 14, fill=(26, 26, 26), outline=(60, 60, 60), width=2)
    lc = YEL if light_on else (70, 70, 70)
    d.ellipse((bx + 24, by + 28, bx + 68, by + 72), fill=lc)
    if light_on:
        d.ellipse((bx + 14, by + 18, bx + 78, by + 82), outline=mix(BG, YEL, 0.35), width=3)
    d.text((bx + 90, by + 18), "stair light", font=font(24, light=True), fill=DIM)
    d.text((bx + 90, by + 48), ("ON" if light_on else "OFF") + (("   " + hold_text) if hold_text else ""),
           font=font(30, bold=True), fill=FG if light_on else DIM)
    return d

ZONE = (-2000, 2000, 300, 4000)
def in_zone(p): return p is not None and ZONE[0] <= p[0] <= ZONE[1] and ZONE[2] <= p[1] <= ZONE[3]

# ----------------------------------------------------------------- code panes
PY_KW = set("def return if else elif for in not and or import from class with as None True False while pass lambda".split())
C_KW = set("int void static const return if else for while bool uint8_t uint16_t uint32_t int16_t sizeof struct typedef break continue".split())
def tokens(line):
    return re.findall(r"\s+|[A-Za-z_]\w*|\d+\.?\d*|\"[^\"]*\"|'[^']*'|.", line)

def code_pane(d, box, lines, first, fnt, lang="py", hl=(), title=None, in_block_comment=False):
    x0, y0, x1, y1 = box
    rrect(d, box, 10, fill=PANE)
    if title:
        d.rectangle((x0, y0, x1, y0 + 40), fill=PANE2)
        d.text((x0 + 16, y0 + 8), title, font=font(22, mono=True), fill=DIM)
        y0 += 44
    lh = int(fnt.size * 1.3)
    nvis = int((y1 - y0 - 10) / lh)
    i0 = int(math.floor(first)); frac = first - i0
    y = y0 + 8 - frac * lh
    kw = PY_KW if lang == "py" else C_KW
    for i in range(i0, min(len(lines), i0 + nvis + 1)):
        if y < y0 - lh: y += lh; continue
        ln = lines[i].rstrip("\n").replace("\t", "    ")
        if i + 1 in hl:
            d.rectangle((x0 + 4, y - 2, x1 - 4, y + lh - 2), fill=(55, 60, 45))
        d.text((x0 + 14, y), "%4d" % (i + 1), font=fnt, fill=(90, 90, 90))
        x = x0 + 14 + fnt.getlength("%4d  " % 0)
        stripped = ln.lstrip()
        if lang == "md":
            col = C1 if stripped.startswith("#") else (DIM if stripped.startswith("|") else CODE_FG)
            if stripped.startswith("**"): col = CODE_STR
            d.text((x, y), ln[: 120], font=fnt, fill=col)
        elif stripped.startswith("#") and lang == "py" or stripped.startswith(("/*", "*", "//")):
            d.text((x, y), ln[: 120], font=fnt, fill=CODE_CM)
        else:
            in_str = None
            for tok in tokens(ln):
                if x > x1 - 20: break
                if in_str is None and tok in ("\"", "'"): in_str = tok; col = CODE_STR
                elif in_str is not None:
                    col = CODE_STR
                    if tok == in_str: in_str = None
                elif tok.startswith(("\"", "'")): col = CODE_STR
                elif tok in kw: col = CODE_KW
                elif re.match(r"^\d", tok): col = CODE_NUM
                elif tok.startswith("#") and lang == "py": col = CODE_CM
                else: col = CODE_FG
                if tok.startswith("#") and lang == "py":
                    d.text((x, y), ln[ln.index("#"):][:120], font=fnt, fill=CODE_CM); break
                d.text((x, y), tok, font=fnt, fill=col); x += fnt.getlength(tok)
        y += lh
        if y > y1 - lh: break
    # mask overflow above title
    return

def read_lines(rel): return open(os.path.join(ROOT, rel)).read().split("\n")

def terminal(d, box, entries, t, fnt, title="serial monitor", speed=0.0):
    """entries: [(t_show, text, color)] ; typewriter per line (speed chars/s, 0 = instant)."""
    x0, y0, x1, y1 = box
    rrect(d, box, 10, fill=(14, 14, 14), outline=(50, 50, 50), width=2)
    d.rectangle((x0, y0, x1, y0 + 40), fill=PANE2)
    d.text((x0 + 16, y0 + 8), title, font=font(22, mono=True), fill=DIM)
    lh = int(fnt.size * 1.35)
    vis = [(ts, s, c) for ts, s, c in entries if ts <= t]
    nmax = int((y1 - y0 - 60) / lh)
    vis = vis[-nmax:]
    y = y0 + 52
    for ts, s, c in vis:
        if speed > 0:
            n = int((t - ts) * speed); s = s[:n]
        d.text((x0 + 16, y), s, font=fnt, fill=c); y += lh

def chat_bubble(d, box, text, fnt, t, t0, cps=40, label="the request"):
    x0, y0, x1, y1 = box
    n = int(max(0, t - t0) * cps)
    shown = text[:n]
    rrect(d, box, 16, fill=(32, 36, 44), outline=(60, 70, 90), width=2)
    d.text((x0 + 24, y0 + 16), label, font=font(22, light=True), fill=DIM)
    paragraph(d, (x0 + 24, y0 + 54), shown + ("|" if n < len(text) else ""), fnt, FG, x1 - x0 - 48)

# ----------------------------------------------------------------- shots
def shot_01(t, dur):
    key = "01_open"
    img = new_frame()
    walk1 = [(2.0, 1700, 3900), (6.5, 300, 2600), (9.5, -660, 1200), (12.0, -350, 500)]
    walk2 = [(17.0, -1600, 3700), (21.0, -660, 1250), (23.5, -200, 600)]
    walk3 = [(25.0, 900, 3000), (29.5, 1500, 3800)]
    tracks = [walk1, walk2, walk3]
    light = any(in_zone(path_at(k, tp)) for k in tracks for tp in np.arange(0, t, 0.25))
    draw_chart(img, t, tracks, light, frames=int(11 * t) + 48213)
    d = ImageDraw.Draw(img)
    caption(d, "Recreation of the live chart served by the device (synthetic walks; real zone)", "left")
    # title overlay
    t_title = cue(key, "it is not why")
    a = seg(t, t_title, t_title + 1.2) * (1 - seg(t, dur - 1.8, dur - 0.8))
    if a > 0:
        ov = Image.new("RGB", (W, H), BG)
        img = Image.blend(img, ov, 0.55 * a); d = ImageDraw.Draw(img)
        f1 = font(60, bold=True); f2 = font(32, light=True)
        s1 = "A radar stair light, built with an AI co-engineer"
        d.text(((W - f1.getlength(s1)) / 2, 330), s1, font=f1, fill=mix(BG, FG, a))
        s2 = "and where the human earned his keep"
        d.text(((W - f2.getlength(s2)) / 2, 415), s2, font=f2, fill=mix(BG, DIM, a))
        t_stats = cue(key, "Over four weeks")
        stats = ["4 weeks of evenings", "~1,450 lines of C  ·  19 host tests",
                 "~1,900 lines of Fusion 360 Python", "10 dated specs and plans", "7 revisions of the back plate"]
        for i, s in enumerate(stats):
            b = seg(t, t_stats + i * 0.9, t_stats + i * 0.9 + 0.6) * a
            if b > 0:
                f = font(30)
                d.text(((W - f.getlength(s)) / 2, 520 + i * 48), s, font=f, fill=mix(BG, FG, b))
    return fade(img, t, dur, fin=1.2)

def plate_parts(): return [(load("rd03d_case_back.stl"), PLATE_COL, None, (0, 0, 0))]
def shell_parts(flip=True, off=(0, 0, 0)):
    return [(load("rd03d_case_shell.stl"), SHELL_COL, SHELL_FLIP if flip else None, off)]

def shot_02(t, dur):
    key = "02_thing"
    img = new_frame(); d = ImageDraw.Draw(img)
    t_plate = cue(key, "The back plate"); t_shell = cue(key, "The shell has"); t_print = cue(key, "It printed")
    t_lego = cue(key, "six LEGO")
    az = 30 + 9 * t
    if t < t_plate:  # exploded assembly
        R = view(az, 32); sc = 11; c = (W / 2, H / 2 + 40)
        gap = 34 + 4 * math.sin(t * 0.8)
        render_meshes(d, plate_parts() + board_parts(lift=gap * 0.25) + shell_parts(flip=False, off=(0, 0, gap)), R, sc, c, pivot=(0, 0, gap / 2))
        f = font(28, light=True)
        for i, s in enumerate(["Ai-Thinker RD-03D   24 GHz FMCW, 3 targets, 30-byte frames at 256 kbaud",
                               "Seeed XIAO ESP32-C6   RISC-V, 2.4 GHz WiFi, 4 MB flash"]):
            b = seg(t, 1.5 + i * cue(key, "It is wired") / 2, 2.3 + i * cue(key, "It is wired") / 2)
            d.text((60, H - 170 + i * 44), s, font=f, fill=mix(BG, FG, b))
        caption(d, "Rendered from the project's STL files and the vendor STEP models, exploded", "right")
    elif t < t_shell:
        bottom = t_lego <= t < t_shell
        if bottom:
            R = view(az, -38); c = (W / 2 - 150, H / 2 - 30)
        else:
            R = view(az, 38); c = (W / 2 - 150, H / 2 + 30)
        sc = 13
        if bottom:
            render_meshes(d, plate_parts(), R, sc, c)
        else:
            t_drop = cue(key, "posts for the XIAO")
            lift = 45 * (1 - seg(t, t_drop, t_drop + 1.6))
            render_meshes(d, plate_parts() + board_parts(lift=lift), R, sc, c)
        P = lambda p: project(p, R, sc, c)
        items_top = [("radar bay", "radar bay (crossbars bear on bare PCB)", (-11, 0, 4), (1180, 240)),
                     ("posts for the XIAO", "XIAO posts and retention clips", (12, 0, 4), (1180, 330)),
                     ("five cantilever", "five cantilever clips, 0.6 mm lip", (-20.8, 0, 10), (1180, 420)),
                     ("USB-C", "USB-C power jack, flush at the back face", (13.6, -19, 0), (1180, 510)),
                     ("capacitor cradled", "100 µF capacitor cradle", (10, 16.75, 5.5), (1180, 600))]
        items_bottom = [("six LEGO", "6× LEGO Technic Ø4.9 mm, 8 mm pitch, counterbored", (0.95, 4, -8), (1180, 300)),
                        ("ball joint", "flat back face: ball-joint pin or tape", (-10, -12, -8), (1180, 400))]
        for sub, label, anchor, tp in (items_bottom if bottom else items_top):
            tc = cue(key, sub)
            a = seg(t, tc, tc + 0.6)
            if a > 0: callout(d, P(anchor), tp, label, color=C3, a=a)
        caption(d, "Back plate from rd03d_case_back.stl" + (", viewed from the back" if bottom else "; boards from the vendor STEP models, antenna patches added schematically"), "right")
    elif t < t_print:
        R = view(az, 40); sc = 13; c = (W / 2 - 150, H / 2 + 20)
        render_meshes(d, shell_parts(flip=True), R, sc, c)
        P = lambda p: project(p, R, sc, c, pre=SHELL_FLIP)
        a1 = seg(t, t_shell + 0.3, t_shell + 0.9)
        callout(d, P((-11, 10, 12.9)), (1180, 300), "radome step: 1.21 mm gap, 3.1 mm solid PETG", color=C3, a=a1)
        callout(d, P((-11, -10, 12.9)), (1180, 380), "both antenna groups: TX and the 2×2 RX array", color=C3, a=a1)
        tb = cue(key, "a boss"); a2 = seg(t, tb, tb + 0.6)
        callout(d, P((6, 0, 6.4)), (1180, 470), "7×7 mm boss over the XIAO RF shield", color=C3, a=a2)
        caption(d, "Front shell, rendered from rd03d_case_shell.stl, open side up", "right")
    else:
        R = view(az, 30); sc = 10; c = (W / 2 - 200, H / 2 + 20)
        render_meshes(d, plate_parts() + board_parts() + shell_parts(flip=True, off=(0, 58, 0)), R, sc, c, pivot=(0, 29, 0))
        f = font(32)
        for i, s in enumerate(["PETG", "0.6 mm nozzle", "no supports", "shell at high infill (solid radome)", "7 revisions of the plate"]):
            b = seg(t, t_print + 0.3 + i * 0.5, t_print + 0.9 + i * 0.5)
            d.text((1250, 330 + i * 56), s, font=f, fill=mix(BG, FG, b))
        caption(d, "Both printed parts from the STL files, boards from the vendor STEP models", "right")
    chapter(d, key, t, 2)
    return fade(img, t, dur)

def shot_03(t, dur):
    key = "03_firmware"
    img = new_frame(); d = ImageDraw.Draw(img)
    t_spec = cue(key, "wrote a short design spec"); t_ten = cue(key, "Ten of those")
    t_parser = cue(key, "The radar frame parser"); t_tests = cue(key, "Nineteen host")
    t_ota = cue(key, "Over-the-air"); t_trap = cue(key, "The agent also walked"); t_fix = cue(key, "One line to fix")
    fm = font(22, mono=True)
    request = ("I have an Ai-Thinker RD-03D radar wired to a XIAO ESP32-C6. Read its UART frames, decode the three "
               "targets and print them to the console. Then I want a live radar chart in a browser over WiFi, "
               "MQTT events for Node-RED, and OTA updates so I am not up a ladder with a USB cable. Test what you can "
               "on the Mac before it touches the board.")
    if t < t_ten:
        chat_bubble(d, (120, 170, 980, 560), request, font(28), t, 0.8, cps=45)
        if t >= t_spec:
            spec = read_lines("docs/superpowers/specs/2026-08-31-rd03d-uart-design.md")
            first = max(0, (t - t_spec) * 1.6)
            code_pane(d, (1040, 170, 1820, 980), spec, first, fm, lang="md", title="docs/superpowers/specs/2026-08-31-rd03d-uart-design.md")
        caption(d, "The request is paraphrased; the spec on the right is the real file from the repository")
    elif t < t_parser:
        f = font(26, mono=True)
        rrect(d, (160, 150, 1760, 960), 12, fill=PANE)
        d.text((190, 170), "docs/superpowers/", font=font(26, mono=True), fill=DIM)
        specs = sorted(os.listdir(os.path.join(ROOT, "docs/superpowers/specs")))
        plans = sorted(os.listdir(os.path.join(ROOT, "docs/superpowers/plans")))
        specs = [s for s in specs if "2026-08" in s or "2026-09" in s]; plans = [p for p in plans if "2026-08" in p or "2026-09" in p]
        d.text((220, 220), "specs/", font=f, fill=C1); d.text((1000, 220), "plans/", font=f, fill=C1)
        for i, (s, p) in enumerate(zip(specs, plans)):
            a = seg(t, t_ten + 0.2 + i * 0.25, t_ten + 0.6 + i * 0.25)
            d.text((240, 265 + i * 40), s, font=f, fill=mix(BG, FG, a))
            d.text((1020, 265 + i * 40), p, font=f, fill=mix(BG, FG, a))
        d.text((220, 700), "spec  ›  argued over  ›  numbered plan  ›  implement + test  ›  hardware check  ›  merge",
               font=font(28), fill=mix(BG, C3, seg(t, t_ten + 2.5, t_ten + 3.2)))
        caption(d, "Real file names from the repository")
    elif t < t_ota:
        src = read_lines("rd03d_uart/main/rd03d.c")
        first = max(0, (t - t_parser) * 1.1)
        code_pane(d, (100, 150, 1180, 980), src, first, fm, lang="c", title="rd03d_uart/main/rd03d.c  (pure C, no IDF dependency)")
        if t >= t_tests - 1.5:
            names = [l for l in read_lines("rd03d_uart/tests/test_rd03d.c") + read_lines("rd03d_uart/tests/test_mqtt_throttle.c") if "void test_" in l]
            names = [re.sub(r".*void (test_\w+).*", r"\1", n) for n in names]
            entries = [(t_tests - 1.5 + i * 0.12, "  ok  " + n, FG) for i, n in enumerate(names)]
            entries.append((t_tests + 2.6, "", FG)); entries.append((t_tests + 2.7, "19 passed, 0 failed  (test_rd03d: 6, test_mqtt_throttle: 13)", GREEN))
            terminal(d, (1220, 150, 1820, 980), entries, t, font(20, mono=True), title="host tests  (cc + run on the Mac)")
        caption(d, "Real source and real test names; the runner output is reconstructed")
    elif t < t_trap:
        log = [
            (0.0, "I (512) boot: ESP-IDF v5.5 2nd stage bootloader", DIM),
            (0.3, "I (548) boot: ota_1 selected (new image, PENDING_VERIFY)", DIM),
            (0.6, "I (1204) rd03d: fw deadbeef  (drill image: web server start skipped)", C3),
            (1.1, "I (3310) wifi_link: connected, got IP", DIM),
            (1.4, "I (3312) main: validation pending - need WiFi + web server within 90 s", FG),
            (2.6, "I (33310) main: validation pending ... 60 s left", DIM),
            (4.0, "I (63310) main: validation pending ... 30 s left", DIM),
            (5.6, "E (93312) main: validation deadline missed - restarting to roll back", RED),
            (6.1, "I (93320) esp_ota_ops: marking ota_1 invalid, booting ota_0", RED),
            (6.6, "I (512) boot: ESP-IDF v5.5 2nd stage bootloader", DIM),
            (6.9, "I (548) boot: ota_0 selected", DIM),
            (7.2, "I (1204) rd03d: fw b7bca03", GREEN),
            (7.6, "I (3310) wifi_link: connected, got IP", DIM),
            (8.0, "I (4420) web_server: listening on :80, mDNS rd03d.local", DIM),
            (8.3, "I (4425) main: firmware validated (WiFi + web server up)", GREEN),
            (9.2, "", FG),
            (9.3, "# deliberately bad image self-recovered in ~95 s", C3),
        ]
        entries = [(t_ota + 0.4 + ts, s, c) for ts, s, c in log]
        terminal(d, (160, 150, 1760, 960), entries, t, font(24, mono=True), title="serial monitor  -  OTA rollback drill, 2026-09-06")
        caption(d, "Log reconstructed from the project notes of the drill; timings as recorded")
    else:
        src = read_lines("rd03d_uart/main/main.c")
        code_pane(d, (100, 150, 1180, 980), src, 70, fm, lang="c", hl=(81, 82, 89, 90), title="rd03d_uart/main/main.c  -  OTA validation task")
        f = font(28)
        y = 200
        y = paragraph(d, (1230, y), "Station image: the IP event sets wifi_link_is_up(), the web server comes up, the image is marked valid.", f, FG, 580)
        a = seg(t, t_trap + 2.0, t_trap + 2.6)
        y = paragraph(d, (1230, y + 30), "Access-point image: no IP event ever fires. The flag stayed false, the deadline passed, every OTA rolled back. USB flashing kept working, which hid it.", f, mix(BG, RED, a), 580)
        b = seg(t, t_fix, t_fix + 0.6)
        paragraph(d, (1230, y + 30), "Fix: set the flag on WIFI_EVENT_AP_START as well. One line.", f, mix(BG, GREEN, b), 580)
        caption(d, "Real source; lines 81-82 and 89-90 are the gate")
    chapter(d, key, t, 3)
    return fade(img, t, dur)

def shot_04(t, dur):
    key = "04_cad"
    img = new_frame(); d = ImageDraw.Draw(img)
    t_driver = cue(key, "The agent wrote a driver"); t_scripts = cue(key, "a sequence of numbered")
    t_lines = cue(key, "About nineteen"); t_cross = cue(key, "Here are the crossbars")
    t_verify = cue(key, "The last script"); t_caught = cue(key, "It caught exactly")
    t_unit = cue(key, "A unit test"); t_sw = cue(key, "None of this depends")
    fm = font(21, mono=True)
    az = 20 + 8 * t
    if t < t_scripts:
        # architecture diagram
        boxes = [("AI agent", "Claude Code on the Mac", 160), ("MCP server", "Autodesk adapter\nlocalhost:27182", 760), ("Fusion 360", "live document\nrd-03d_case", 1360)]
        for i, (a, b, x) in enumerate(boxes):
            u = seg(t, 0.6 + i * 0.5, 1.2 + i * 0.5)
            rrect(d, (x, 380, x + 400, 560), 18, fill=mix(BG, PANE2, u), outline=mix(BG, C1 if i != 1 else C3, u), width=3)
            d.text((x + 24, 400), a, font=font(36, bold=True), fill=mix(BG, FG, u))
            yy = 452
            for ln in b.split("\n"):
                d.text((x + 24, yy), ln, font=font(26, light=True), fill=mix(BG, DIM, u)); yy += 34
        for x in (560, 1160):
            u = seg(t, 1.8, 2.4)
            arrow(d, (x + 10, 450), (x + 190, 450), mix(BG, FG, u), width=4, head=16)
            arrow(d, (x + 190, 490), (x + 10, 490), mix(BG, DIM, u), width=4, head=16)
            d.text((x + 40, 405), "Python script", font=font(22), fill=mix(BG, FG, u))
            d.text((x + 30, 500), "result / screenshot", font=font(22), fill=mix(BG, DIM, u))
        if t >= t_driver:
            src = read_lines("case/fusion_scripts/run_fusion.py")
            code_pane(d, (160, 620, 1760, 980), src, 0, fm, lang="py", title="case/fusion_scripts/run_fusion.py  -  the driver (JSON-RPC over HTTP)")
        caption(d, "Fusion API unit is centimetres; every script carries an MM constant. The live session was not recorded.")
    elif t < t_cross:
        R = view(az, 36); sc = 9.5; c = (1450, 560)
        render_meshes(d, plate_parts(), R, sc, c)
        scripts = ["00_smoke.py", "01_setup.py", "02_backplate.py", "03_shell.py", "04_boards.py", "05_export.py", "90_verify.py", "run_fusion.py"]
        counts = {}
        for s in scripts:
            counts[s] = sum(1 for _ in open(os.path.join(ROOT, "case/fusion_scripts", s)))
        f = font(28, mono=True)
        d.text((140, 180), "case/fusion_scripts/", font=f, fill=DIM)
        for i, s in enumerate(scripts):
            a = seg(t, t_scripts + 0.2 + i * 0.35, t_scripts + 0.7 + i * 0.35)
            col = C3 if s == "90_verify.py" else FG
            d.text((170, 230 + i * 44), "%-16s %5d lines" % (s, counts[s]), font=f, fill=mix(BG, col, a))
        a = seg(t, t_lines, t_lines + 0.6)
        d.text((170, 230 + len(scripts) * 44 + 10), "%-16s %5d lines" % ("", sum(counts.values())), font=f, fill=mix(BG, DIM, a))
        if t >= t_lines + 1.0:
            src = read_lines("case/fusion_scripts/02_backplate.py")
            first = 86 + (t - t_lines - 1.0) * 1.4
            code_pane(d, (140, 640, 1000, 980), src, first, fm, lang="py", title="02_backplate.py  -  clip(): raise wall, thin finger, lip + lead-in")
        caption(d, "Scripts are the construction record; the render is the exported plate", "right")
    elif t < t_verify:
        R = view(az, 40); sc = 12; c = (1400, 560)
        render_meshes(d, plate_parts(), R, sc, c)
        a = seg(t, t_cross + 0.5, t_cross + 1.1)
        colA = mix(BG, C3, a)
        wire_box(d, R, sc, c, (-21, -2.5, -12.8, -11.2, 0, 10.46), colA, width=3)
        wire_box(d, R, sc, c, (-21, -2.5, 17.7, 19.8, 0, 10.46), colA, width=3)
        callout(d, project((-11, -12, 10.46), R, sc, c), (1060, 190), "crossbar A  y −12.8…−11.2, top z = 10.46", color=C3, a=a, side="right")
        callout(d, project((-11, 18.7, 10.46), R, sc, c), (1060, 950), "crossbar B  y +17.7…+19.8", color=C3, a=a, side="right")
        src = read_lines("case/fusion_scripts/02_backplate.py")
        first = 270 + max(0, t - t_cross - 2.0) * 1.1
        code_pane(d, (80, 150, 960, 980), src, first, fm, lang="py", title="02_backplate.py  -  board-seating fix, 2026-09-07")
        caption(d, "Highlighted boxes are the crossbar volumes from the script, drawn over the exported geometry", "right")
    elif t < t_sw:
        R = view(az, 42); sc = 12; c = (1400, 560)
        render_meshes(d, plate_parts(), R, sc, c)
        src = read_lines("case/fusion_scripts/90_verify.py")
        if t < t_caught:
            code_pane(d, (80, 150, 960, 600), src, 31, fm, lang="py", title="90_verify.py  -  read-only point-containment probes")
            code_pane(d, (80, 620, 960, 980), src, 150, fm, lang="py", title="90_verify.py  -  check_lego_bores_clear()")
            a = seg(t, t_verify + 1.0, t_verify + 1.6)
            for cx, cy in ((0.95, -12), (0.95, -4), (0.95, 4), (0.95, 12), (8.95, -4), (8.95, 4)):
                for dx in (-1.5, 0, 1.5):
                    p = project((cx + dx, cy, 0.5), R, sc, c)
                    d.ellipse((p[0] - 4, p[1] - 4, p[0] + 4, p[1] + 4), fill=mix(BG, C2, a))
            callout(d, project((0.95, 12, 0.5), R, sc, c), (1060, 190), "three probes per bore, 0.5 mm above the floor", color=C2, a=a, side="right")
        else:
            code_pane(d, (80, 150, 960, 560), src, 150, fm, lang="py", title="90_verify.py  -  check_lego_bores_clear()")
            rep = [(0.0, "$ run_fusion.py script 90_verify.py --read-only", DIM),
                   (0.5, "  check_baseline ................ ok", FG),
                   (0.8, "  check_xiao_clips .............. ok", FG),
                   (1.1, "  check_no_interior_counterbores  ok", FG),
                   (1.4, "  check_lego_bores_clear ........ FAIL", RED),
                   (1.6, "    EXPECTED VOID at (2.45, 12.00, 0.50): Technic bore (0.95, +12) unroofed at dx=+1.5", RED),
                   (2.0, "  check_usb_jack ................ ok", FG),
                   (2.3, "  check_cap_cradle .............. ok", FG),
                   (3.4, "", FG),
                   (3.5, "# cap ribs moved x 3.0/12.8 -> 5.0/14.8; re-run:", C3),
                   (4.6, "  check_lego_bores_clear ........ ok", GREEN),
                   (4.9, "  7 checks, 0 failures", GREEN)]
            terminal(d, (80, 580, 960, 980), [(t_caught + 0.3 + ts, s, col) for ts, s, col in rep], t, font(19, mono=True), title="verification run  (reconstructed)")
            a = seg(t, t_caught + 1.6, t_caught + 2.2)
            wire_box(d, R, sc, c, (2.4, 3.6, 12.45, 21.05, 0, 8), mix(BG, RED, a), width=3)
            wire_box(d, R, sc, c, (-1.5, 3.4, 9.55, 14.45, -8, 0), mix(BG, C2, a), width=2)
            callout(d, project((3.0, 13.5, 4), R, sc, c), (1060, 190), "capacitor rib at x 2.4…3.6 roofed the bore's +x flank", color=RED, a=a, side="right")
            b = seg(t, t_caught + 4.9, t_caught + 5.5)
            wire_box(d, R, sc, c, (3.8, 6.2, 12.45, 21.05, 0, 8), mix(BG, GREEN, b), width=3)
            callout(d, project((5.0, 13.5, 4), R, sc, c), (1060, 900), "rib moved to x 5.0 — bore clear", color=GREEN, a=b, side="right")
            if t >= t_unit:
                u = seg(t, t_unit, t_unit + 0.6)
                f = font(40, bold=True); s = "a unit test for a mechanical part"
                d.text((1400 - f.getlength(s) / 2, 975), s, font=f, fill=mix(BG, C3, u))
        caption(d, "Probe harness is the real script; the run output is reconstructed from its failure format", "right")
    else:
        f1 = font(44, bold=True); f2 = font(30)
        a = seg(t, t_sw, t_sw + 0.8)
        s = "Not a Fusion trick"
        d.text(((W - f1.getlength(s)) / 2, 300), s, font=f1, fill=mix(BG, FG, a))
        if VARIANT == "hackaday":
            rows = [("Fusion 360", "Python API over Autodesk's MCP server", "done here"),
                    ("FreeCAD · OpenSCAD · Onshape · SolidWorks", "Python, script-native, REST API, COM automation", "same approach"),
                    ("Any CAD with a scripting API", "same loop: numbered scripts + read-only probe harness", "")]
        else:
            rows = [("Fusion 360", "Python API over Autodesk's MCP server", "done here"),
                    ("SolidWorks", "COM automation API (pywin32 / VBA / C#), equations, ray & interference checks", "the easier target"),
                    ("Any CAD with a scripting API", "same loop: numbered scripts + read-only probe harness", "")]
        for i, (aa, bb, cc) in enumerate(rows):
            u = seg(t, t_sw + 1.0 + i * 1.6, t_sw + 1.6 + i * 1.6)
            y = 420 + i * 120
            d.text((300, y), aa, font=font(34, bold=True), fill=mix(BG, C1 if i < 2 else FG, u))
            d.text((300, y + 44), bb, font=f2, fill=mix(BG, FG, u))
            d.text((1420, y), cc, font=font(28, light=True), fill=mix(BG, C3, u))
    chapter(d, key, t, 4)
    return fade(img, t, dur)

# ---- diagrams for shot 5
def diag_board_on_connector(d, u, box=(140, 200, 1780, 920)):
    """u in [0,1]: 0 = before (bars at 6.65 under y ±18), 1 = after (bars at 10.46 in the clear bands)."""
    x0, y0, x1, y1 = box
    S = 30.0  # px per mm
    ox = (x0 + x1) / 2; oy = y1 - 60  # plate floor (z=0) at oy; y axis (board length) horizontal
    def P(y_mm, z_mm): return (ox + y_mm * S, oy - z_mm * S)
    # plate floor
    d.rectangle((P(-24, 0)[0], P(0, 0)[1], P(24, 0)[0], P(0, -3)[1]), fill=(80, 80, 80))
    d.text((P(-24, -3.5)[0], P(0, -3.5)[1] + 4), "back plate interior floor, z = 0", font=font(22), fill=DIM)
    # bars
    barA_y = lerp(-18, -12.0, u); barB_y = lerp(18, 18.75, u)
    barA_w = lerp(4, 1.6, u); barB_w = lerp(4, 2.1, u)
    top = lerp(6.65, 10.46, u)
    for by, bw in ((barA_y, barA_w), (barB_y, barB_w)):
        d.rectangle((P(by - bw / 2, top)[0], P(0, top)[1], P(by + bw / 2, 0)[0], P(0, 0)[1]), fill=(120, 128, 140))
    # board: PCB rear at 10.46, thickness 1.6; patch stack to 13.0; connector y -20..-13.5 down to 6.70
    pcb_bottom = 10.46 if u > 0.5 else 6.65 + (10.46 - 6.70)  # before: board sits on connector, so PCB rear = 6.65 + (10.46-6.70)
    pcb_bottom = lerp(6.65 + (10.46 - 6.70), 10.46, ease(u))
    d.rectangle((P(-22.5, pcb_bottom + 1.6)[0], P(0, pcb_bottom + 1.6)[1], P(22.5, pcb_bottom)[0], P(0, pcb_bottom)[1]), fill=(40, 110, 70))
    d.rectangle((P(-22.5, pcb_bottom + 2.54)[0], P(0, pcb_bottom + 2.54)[1], P(22.5, pcb_bottom + 1.6)[0], P(0, pcb_bottom + 1.6)[1]), fill=(170, 140, 60))
    conn_bottom = pcb_bottom - (10.46 - 6.70)
    d.rectangle((P(-20, pcb_bottom)[0], P(0, pcb_bottom)[1], P(-13.5, conn_bottom)[0], P(0, conn_bottom)[1]), fill=(200, 200, 200))
    lf = font(22); lab = "5-pin connector"
    d.text((P(-22.5, 0)[0] - lf.getlength(lab) - 24, P(0, (pcb_bottom + conn_bottom) / 2)[1] - 12), lab, font=lf, fill=FG)
    d.line([(P(-22.5, 0)[0] - 18, P(0, (pcb_bottom + conn_bottom) / 2)[1]), (P(-20, 0)[0], P(0, (pcb_bottom + conn_bottom) / 2)[1])], fill=DIM, width=2)
    d.text((P(-5, pcb_bottom + 2.54)[0], P(0, pcb_bottom + 2.54)[1] - 60), "RD-03D: patches (front) / PCB / rear components", font=font(22), fill=FG)
    # dimensions
    if u < 0.5:
        dim_line(d, (P(18, 0)[0] + 90, P(0, 6.65)[1]), (P(18, 0)[0] + 90, P(0, pcb_bottom)[1]), "3.85 mm gap", fill=RED, offset=(120, 0))
        d.text((P(-8, 0)[0], P(0, 3)[1]), "board rests on the connector only", font=font(26, bold=True), fill=RED)
        d.text((x0, y0), "before: bars sized from total thickness (6.65 mm incl. connector)", font=font(30), fill=FG)
    else:
        dim_line(d, (P(24, 0)[0] + 60, P(0, 0)[1]), (P(24, 0)[0] + 60, P(0, 10.46)[1]), "10.46 mm", fill=GREEN, offset=(80, 0))
        d.text((P(-8, 0)[0], P(0, 3)[1]), "bars bear on bare PCB in the two clear bands; connector hangs free", font=font(26, bold=True), fill=GREEN)
        d.text((x0, y0), "after: measured rear profile  (clear bands y −13…−11 and +17.5…+20)", font=font(30), fill=FG)

def diag_radome(d, t, u, show_waves=True, box=(140, 200, 1780, 920)):
    """u: 0 = gap 3.10 mm (λ/4), 1 = gap 1.21 mm (λ/10). Vertical section, antenna plane left."""
    x0, y0, x1, y1 = box
    S = 150.0  # px per mm
    gap = lerp(3.10, 1.21, u); rad_t = lerp(1.20, 3.10, u)
    ax = x0 + 300; cy = 540
    # antenna / PCB
    d.rectangle((ax - 60, cy - 190, ax, cy + 190), fill=(40, 110, 70))
    d.rectangle((ax - 6, cy - 190, ax, cy + 190), fill=(170, 140, 60))
    d.text((ax - 200, cy + 206), "antenna plane (patch face)", font=font(22), fill=FG)
    # radome slab
    rx0 = ax + gap * S; rx1 = rx0 + rad_t * S
    d.rectangle((rx0, cy - 210, rx1, cy + 210), fill=(70, 95, 120))
    d.text((rx0, cy + 226), "PETG radome  %.2f mm thick" % rad_t, font=font(22), fill=FG)
    d.text((rx1 + 20, cy - 200), "outside: exterior face stays flat", font=font(22), fill=DIM)
    # gap dimension
    dim_line(d, (ax, cy - 250), (rx0, cy - 250), "air gap  %.2f mm" % gap, fill=C3 if u < 0.5 else GREEN, fnt=font(26, bold=True), offset=(0, -14))
    # waves in the gap
    if show_waves:
        lam_px = 12.5 * S
        xs = np.linspace(ax, rx0, 120)
        ph = 2 * math.pi * 1.2 * t
        inc = np.sin(2 * math.pi * (xs - ax) / lam_px - ph)
        refl = -np.sin(2 * math.pi * (2 * (rx0 - ax) - (xs - ax)) / lam_px - ph)   # phase flip at the plastic
        for arr, col, amp in ((inc, C1, 70), (refl, C3, 70), (inc + refl, FG, 70)):
            pts = [(float(x), float(cy - a * amp)) for x, a in zip(xs, arr)]
            d.line(pts, fill=col, width=3 if col != FG else 4)
        d.text((ax + 10, cy + 100), "incident", font=font(20), fill=C1)
        d.text((ax + 10, cy + 124), "reflected (flipped at the plastic)", font=font(20), fill=C3)
        d.text((ax + 10, cy + 148), "sum at the antenna", font=font(20), fill=FG)
    # equations (bottom left)
    f = font(28); fb = font(28, bold=True)
    yy = 800
    d.text((x0, yy), "λ = c / f = 12.5 mm at 24 GHz", font=fb, fill=FG); yy += 40
    d.text((x0, yy), "λ/4 = 3.125 mm   worst gap: the reflection returns in phase", font=f, fill=C3); yy += 36
    d.text((x0, yy), "λ/10 = 1.25 mm   design rule: keep the gap under this", font=f, fill=GREEN); yy += 36
    # scale bar on right
    bx = x1 - 300; by0 = y0 + 60
    d.text((bx, by0 - 40), "gap", font=font(22), fill=DIM)
    for mm, lab, col in ((3.125, "λ/4", C3), (1.25, "λ/10", GREEN)):
        yv = by0 + 400 - mm * 100
        d.line([(bx, yv), (bx + 200, yv)], fill=col, width=2); d.text((bx + 210, yv - 14), lab, font=font(22), fill=col)
    yv = by0 + 400 - gap * 100
    d.ellipse((bx + 90, yv - 10, bx + 110, yv + 10), fill=FG)
    d.text((bx + 120, yv - 36), "%.2f mm" % gap, font=font(22, bold=True), fill=FG)
    d.line([(bx + 100, by0), (bx + 100, by0 + 400)], fill=DIM2, width=1)

def diag_orientation(d, t, u, box=(140, 200, 1780, 920)):
    """u: 0 portrait (long axis vertical), 1 landscape. Left: board face-on with fan; right: staircase side view."""
    x0, y0, x1, y1 = box
    cx, cy = x0 + 420, (y0 + y1) / 2 + 20
    ang = lerp(0, math.pi / 2, ease(u))
    S = 7.0  # px per mm
    L, Wd = 45.0, 15.1
    def R2(p):
        x, y = p; return (cx + (x * math.cos(ang) - y * math.sin(ang)) * S, cy - (x * math.sin(ang) + y * math.cos(ang)) * S)
    # board rectangle (x across width, y along length)
    corners = [(-Wd / 2, -L / 2), (Wd / 2, -L / 2), (Wd / 2, L / 2), (-Wd / 2, L / 2)]
    d.polygon([R2(c) for c in corners], fill=(40, 110, 70), outline=(90, 160, 110))
    # patches: RX 2x2 at y +4..+23 spaced 6.25 across width; TX 2 at y -17..-4
    for (px, py) in ((-3.125, 8), (3.125, 8), (-3.125, 18), (3.125, 18)):
        pts = [R2((px + dx, py + dy)) for dx, dy in ((-2, -2), (2, -2), (2, 2), (-2, 2))]
        d.polygon(pts, fill=C1)
    for (px, py) in ((0, -8), (0, -14)):
        pts = [R2((px + dx, py + dy)) for dx, dy in ((-2, -2), (2, -2), (2, 2), (-2, 2))]
        d.polygon(pts, fill=C3)
    # RX spacing dimension
    dim_line(d, R2((-3.125, 24)), R2((3.125, 24)), "RX pair ≈ λ/2 = 6.25 mm", fill=C1, offset=(0, -10 if u < 0.5 else -10))
    # angular coverage projected onto the board plane: a +/-60 deg bow-tie along the WIDTH axis
    fan_dir = ang  # board width axis direction on screen
    fl = 300
    ycol = mix(BG, YEL, 0.8)
    for base in (fan_dir, fan_dir + math.pi):
        for sgn in (-1, 1):
            a = base + sgn * math.radians(60)
            d.line([(cx, cy), (cx + fl * math.cos(a), cy - fl * math.sin(a))], fill=ycol, width=3)
        bb = (cx - fl, cy - fl, cx + fl, cy + fl)
        d.arc(bb, -math.degrees(base) - 60, -math.degrees(base) + 60, fill=ycol, width=3)
    lab = "±60° coverage opens ACROSS the board's width" if u < 0.5 else "board landscape  ›  coverage fan is vertical"
    d.text((x0, y0), lab, font=font(32, bold=True), fill=YEL)
    d.text((x0, y0 + 46), "two RX channels across the short axis give the angle; the beam is narrow along the long axis", font=font(24), fill=DIM)
    d.text((x0, y1 - 40), "yellow: angular coverage projected onto the board plane (schematic)", font=font(20), fill=DIM)
    # staircase side view
    sx0 = x1 - 640; base = y1 - 80
    pts = [(sx0, base)]
    for i in range(8):
        pts.append((sx0 + i * 70, base - i * 45)); pts.append((sx0 + (i + 1) * 70, base - i * 45))
    pts.append((sx0 + 8 * 70, base - 8 * 45))
    d.line(pts, fill=(110, 110, 110), width=4)
    # sensor on wall at mid height, fan vertical when landscape
    sxs, sys_ = sx0 + 560, base - 4 * 45 - 60
    d.rectangle((sxs - 14, sys_ - 10, sxs + 14, sys_ + 10), fill=C3)
    spread = lerp(8, 60, ease(u))
    for sgn in (-1, 1):
        a = math.radians(180 + sgn * spread)
        d.line([(sxs, sys_), (sxs + 520 * math.cos(a), sys_ - 520 * math.sin(a))], fill=mix(BG, YEL, 0.6), width=3)
    d.text((sx0, base + 20), "staircase, side view: upstairs and downstairs approaches both need coverage", font=font(22), fill=DIM)

def diag_clips(d, t, u, box=(140, 200, 1780, 920)):
    x0, y0, x1, y1 = box
    S = 60.0
    def panel(ox, oy, slotted, title, col):
        ty = oy - 440
        for ln in title.split("\n"):
            d.text((ox, ty), ln, font=font(28, bold=True), fill=col); ty += 36
        # floor
        d.rectangle((ox, oy, ox + 9 * S, oy + 1.5 * S), fill=(80, 80, 80))
        wall_t = 1.0 if slotted else 1.5
        wx = ox + 4 * S
        if slotted:
            # trench sinking root below floor
            d.rectangle((wx - 1.2 * S, oy, wx, oy + 1.5 * S), fill=BG)
            d.rectangle((wx + wall_t * S, oy, wx + wall_t * S + 1.2 * S, oy + 1.5 * S), fill=BG)
            d.rectangle((wx, oy - 5.8 * S, wx + wall_t * S, oy + 1.5 * S), fill=(120, 128, 140))
        else:
            d.rectangle((wx, oy - 5.6 * S, wx + wall_t * S, oy), fill=(120, 128, 140))
        # lip
        lip_y = oy - (5.8 if slotted else 5.6) * S
        d.polygon([(wx, lip_y), (wx - 0.6 * S, lip_y + 0.3 * S), (wx, lip_y + 0.6 * S)], fill=(120, 128, 140))
        # board edge under the lip
        d.rectangle((wx - 3.0 * S, lip_y + 0.7 * S, wx - 0.05 * S, lip_y + 0.7 * S + 1.0 * S), fill=(40, 110, 70))
        dim_line(d, (wx, oy + 1.5 * S + 40), (wx + wall_t * S, oy + 1.5 * S + 40), "%.1f mm" % wall_t, fill=col, offset=(0, 36))
        d.text((wx - 3.0 * S, lip_y + 1.8 * S + 10), "XIAO PCB edge", font=font(20), fill=DIM)
    panel(x0 + 40, y0 + 460, True, "slotted finger, 1.0 mm, trenched root\n~2 % strain in PETG  —  \"very wimpy\"", RED)
    panel(x0 + 900, y0 + 460, False, "continuous 1.5 mm wall, 0.6 mm lip\n0.34 mm grab  —  firm push to click in", GREEN)
    yy = y0 + 665
    for i, s in enumerate(["0.6 mm fence walls on a 0.6 mm nozzle: one wobbly extrusion  ›  all walls now ≥ 1.5 mm",
                           "tape recess on the back: first layer was a rim with nothing inside  ›  back face is now flat",
                           "the strain analysis was right; what \"holds\" means to a thumb was not in the analysis"]):
        a = seg(t, 2.0 + i * 2.4, 2.6 + i * 2.4)
        d.text((x0, yy + i * 44), "•  " + s, font=font(26), fill=mix(BG, FG, a))

def shot_05(t, dur):
    key = "05_catches"
    img = new_frame(); d = ImageDraw.Draw(img)
    t1 = cue(key, "First, the board"); t1m = cue(key, "I measured the board")
    t2 = cue(key, "Second, the radome"); t2w = cue(key, "At a quarter-wave gap"); t2f = cue(key, "The radome came down")
    t3 = cue(key, "Third, the antenna"); t3l = cue(key, "so the board mounts landscape")
    t4 = cue(key, "Fourth, the printer")
    if t < t1:
        f1 = font(48, bold=True); f2 = font(32, light=True)
        a = seg(t, 0.8, 1.6)
        s = "What the agent got confidently wrong"
        d.text(((W - f1.getlength(s)) / 2, 440), s, font=f1, fill=mix(BG, FG, a))
        s = "and how a reviewer with a caliper and a section view caught it"
        d.text(((W - f2.getlength(s)) / 2, 515), s, font=f2, fill=mix(BG, DIM, a))
    elif t < t2:
        u = seg(t, t1m + 1.0, t1m + 2.5)
        diag_board_on_connector(d, u)
        d.text((140, 150), "1 · the board was resting on its connector", font=font(34, bold=True), fill=C3)
        caption(d, "Cross-section along the board, dimensions from the measured vendor model")
    elif t < t3:
        u = seg(t, t2f, t2f + 2.0)
        diag_radome(d, t, u, show_waves=(t >= t2w - 0.5))
        d.text((140, 150), "2 · the radome gap was a quarter wavelength", font=font(34, bold=True), fill=C3)
        caption(d, "Section through the antenna and radome; waves are schematic (amplitude vs position)")
    elif t < t4:
        u = seg(t, t3l - 0.5, t3l + 1.2)
        diag_orientation(d, t, u)
        d.text((140, 150), "3 · the antenna was going in sideways", font=font(34, bold=True), fill=C3)
        caption(d, "Patch layout schematic: 2×2 RX array (blue) and TX pair (orange)")
    else:
        diag_clips(d, t - t4, 0)
        d.text((140, 150), "4 · the printer disagreed with the design", font=font(34, bold=True), fill=C3)
        caption(d, "Clip cross-sections, schematic; dimensions from the scripts")
    chapter(d, key, t, 5)
    return fade(img, t, dur)

def shot_06(t, dur):
    key = "06_meaning"
    img = new_frame(); d = ImageDraw.Draw(img)
    t_loop = cue(key, "The loop I ran"); t_except = cue(key, "Except that")
    t_c = cue(key, "Three cautions"); t_c2 = cue(key, "The physics has")
    t_c3 = cue(key, "And treat the scripts") if VARIANT == "hackaday" else cue(key, "And the agent you use")
    if t < t_c:
        # analogues list + loop ring
        if VARIANT == "hackaday":
            items = ["a sensor bracket", "a soldering jig", "a camera mount", "a box for the thing you just built"]
        else:
            items = ["fixtures", "cable guides", "probe holders", "optical mounts", "test-head carriers"]
        for i, s in enumerate(items):
            a = seg(t, 1.0 + i * 0.7, 1.5 + i * 0.7)
            d.text((160, 260 + i * 60), s, font=font(40, light=True), fill=mix(BG, FG, a))
        steps = ["describe the part", "agent builds it\nparametrically", "probe harness\nasserts geometry", "print it", "hold it, correct it", "re-run the script"]
        cx, cy, r = 1250, 540, 300
        ring_a = seg(t, t_loop, t_loop + 0.8)
        d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=mix(BG, DIM2, ring_a), width=3)
        for i, s in enumerate(steps):
            a = seg(t, t_loop + 0.3 + i * 0.5, t_loop + 0.9 + i * 0.5)
            ang = -math.pi / 2 + i * 2 * math.pi / len(steps)
            x, y = cx + r * math.cos(ang), cy + r * math.sin(ang)
            rrect(d, (x - 150, y - 44, x + 150, y + 44), 14, fill=mix(BG, PANE2, a), outline=mix(BG, C1, a), width=2)
            lines = s.split("\n"); f = font(26)
            for j, ln in enumerate(lines):
                d.text((x - f.getlength(ln) / 2, y - 16 * len(lines) + j * 32), ln, font=f, fill=mix(BG, FG, a))
            # chevron on the ring midway to the next step
            am = ang + math.pi / len(steps)
            px_, py_ = cx + r * math.cos(am), cy + r * math.sin(am)
            tang = am + math.pi / 2
            arrow(d, (px_ - 14 * math.cos(tang), py_ - 14 * math.sin(tang)), (px_ + 14 * math.cos(tang), py_ + 14 * math.sin(tang)), mix(BG, C1, a), width=3, head=10)
        b = seg(t, t_except, t_except + 0.8)
        f = font(30)
        for i, s in enumerate(["minutes, not an afternoon", "a reviewable script", "a self-test that re-runs"]):
            d.text((cx - 140, cy - 50 + i * 40), s, font=f, fill=mix(BG, C3, b))
    else:
        f1 = font(44, bold=True); f = font(32)
        a = seg(t, t_c, t_c + 0.7)
        d.text((160, 180), "Three cautions", font=f1, fill=mix(BG, FG, a))
        cautions = [(t_c + 1.2, "Confidence is not correctness.", "On anything the agent cannot measure, and in CAD that is everything, its confidence tells you nothing. Every print made without a section view first was made twice."),
                    (t_c2, "The physics has to come from somewhere.", "The quarter-wave radome would have shipped. The datasheet and the reviewer supplied it, not the agent."),
                    (t_c3, "Scripts are the source of truth.", "Keep them under version control and change parameters there, not in the CAD window. A value tuned in the UI was silently reset by the next run of the setup script.")
                    if VARIANT == "hackaday" else
                    (t_c3, "Company work on company tooling.", "Company parts and firmware go through the company-provisioned agent on company accounts. This project was personal, on personal tools, and stayed that way.")]
        y = 280
        for tc, head, body in cautions:
            b = seg(t, tc, tc + 0.7)
            d.rectangle((160, y + 6, 166, y + 46), fill=mix(BG, C1, b))
            d.text((190, y), head, font=font(34, bold=True), fill=mix(BG, FG, b))
            y = paragraph(d, (190, y + 48), body, f, mix(BG, DIM, b), 1500) + 50
    chapter(d, key, t, 6)
    return fade(img, t, dur)

def shot_07(t, dur):
    key = "07_close"
    img = new_frame()
    t_repo = cue(key, "The firmware, the Fusion")
    leave = [(-20.0, -300, 700), (0.0, -500, 900), (3.0, -1200, 2600), (4.5, -1700, 3900)]
    light = t < 11.0
    hold = None
    if 4.5 <= t < 11.0:
        hold = "off in %2d s" % int(max(0, 60 - (t - 4.5) * (60 / 6.5)))
    draw_chart(img, t, [leave, [(99, 0, 0), (100, 0, 0)], [(99, 0, 0), (100, 0, 0)]], light, hold_text=hold, frames=61532 + int(11 * t))
    d = ImageDraw.Draw(img)
    caption(d, "Hold timer shown accelerated (60 s → 6.5 s)", "left")
    a = seg(t, t_repo, t_repo + 1.0)
    if a > 0:
        ov = Image.new("RGB", (W, H), BG); img = Image.blend(img, ov, 0.7 * a); d = ImageDraw.Draw(img)
        f1 = font(48, bold=True); f2 = font(30); f3 = font(26, light=True)
        s = "RD-03D stair radar"
        d.text(((W - f1.getlength(s)) / 2, 300), s, font=f1, fill=mix(BG, FG, a))
        lines = ["firmware  ·  Fusion 360 scripts  ·  Node-RED flow  ·  STLs  ·  ten dated design specs and plans",
                 "all in the repository"]
        for i, s in enumerate(lines):
            d.text(((W - f2.getlength(s)) / 2, 380 + i * 44), s, font=f2, fill=mix(BG, FG, a))
        s = "github.com/nThanksForAllTheFish"
        d.text(((W - font(32, mono=True).getlength(s)) / 2, 510), s, font=font(32, mono=True), fill=mix(BG, C1, a))
        b = seg(t, cue(key, "Everything you have seen"), cue(key, "Everything you have seen") + 1.0)
        creds = ["Everything here was synthesized from the repository:",
                 "CAD views rendered from the exported STL files  ·  radar chart recreated from the device's web page",
                 "code and specs shown are the real files  ·  logs and run output reconstructed from the notes",
                 "narration: macOS text-to-speech"]
        for i, s in enumerate(creds):
            d.text(((W - f3.getlength(s)) / 2, 640 + i * 38), s, font=f3, fill=mix(BG, DIM, b))
    return fade(img, t, dur, fout=1.5)

SHOT_FN = {"01_open": shot_01, "02_thing": shot_02, "03_firmware": shot_03, "04_cad": shot_04,
           "05_catches": shot_05, "06_meaning": shot_06, "07_close": shot_07}

# ----------------------------------------------------------------- drivers
def preview():
    os.makedirs(os.path.join(HERE, "preview"), exist_ok=True)
    for key, fn in SHOT_FN.items():
        dur = shot_len(key)
        for frac in (0.08, 0.3, 0.5, 0.7, 0.92):
            t = dur * frac
            img = fn(t, dur)
            img.save(os.path.join(HERE, "preview", "%s_%03d.png" % (key, int(frac * 100))))
        print("preview", key, "dur %.1f" % dur)

def render(key):
    fn = SHOT_FN[key]; dur = shot_len(key); n = int(math.ceil(dur * FPS))
    os.makedirs(SEG_DIR, exist_ok=True)
    out = os.path.join(SEG_DIR, key + ".mp4")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "%dx%d" % (W, H), "-r", str(FPS), "-i", "-",
           "-i", os.path.join(AUDIO_DIR, key + ".aiff"),
           "-af", "adelay=%d|%d,apad" % (int(LEAD * 1000), int(LEAD * 1000)),
           "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-shortest", "-movflags", "+faststart", out]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        img = fn(i / FPS, dur)
        p.stdin.write(img.tobytes())
    p.stdin.close(); p.wait()
    print("rendered", key, n, "frames ->", out, "rc", p.returncode)

def concat():
    lst = os.path.join(SEG_DIR, "list.txt")
    with open(lst, "w") as f:
        for key in SHOT_FN: f.write("file '%s'\n" % os.path.join(SEG_DIR, key + ".mp4"))
    out = os.path.join(HERE, "final%s.mp4" % SUFFIX)
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", "-movflags", "+faststart", out], check=True)
    print("final ->", out)

def preview_at(pairs):
    os.makedirs(os.path.join(HERE, "preview2"), exist_ok=True)
    for key, t in pairs:
        dur = shot_len(key)
        img = SHOT_FN[key](t, dur).resize((960, 540), Image.LANCZOS)
        img.save(os.path.join(HERE, "preview2", "%s_%05.1f.png" % (key, t)))
        print(key, t)

if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "preview": preview()
    elif mode == "at":
        pairs = [(a.split("@")[0], float(a.split("@")[1])) for a in sys.argv[2:]]
        preview_at(pairs)
    elif mode == "render": render(sys.argv[2])
    elif mode == "concat": concat()
