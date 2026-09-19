"""Calibrate drawing using known 110mm and 69mm dims, locate arrowed holes."""
import math
from pathlib import Path
from PIL import Image, ImageDraw

img = Image.open(Path(r"G:/soft/S200工程/tools/beam_drawing.png")).convert("RGB")
w, h = img.size
px = img.load()

# Find red arrow tip clusters
reds = [
    (x, y)
    for y in range(h)
    for x in range(w)
    if px[x, y][0] > 200 and px[x, y][1] < 90 and px[x, y][2] < 90
]
left = [p for p in reds if p[0] < w / 2]
right = [p for p in reds if p[0] >= w / 2]
# Arrow HEAD = the pointy end nearest the target. For upward-pointing arrows, min y.
# Looking at crop description saying arrows point down - check both extrema
for name, cluster in [("L", left), ("R", right)]:
    ys = [p[1] for p in cluster]
    xs = [p[0] for p in cluster]
    print(f"{name}: x[{min(xs)},{max(xs)}] y[{min(ys)},{max(ys)}] n={len(cluster)}")
    top = min(cluster, key=lambda p: p[1])
    bot = max(cluster, key=lambda p: p[1])
    # densest x
    from collections import Counter
    xc = Counter(p[0] for p in cluster).most_common(3)
    print(f"  top={top} bot={bot} common_x={xc}")

# Manual: looking at original image, arrows are BELOW holes pointing UP.
# So target hole is near top of arrow (min y), search a bit above for crosshair.
# Crosshairs are dark circle + cross.

def find_crosshair_near(x0, y0, search=50):
    best = None
    for y in range(max(0, y0 - search), min(h, y0 + search)):
        for x in range(max(0, x0 - search), min(w, x0 + search)):
            r, g, b = px[x, y]
            # skip red
            if r > 180 and g < 100:
                continue
            # center of crosshair often dark-ish or has dark neighbors in + shape
            dark_cross = 0
            for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (2, 0), (-2, 0), (0, 2), (0, -2)]:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and 0 <= yy < h:
                    rr, gg, bb = px[xx, yy]
                    if rr < 100 and gg < 100 and bb < 100:
                        dark_cross += 1
            # also ring
            ring = 0
            for a in range(0, 360, 30):
                rad = math.radians(a)
                xx = int(x + 4 * math.cos(rad))
                yy = int(y + 4 * math.sin(rad))
                if 0 <= xx < w and 0 <= yy < h:
                    rr, gg, bb = px[xx, yy]
                    if rr < 100 and gg < 100 and bb < 100:
                        ring += 1
            score = dark_cross + ring * 0.5 - 0.1 * math.hypot(x - x0, y - y0)
            if dark_cross >= 5 and ring >= 5:
                if best is None or score > best[0]:
                    best = (score, x, y, dark_cross, ring)
    return best

# Use top of each arrow as search origin
results = {}
for name, cluster in [("L", left), ("R", right)]:
    tip = min(cluster, key=lambda p: p[1])
    best = find_crosshair_near(tip[0], tip[1] - 10, search=60)
    print(f"{name} tip {tip} -> {best}")
    results[name] = best

# Find the 110-dimension holes (bottom row of 4X) by searching for crosshairs
# near expected positions after we establish scale from overall 310 width.
# First get plate left/right from outer vertical edges of the rectangle.
# Find top horizontal edge of plate (long dark run)
row_dark = {}
for y in range(h):
    run = 0
    best_run = 0
    best_x0 = 0
    x0 = 0
    for x in range(w):
        r, g, b = px[x, y]
        if r < 90 and g < 90 and b < 90:
            if run == 0:
                x0 = x
            run += 1
            if run > best_run:
                best_run = run
                best_x0 = x0
        else:
            run = 0
    if best_run > 200:
        row_dark[y] = (best_x0, best_run)

# plate top = first long run in upper half
tops = sorted([(y, a, b) for y, (a, b) in row_dark.items() if y < h / 2], key=lambda t: t[0])
bots = sorted([(y, a, b) for y, (a, b) in row_dark.items() if y > h / 2], key=lambda t: -t[0])
print("top edge candidates", tops[:5])
print("bot edge candidates", bots[:5])

if tops and bots:
    y_top = tops[0][0]
    y_bot = bots[0][0]
    x_left = tops[0][1]
    x_right = tops[0][1] + tops[0][2]
    print(f"plate px: x[{x_left},{x_right}] y[{y_top},{y_bot}]")
    mm_x = 310.0 / (x_right - x_left)
    mm_y = 94.0 / (y_bot - y_top)
    cx = (x_left + x_right) / 2
    cy = (y_top + y_bot) / 2
    print(f"scale mm/px x={mm_x:.4f} y={mm_y:.4f} center=({cx:.1f},{cy:.1f})")

    for name, best in results.items():
        if not best:
            continue
        _, x, y, _, _ = best
        mx = (x - cx) * mm_x
        my = (cy - y) * mm_y
        print(f"arrowed {name}: px=({x},{y}) mm=({mx:.2f},{my:.2f})")

    # Expected ±55 at y=-34.5
    for sx in (-55, 55):
        px_x = cx + sx / mm_x
        px_y = cy - (-34.5) / mm_y
        print(f"expected ±55 bottom at px (~{px_x:.0f},{px_y:.0f})")
        best55 = find_crosshair_near(int(px_x), int(px_y), search=25)
        if best55:
            _, x, y, _, _ = best55
            print(f"  found ({x},{y}) mm=({(x-cx)*mm_x:.2f},{(cy-y)*mm_y:.2f})")

# annotate
out = img.copy()
dr = ImageDraw.Draw(out)
for name, best in results.items():
    if best:
        _, x, y, _, _ = best
        dr.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(0, 180, 0), width=2)
out.save(Path(r"G:/soft/S200工程/tools/arrow_targets.png"))
print("saved arrow_targets.png")
