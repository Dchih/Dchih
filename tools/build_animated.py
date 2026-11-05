#!/usr/bin/env python3
"""Build the animated SVGs for the GitHub profile README. Standard library only.

Run from the folder that holds README.md:
    python3 tools/build_animated.py          build every image
    python3 tools/build_animated.py hero     build only the hero (what the GitHub Action runs)

The hero's towers come from tools/contributions.json, the contributionCalendar
response from GitHub's GraphQL API. Its text comes from tools/layers/hero-text.png,
a transparent export from Figma. The character sheet and inventory are traced from
assets/*.png, so re-export those PNGs from Figma after editing their text.

GitHub shows README SVGs through <img>, so only CSS animation is available: no
scripts and no external files. All artwork is therefore plain vector paths.
"""
import json
import math
import struct
import sys
import zlib
from collections import Counter

INK = "#05081c"
CREAM = "#f4ecd8"
AMBER = "#ffd166"
CORAL = "#ff7a59"
EMPTY_SEG = "#1e2a63"
GREEN_SEG = "#39d353"
SKIN = "#ffd7b0"

BASE_CSS = (
    "svg{shape-rendering:crispEdges}"
    "@media (prefers-reduced-motion:reduce){*{animation:none!important}}"
)


# --- PNG and path helpers ---------------------------------------------------
def read_png(path):
    data = open(path, "rb").read()
    pos, idat, width, height = 8, b"", 0, 0
    while pos < len(data):
        length, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if kind == b"IHDR":
            width, height = struct.unpack(">II", body[:8])
            assert body[8] == 8 and body[9] == 6 and body[12] == 0, f"{path}: unsupported PNG"
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = zlib.decompress(idat)
    stride = width * 4
    rows, prev = [], bytearray(stride)
    for y in range(height):
        start = y * (stride + 1)
        filt = raw[start]
        row = bytearray(raw[start + 1:start + 1 + stride])
        for i in range(stride):
            a = row[i - 4] if i >= 4 else 0
            b = prev[i]
            c = prev[i - 4] if i >= 4 else 0
            if filt == 1:
                row[i] = (row[i] + a) & 255
            elif filt == 2:
                row[i] = (row[i] + b) & 255
            elif filt == 3:
                row[i] = (row[i] + (a + b) // 2) & 255
            elif filt == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(row))
        prev = row
    return width, height, rows


def rgb(hex_color):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def nearest(pixel, palette):
    return min(palette, key=lambda c: sum((p - q) ** 2 for p, q in zip(pixel, rgb(c))))


def paths(fn, width, height, unit=1, ox=0, oy=0):
    """One <path> per colour from fn(x, y) -> colour or None, merging horizontal runs."""
    by_colour = {}
    for y in range(height):
        x = 0
        while x < width:
            colour = fn(x, y)
            if not colour:
                x += 1
                continue
            end = x + 1
            while end < width and fn(end, y) == colour:
                end += 1
            w = (end - x) * unit
            by_colour.setdefault(colour, []).append(f"M{ox + x * unit} {oy + y * unit}h{w}v{unit}h-{w}z")
            x = end
    return "".join(f'<path fill="{c}" d="{"".join(d)}"/>' for c, d in by_colour.items())


def sprite(rows, colours, unit=4, ox=0, oy=0):
    def fn(x, y):
        ch = rows[y][x]
        return None if ch == "." else colours[ch]
    return paths(fn, len(rows[0]), len(rows), unit, ox, oy)


def text_layer(path, palette):
    """Trace a transparent text export into crisp vector pixels."""
    w, h, rows = read_png(path)

    def fn(x, y):
        r, g, b, a = rows[y][x * 4:x * 4 + 4]
        return nearest((r, g, b), palette) if a >= 128 else None
    return paths(fn, w, h)


def trace_png(path, scale=2, max_colours=20):
    """Trace an exported panel into vector pixels; returns (width, height, grid, svg)."""
    w, h, rows = read_png(path)
    w, h = w // scale, h // scale
    grid, counts = [], Counter()
    for y in range(h):
        row = rows[y * scale]
        line = []
        for x in range(w):
            r, g, b, a = row[x * scale * 4:x * scale * 4 + 4]
            colour = None if a < 128 else "#%02x%02x%02x" % (r, g, b)
            line.append(colour)
            if colour:
                counts[colour] += 1
        grid.append(line)
    palette = [c for c, _ in counts.most_common(max_colours)]
    cache = {}

    def snap(colour):
        if colour is None:
            return None
        if colour not in cache:
            cache[colour] = colour if colour in palette else nearest(rgb(colour), palette)
        return cache[colour]

    grid = [[snap(c) for c in line] for line in grid]
    return w, h, grid, paths(lambda x, y: grid[y][x], w, h)


