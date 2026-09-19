"""Calibrate drawing and find all hole crosshair centers on top/bottom rows."""
import math
from collections import Counter
from pathlib import Path

from PIL import Image, ImageDraw

img = Image.open(Path(r"G:/soft/S200工程/tools/beam_drawing2.png")).convert("RGB")
w, h = img.size
px = img.load()
print("size", w, h)

# 1) Find plate rectangle via longest dark horizontal edges
def longest_dark_run(y, thresh=90):
    best = (0, 0, 0)  # len, x0, x1
    run = 0
    x0 = 0
    for x in range(w):
        r, g, b = px[x, y]
        dark = r < thresh and g < thresh and b < thresh
        if dark:
            if run == 0:
                x0 = x
            run += 1
        else:
            if run > best[0]:
                best = (run, x0, x - 1)
            run = 0
    if run > best[0]:
        best = (run, x0, w - 1)
    return best


edge_rows = []
for y in range(h):
    ln, x0, x1 = longest_dark_run(y)
    if ln > w * 0.55:
        edge_rows.append((y, ln, x0, x1))

# Cluster into top/bottom plate edges (not dimension lines far outside)
# Prefer runs near vertical middle of content
print("long dark rows sample:", edge_rows[:: max(1, len(edge_rows) // 10)][:12])

# Use the longest run as plate width reference
edge_rows.sort(key=lambda t: -t[1])
best_run = edge_rows[0]
print("best run", best_run)

# Among long runs, take uppermost and lowermost that share similar x0/x1
long = [e for e in edge_rows if e[1] > best_run[1] * 0.9]
y_top = min(e[0] for e in long)
y_bot = max(e[0] for e in long)
# median x bounds
xs0 = sorted(e[2] for e in long)
xs1 = sorted(e[3] for e in long)
x_left = xs0[len(xs0) // 2]
x_right = xs1[len(xs1) // 2]
print(f"plate px x[{x_left},{x_right}] y[{y_top},{y_bot}]")

mm_x = 310.0 / (x_right - x_left)
mm_y = 94.0 / (y_bot - y_top)
cx = (x_left + x_right) / 2
cy = (y_top + y_bot) / 2
print(f"mm/px x={mm_x:.5f} y={mm_y:.5f} center=({cx:.1f},{cy:.1f})")

# 2) Detect crosshair centers: dark + shape and/or small circle
candidates = []
for y in range(y_top + 5, y_bot - 5):
    for x in range(x_left + 5, x_right - 5):
        r, g, b = px[x, y]
        # center can be light (intersection) — score by dark cross arms
        arm = 0
        for d in range(1, 6):
            for xx, yy in ((x + d, y), (x - d, y), (x, y + d), (x, y - d)):
                if 0 <= xx < w and 0 <= yy < h:
                    rr, gg, bb = px[xx, yy]
                    if rr < 100 and gg < 100 and bb < 100:
                        arm += 1
        ring = 0
        for a in range(0, 360, 20):
            rad = math.radians(a)
            for rad_r in (3, 4, 5):
                xx = int(x + rad_r * math.cos(rad))
                yy = int(y + rad_r * math.sin(rad))
                if 0 <= xx < w and 0 <= yy < h:
                    rr, gg, bb = px[xx, yy]
                    if rr < 100 and gg < 100 and bb < 100:
                        ring += 1
        score = arm + ring * 0.35
        if arm >= 10 and ring >= 6:
            candidates.append((score, x, y, arm, ring))

candidates.sort(key=lambda t: -t[0])
holes = []
for c in candidates:
    if all(math.hypot(c[1] - h0[0], c[2] - h0[1]) > 10 for h0 in holes):
        holes.append((c[1], c[2], c[0], c[3], c[4]))

print(f"detected crosshairs: {len(holes)}")

# Convert to mm and classify by row
rows = {"top": [], "bot": [], "mid": [], "other": []}
for x, y, score, arm, ring in holes:
    mx = (x - cx) * mm_x
    my = (cy - y) * mm_y
    item = (round(mx, 2), round(my, 2), x, y, round(score, 1))
    if abs(my - 34.5) < 6:
        rows["top"].append(item)
    elif abs(my + 34.5) < 6:
        rows["bot"].append(item)
    elif abs(my) < 8:
        rows["mid"].append(item)
    else:
        rows["other"].append(item)

for k in rows:
    rows[k].sort(key=lambda t: t[0])
    print(f"\n{k} row ({len(rows[k])}):")
    for it in rows[k]:
        print(f"  x={it[0]:7.2f} y={it[1]:7.2f}  px=({it[2]},{it[3]}) score={it[4]}")

# 3) Refine scale using known ±55 if found near them
known = []
for it in rows["top"] + rows["bot"]:
    if abs(abs(it[0]) - 55) < 8:
        known.append(it)
print("\nnear ±55:", known)

# Annotate
out = img.copy()
dr = ImageDraw.Draw(out)
for x, y, *_ in holes:
    dr.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(0, 180, 0), width=2)
# mark expected ±55,±34.5
for sx, sy in [(55, 34.5), (-55, 34.5), (55, -34.5), (-55, -34.5)]:
    px_x = cx + sx / mm_x
    px_y = cy - sy / mm_y
    dr.ellipse([px_x - 8, px_y - 8, px_x + 8, px_y + 8], outline=(255, 0, 0), width=2)
out.save(Path(r"G:/soft/S200工程/tools/beam_drawing2_annot.png"))
print("\nsaved annot")
