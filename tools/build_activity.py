#!/usr/bin/env python3
"""Build the 3D contribution chart for the GitHub profile README. Standard library only.

Run from the folder that holds README.md:  python3 tools/build_activity.py

Reads tools/contributions.json, the contributionCalendar response from GitHub's
GraphQL API, and writes one SVG per GitHub theme. One bar per day: weeks run from
back left to front right, so the newest days are nearest the viewer.
"""
import json
import math

WEEK = (12.8, 1.8)  # screen step from one week to the next
DAY = (-6.5, 4.2)  # screen step from one weekday to the next
TILE = 0.84  # share of each cell the bar covers, leaving a gap between bars
MIN_BAR, MAX_BAR = 8, 76
EMPTY_DEPTH = 2
PAD = 4

THEMES = {
    "dark": {
        "empty": ("#21262d", "#191d23", "#14181d"),
        "levels": ("#0e4429", "#006d32", "#26a641", "#39d353"),
    },
    "light": {
        "empty": ("#ebedf0", "#dcdfe3", "#d0d4d9"),
        "levels": ("#9be9a8", "#40c463", "#30a14e", "#216e39"),
    },
}


def shade(colour, factor):
    channels = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % tuple(round(c * factor) for c in channels)


def face(points):
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in points) + "z"


def prism(i, j, height):
    """Return the top, left and right faces of the bar at week i, day j."""
    ox, oy = i * WEEK[0] + j * DAY[0], i * WEEK[1] + j * DAY[1]
    wx, wy, dx, dy = WEEK[0] * TILE, WEEK[1] * TILE, DAY[0] * TILE, DAY[1] * TILE
    back = (ox, oy)
    right = (ox + wx, oy + wy)
    left = (ox + dx, oy + dy)
    front = (ox + wx + dx, oy + wy + dy)
    lift = lambda p: (p[0], p[1] - height)
    return (
        face([lift(back), lift(right), lift(front), lift(left)]),
        face([lift(left), lift(front), front, left]),
        face([lift(front), lift(right), right, front]),
        front,
    )


def build(theme, path="tools/contributions.json"):
    calendar = json.load(open(path))["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    weeks = calendar["weeks"]
    last = len(weeks) - 1
    cells = []
    for i, week in enumerate(weeks):
        # Only the first and last weeks can be partial. The first ends on Saturday, so
        # align it to the bottom of its column; the last starts on Sunday as usual.
        offset = 7 - len(week["contributionDays"]) if i == 0 and i != last else 0
        for j, day in enumerate(week["contributionDays"]):
            cells.append((i, j + offset, day["contributionCount"]))

    busiest = max((c for _, _, c in cells), default=0) or 1
    total = sum(c for _, _, c in cells)

    # Bounds, so the viewBox hugs the chart.
    origins = [i * WEEK[0] + j * DAY[0] for i, j, _ in cells]
    min_x = min(origins) + DAY[0] * TILE - PAD
    max_x = max(origins) + WEEK[0] * TILE + PAD

    palette = THEMES[theme]
    flat = {0: [], 1: [], 2: []}
    bars = []
    top_y, bottom_y = 0, 0
    for i, j, count in sorted(cells, key=lambda c: (c[0] + c[1], c[0])):
        if count == 0:
            parts = prism(i, j, EMPTY_DEPTH)
            for n in range(3):
                flat[n].append(parts[n])
            bottom_y = max(bottom_y, parts[3][1])
            continue
        ratio = math.sqrt(count / busiest)
        height = MIN_BAR + (MAX_BAR - MIN_BAR) * ratio
        colour = palette["levels"][min(3, math.ceil(4 * ratio) - 1)]
        top, left, right, foot = prism(i, j, height)
        top_y = min(top_y, i * WEEK[1] + j * DAY[1] - height)
        bottom_y = max(bottom_y, foot[1])
        bars.append(
            f'<g class="b" style="transform-origin:{foot[0]:.1f}px {foot[1]:.1f}px;animation-delay:{i * .018:.2f}s">'
            f'<path fill="{colour}" d="{top}"/>'
            f'<path fill="{shade(colour, .72)}" d="{left}"/>'
            f'<path fill="{shade(colour, .54)}" d="{right}"/></g>'
        )

    top_y = min(top_y, 0) - PAD
    bottom_y += PAD
    width, height = max_x - min_x, bottom_y - top_y
    empties = "".join(f'<path fill="{palette["empty"][n]}" d="{"".join(flat[n])}"/>' for n in range(3))
    css = (
        "@keyframes g{from{transform:scaleY(0)}}"
        ".b{animation:g .7s cubic-bezier(.2,.8,.2,1) both}"
        "@media (prefers-reduced-motion:reduce){.b{animation:none}}"
    )
    title = f"{total} contributions in the last year"
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="{min_x:.1f} {top_y:.1f} {width:.1f} {height:.1f}" role="img" aria-label="{title}">'
        f"<title>{title}</title><style>{css}</style>{empties}{''.join(bars)}</svg>\n"
    )


for theme in THEMES:
    content = build(theme)
    open(f"assets/activity-{theme}.svg", "w").write(content)
    print(f"assets/activity-{theme}.svg  {len(content) / 1024:.1f} KB")