def svg(width, height, css, body, title):
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{title}">'
        f"<title>{title}</title><style>{BASE_CSS}{css}</style>{body}</svg>\n"
    )


class Rng:
    """Same generator as the Figma script, so scenes match the design."""

    def __init__(self, seed):
        self.seed = seed

    def __call__(self):
        self.seed = (self.seed * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.seed / 4294967296


# --- Shared artwork ---------------------------------------------------------
CHIH_TOP = [
    "....kkkkkkkk....", "...khhhhhhhhk...", "..khhHHhhhhhhk..", "..khHhhhhhhhhk..",
    "..khhhhhhhhhhk..", "..khhsssssshhk..", "..khsskssksshk..", "..kssskssksssk..",
    "..kSssssssssSk..", "...kcccccccck...", "..kCccccccccCk..", ".kgkggggggggkgk.",
    ".kgkgGggggGgkgk.", ".kskggggggggksk.", "..kkGGGGGGGGkk..", "...kppppppppk...",
    "...kpppkkpppk...",
]
LEGS_STEP_A = ["...kbbbkkkkkk...", "...kkkk........."]
LEGS_STEP_B = ["...kkkkkkbbbk...", ".........kkkk..."]
CHIH_COLOURS = {
    "k": INK, "h": "#2b2140", "H": "#5a4a86", "s": SKIN, "S": "#e8a87c", "c": CORAL,
    "C": "#c94f3d", "g": "#26a641", "G": "#006d32", "p": "#2d3a5f", "b": "#1a1c2c",
}
CAT_BODY = ["o...o.....", "oo.oo.....", "ooooo.....", "okoko.....", "oooooooooo", ".ooooooooo"]
CAT_TAIL_A = [".o", "oo", "o.", "o.", "o.", ".."]
CAT_TAIL_B = ["..", "..", "..", ".o", "oo", ".."]
CAT_LEGS_A = [".oo.....oo.."]
CAT_LEGS_B = ["..oo...oo..."]
CAT_COLOURS = {"o": "#ffb35c", "k": INK}
PAD = "." * 12


def cat_rows(body, tail, legs, flip=False):
    rows = [b + t for b, t in zip(body, tail)] + legs
    rows = [r.ljust(12, ".") for r in rows]
    return [r[::-1] for r in rows] if flip else rows


def is_corner(x, y, w, h):
    return x in (0, w - 1) and y in (0, h - 1)


def frame_layer(w, h):
    def fn(x, y):
        if is_corner(x, y, w, h):
            return None
        if x in (0, w - 1) or y in (0, h - 1):
            return INK
        if x in (1, w - 2) and y in (1, h - 2):
            return INK
        return None
    return paths(fn, w, h, 4)


# --- Hero -------------------------------------------------------------------
def weekly_levels(path, weeks=52):
    """Tower level 0-4 for each of the last 52 weeks, scaled to this person's busiest week.

    Reads the GitHub GraphQL contributionCalendar response. The square root keeps one
    unusually busy week from flattening every other tower.
    """
    calendar = json.load(open(path))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    totals = [sum(d["contributionCount"] for d in w["contributionDays"]) for w in calendar["weeks"]][-weeks:]
    totals = [0] * (weeks - len(totals)) + totals
    busiest = max(totals) or 1
    return [math.ceil(4 * math.sqrt(t / busiest)) for t in totals]


def build_hero():
    W, H, BASE = 210, 100, 88
    rnd = Rng(20261104)
    bands = [(0, "#0b1030"), (22, "#111a45"), (40, "#16305f"), (56, "#1a5070"), (70, "#2a7d7e"), (82, "#57b08c")]

    def sky(x, y):
        i = 0
        while i < len(bands) - 1 and y >= bands[i + 1][0]:
            i += 1
        if i + 1 < len(bands):
            d = bands[i + 1][0] - y
            if d == 1 and (x + y) % 2 == 0:
                return bands[i + 1][1]
            if d == 2 and (x + y) % 4 == 0:
                return bands[i + 1][1]
        return bands[i][1]

    mx, my, mr = 174, 24, 13
    stars = {}
    for _ in range(90):
        x = math.floor(rnd() * W)
        y = 1 + math.floor(rnd() * 54)
        if math.hypot(x - mx, y - my) < mr + 6:
            continue
        if x < 140 and 6 < y < 62:
            continue
        r = rnd()
        stars[(x, y)] = CREAM if r < .7 else AMBER if r < .85 else "#a9b4d6"
    sparkles = [(150, 8), (128, 42), (200, 50)]

    star_svg = {0: [], 1: [], 2: []}
    for i, ((x, y), colour) in enumerate(sorted(stars.items())):
        star_svg[i % 3].append(f'<rect x="{x * 4}" y="{y * 4}" width="4" height="4" fill="{colour}"/>')
    sparkle_svg = ""
    for x, y in sparkles:
        arms = "".join(
            f'<rect x="{(x + a) * 4}" y="{(y + b) * 4}" width="4" height="4" fill="#a9b4d6"/>'
            for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
        )
        sparkle_svg += f'<g class="sp">{arms}<rect x="{x * 4}" y="{y * 4}" width="4" height="4" fill="{CREAM}"/></g>'

    def moon(x, y):
        dx, dy = x - mx, y - my
        d = math.hypot(dx, dy)
        if d <= mr:
            crater = math.hypot(dx + 4, dy + 3) < 3 or math.hypot(dx - 5, dy - 4) < 2.2 or math.hypot(dx - 3, dy + 6) < 1.6
            return "#f2a541" if crater or dx + dy > 11 else AMBER
        if d <= mr + 3 and (x + y) % 2 == 0:
            return "#1c2f6a"
        return None

    def cloud_at(x, y):
        for cx, cy, length in ((116, 60, 26), (176, 66, 22), (60, 62, 20)):
            if y == cy and cx <= x < cx + length:
                return "#2f6a86"
            if y == cy - 1 and cx + 4 <= x < cx + length - 6:
                return "#2f6a86"
            if y == cy + 1 and cx + 2 <= x < cx + length - 3:
                return "#2f6a86"
        return None

    cloud_svg = paths(cloud_at, W, H, 4)

    # Contribution skyline: one tower per real week, newest on the right. Each tower has
    # its own random stream, so a change in one week leaves the other towers alone.
    levels = weekly_levels("tools/contributions.json")
    tones = [
        ("#10253a", "#0b1a2b", "#1a3450"), ("#0e4429", "#0a3320", "#155c38"), ("#006d32", "#004f24", "#0a8a42"),
        ("#26a641", "#1c7d31", "#39d353"), ("#39d353", "#26a641", "#7ee787"),
    ]
    towers = []
    for i, level in enumerate(levels):
        rnd = Rng((i + 1) * 2654435761 & 0xFFFFFFFF)
        rnd()
        x0 = 1 + i * 4
        h = 6 + level * 9 + math.floor(rnd() * 4)
        top = BASE - h
        body, side, cap = tones[level]
        parts = [
            f'<path fill="{body}" d="M{x0 * 4} {top * 4}h12v{(BASE - top) * 4 + 60}h-12z"/>',
            f'<path fill="{side}" d="M{(x0 + 3) * 4} {top * 4}h4v{(BASE - top) * 4 + 60}h-4z"/>',
            f'<path fill="{cap}" d="M{x0 * 4} {top * 4}h16v4h-16z"/>',
        ]
        y = top + 2
        while y < BASE - 1:
            lit = rnd() < .4
            if lit:
                cls = {0: ' class="w1"', 1: ' class="w2"', 2: ' class="w3"'}.get((i + y) % 6, "")
                parts.append(f'<rect{cls} x="{(x0 + 1) * 4}" y="{y * 4}" width="4" height="4" fill="{AMBER}"/>')
            else:
                parts.append(f'<rect x="{(x0 + 1) * 4}" y="{y * 4}" width="4" height="4" fill="{side}"/>')
            y += 3
        if level == 4 and i % 2 == 0:
            parts.append(f'<rect x="{(x0 + 1) * 4}" y="{(top - 3) * 4}" width="4" height="12" fill="#0e4429"/>')
            parts.append(f'<rect class="tip" x="{(x0 + 1) * 4}" y="{(top - 4) * 4}" width="4" height="4" fill="{CORAL}"/>')
        towers.append(
            f'<g class="t" style="animation-delay:{i * .035:.2f}s;--h:{(BASE - top + 5) * 4}px">{"".join(parts)}</g>'
        )

    def ground(x, y):
        if y < BASE or is_corner(x, y, W, H):
            return None
        if y == BASE:
            return "#2d3a5f"
        if y == 94 and x % 10 < 5:
            return "#3a4a7a"
        return "#141b45"

    char_y = (BASE - 19) * 4
    walker = (
        f'<g class="walk"><g>{sprite(CHIH_TOP, CHIH_COLOURS, 4, 56, char_y)}'
        f'<g class="fa">{sprite(LEGS_STEP_A, CHIH_COLOURS, 4, 56, char_y + 17 * 4)}</g>'
        f'<g class="fb">{sprite(LEGS_STEP_B, CHIH_COLOURS, 4, 56, char_y + 17 * 4)}</g></g>'
    )
    cat_y = (BASE - 7) * 4
    walker += (
        f'<g class="fa">{sprite(cat_rows(CAT_BODY, CAT_TAIL_A, CAT_LEGS_A, True), CAT_COLOURS, 4, 144, cat_y)}</g>'
        f'<g class="fb">{sprite(cat_rows(CAT_BODY, CAT_TAIL_B, CAT_LEGS_B, True), CAT_COLOURS, 4, 144, cat_y)}</g></g>'
    )

    shoot = '<g class="shoot">' + "".join(
        f'<rect x="{560 + n * 8}" y="{20 + n * 4}" width="8" height="4" fill="{c}"/>'
        for n, c in enumerate((CREAM, "#a9b4d6", "#3a4a7a"))
    ) + "</g>"
    # The head of the star leads, so it moves toward the lower left.

    css = (
        "@keyframes rise{from{transform:translateY(var(--h))}to{transform:translateY(0)}}"
        ".t{animation:rise .9s steps(10) both}"
        "@keyframes tw{0%,60%,100%{opacity:1}70%,90%{opacity:.15}}"
        ".s0{animation:tw 3.1s steps(1) infinite}.s1{animation:tw 4.3s steps(1) -1.2s infinite}"
        ".s2{animation:tw 5.7s steps(1) -2.6s infinite}.sp{animation:tw 2.3s steps(1) -.8s infinite}"
        "@keyframes flick{0%,70%,100%{opacity:1}75%,95%{opacity:0}}"
        ".w1{animation:flick 5s steps(1) -1s infinite}.w2{animation:flick 7s steps(1) -3s infinite}"
        ".w3{animation:flick 9s steps(1) -6s infinite}"
        "@keyframes tip{0%,49%{opacity:1}50%,100%{opacity:.2}}.tip{animation:tip 1.4s steps(1) infinite}"
        "@keyframes drift{from{transform:translateX(0)}to{transform:translateX(840px)}}"
        ".cl{animation:drift 70s steps(210) infinite}"
        "@keyframes walk{from{transform:translateX(-260px)}to{transform:translateX(860px)}}"
        ".walk{animation:walk 18s steps(280) infinite}"
        "@keyframes fa{0%,49%{opacity:1}50%,100%{opacity:0}}@keyframes fb{0%,49%{opacity:0}50%,100%{opacity:1}}"
        ".fa{animation:fa .5s steps(1) infinite}.fb{opacity:0;animation:fb .5s steps(1) infinite}"
        "@keyframes blink{0%,59%{opacity:1}60%,100%{opacity:0}}.prompt{animation:blink 1.3s steps(1) infinite}"
        "@keyframes shoot{0%,88%{opacity:0;transform:translate(0,0)}89%{opacity:1;transform:translate(0,0)}"
        "95%{opacity:1;transform:translate(-240px,120px)}96%,100%{opacity:0;transform:translate(-240px,120px)}}"
        ".shoot{opacity:0;animation:shoot 13s linear 3s infinite}"
    )
    body = (
        paths(lambda x, y: None if is_corner(x, y, W, H) else sky(x, y), W, H, 4)
        + "".join(f'<g class="s{k}">{"".join(v)}</g>' for k, v in star_svg.items())
        + sparkle_svg + shoot
        + paths(moon, W, H, 4)
        + f'<g class="cl"><g transform="translate(-840 0)">{cloud_svg}</g>{cloud_svg}</g>'
        + "".join(towers)
        + paths(ground, W, H, 4)
        + walker
        + frame_layer(W, H)
        + text_layer("tools/layers/hero-text.png", [CREAM, CORAL])
    )
    return svg(840, 400, css, body, "Hello, I'm Chih. Developer, love and embrace AI, tinker with agents.")


# --- Character sheet --------------------------------------------------------
def build_sheet():
    w, h, grid, base = trace_png("assets/03-character-sheet.png")
    green = rgb(GREEN_SEG)

    def is_green(x, y):
        c = grid[y][x]
        return c is not None and sum((p - q) ** 2 for p, q in zip(rgb(c), green)) < 300

    def is_greenish(x, y):
        c = grid[y][x]
        if c is None:
            return False
        r, g, b = rgb(c)
        return g > r + 16 and g > b

    # Find each bar's slots: a filled or empty segment is a run on the bar's middle row.
    bars, y = [], 0
    while y < h:
        if any(is_green(x, y) for x in range(w // 2, w)):
            top = y
            while y < h and any(is_green(x, y) for x in range(w // 2, w)):
                y += 1
            mid = (top + y) // 2
            runs, x = [], w // 2
            while x < w:
                if is_green(x, mid):
                    start = x
                    while x < w and is_green(x, mid):
                        x += 1
                    # Segment edges are soft, so grow the cover over any green-tinted pixels.
                    while start > 0 and is_greenish(start - 1, mid):
                        start -= 1
                    while x < w and is_greenish(x, mid):
                        x += 1
                    runs.append((start, x - start))
                else:
                    x += 1
            bars.append((top, y - top, runs))
        else:
            y += 1
    assert len(bars) == 4, f"expected 4 bars, found {len(bars)}"

    longest = max(len(r) for _, _, r in bars)
    css = "".join(
        f"@keyframes c{i}{{0%,{4 + i * 3}%{{opacity:1}}{5 + i * 3}%,92%{{opacity:0}}93%,100%{{opacity:1}}}}"
        f".c{i}{{opacity:0;animation:c{i} 9s steps(1) infinite}}"
        for i in range(longest)
    )
    covers = ""
    for top, height, runs in bars:
        for i, (x, width) in enumerate(runs):
            covers += f'<rect class="c{i}" x="{x}" y="{top}" width="{width}" height="{height}" fill="{EMPTY_SEG}"/>'

    # Blink: cover the eyes with skin colour. Sprite is 16 cells at 8px in the portrait.
    ox, oy = 56, 53
    for cell_x in (6, 9):
        assert grid[oy + 6 * 8 + 4][ox + cell_x * 8 + 4] == INK, "portrait eye not where expected"
    eyes = "".join(
        f'<rect x="{ox + cell_x * 8}" y="{oy + 6 * 8}" width="8" height="12" fill="{SKIN}"/>' for cell_x in (6, 9)
    )
    css += (
        "@keyframes eye{0%,91%{opacity:0}92%,95%{opacity:1}96%,100%{opacity:0}}"
        ".eye{opacity:0;animation:eye 4.2s steps(1) infinite}"
    )
    return svg(w, h, css, base + covers + f'<g class="eye">{eyes}</g>',
               "Character sheet. Full-stack developer. Skill bars for frontend, backend, learning agents and learning LLMs.")


# --- Inventory --------------------------------------------------------------
def build_inventory():
    w, h, grid, base = trace_png("assets/04-inventory.png")
    probe_x = 24 + 61
    ys = [y for y in range(30, h - 12) if grid[y][probe_x] == INK]
    top, bottom = ys[0], ys[-1] + 1
    slot_h = bottom - top
    slot_w, gap, count = 122, 12, 6
    cursor = ""
    for i in range(count):
        x = 24 + i * (slot_w + gap)
        d = (
            f"M{x + 4} {top}h{slot_w - 8}v4h-{slot_w - 8}z"
            f"M{x + 4} {bottom - 4}h{slot_w - 8}v4h-{slot_w - 8}z"
            f"M{x} {top + 4}h4v{slot_h - 8}h-4z"
            f"M{x + slot_w - 4} {top + 4}h4v{slot_h - 8}h-4z"
            f"M{x + slot_w // 2 - 4} {top - 8}h8v4h-8z"
            f"M{x + slot_w // 2 - 8} {top - 12}h16v4h-16z"
        )
        cursor += f'<path class="cur" style="animation-delay:{i * 1.2:.1f}s" fill="{AMBER}" d="{d}"/>'
    css = (
        "@keyframes hop{0%,16%{opacity:1}17%,100%{opacity:0}}"
        f".cur{{opacity:0;animation:hop {count * 1.2:.1f}s steps(1) infinite}}"
    )
    return svg(w, h, css, base + cursor, "Inventory: TypeScript, Vue, Java, Python, databases, Rust.")


BUILDERS = {"01-hero": build_hero, "03-character-sheet": build_sheet, "04-inventory": build_inventory}
for name, builder in BUILDERS.items():
    if len(sys.argv) > 1 and sys.argv[1] not in name:
        continue
    content = builder()
    open(f"assets/{name}.svg", "w").write(content)
    print(f"assets/{name}.svg  {len(content) / 1024:.1f} KB")
