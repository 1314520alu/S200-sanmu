"""Measure hole positions on the CAD drawing by detecting dark circular marks."""
from pathlib import Path
from collections import defaultdict
import math

from PIL import Image

img = Image.open(r"G:\soft\S200工程\tools\beam_drawing.png").convert("RGB")
w, h = img.size
px = img.load()

# Find plate rectangle: dark outline on light bg
# Scan for horizontal extent of main drawing content (dark pixels)
dark = []
for y in range(h):
    for x in range(w):
        r, g, b = px[x, y]
        if r < 80 and g < 80 and b < 80:
            dark.append((x, y))
print("dark pixels", len(dark))
xs = [p[0] for p in dark]
ys = [p[1] for p in dark]
print("dark bbox", min(xs), max(xs), min(ys), max(ys))

# Red arrow pixels
reds = []
for y in range(h):
    for x in range(w):
        r, g, b = px[x, y]
        if r > 180 and g < 100 and b < 100:
            reds.append((x, y))
print("red pixels", len(reds))
if reds:
    # cluster red into two arrow tips (lowest y clusters? arrows point up to holes)
    reds_sorted = sorted(reds, key=lambda p: p[0])
    # two clusters by x
    left = [p for p in reds if p[0] < w / 2]
    right = [p for p in reds if p[0] >= w / 2]
    for name, cluster in [("L", left), ("R", right)]:
        if not cluster:
            continue
        cx = sum(p[0] for p in cluster) / len(cluster)
        cy = sum(p[1] for p in cluster) / len(cluster)
        # tip = topmost red in cluster (smallest y) or point nearest hole
        tip = min(cluster, key=lambda p: p[1])
        print(f"arrow {name}: mean=({cx:.1f},{cy:.1f}) tip={tip}")

# Detect hole centers: look for small dark rings / filled circles in plate region
# Restrict to plate body (exclude dimension text outside)
# From visual, plate is roughly center of image
# Use: find circular blobs of dark pixels with radius ~2-6 px

# First estimate plate left/right from long horizontal edges
# Count dark per column in mid band
col = defaultdict(int)
for x, y in dark:
    if 80 < y < 280:
        col[x] += 1
cols = sorted(col.items())
# plate likely continuous high-density region
plate_xs = [x for x, c in cols if c > 5]
print("plate x approx", min(plate_xs), max(plate_xs), "width_px", max(plate_xs) - min(plate_xs))
plate_left, plate_right = min(plate_xs), max(plate_xs)
mm_per_px = 310.0 / (plate_right - plate_left)
print("mm_per_px", mm_per_px)

# Find hole-like local features: for each candidate, count dark in annulus
candidates = []
for y in range(100, 260):
    for x in range(plate_left + 10, plate_right - 10):
        # center should be relatively light (hole interior) or mixed
        r0, g0, b0 = px[x, y]
        bright = (r0 + g0 + b0) / 3
        if bright < 140:
            continue
        # ring of dark around
        ring = 0
        for a in range(0, 360, 30):
            rad = math.radians(a)
            for rad_r in (3, 4, 5):
                xx = int(x + rad_r * math.cos(rad))
                yy = int(y + rad_r * math.sin(rad))
                if 0 <= xx < w and 0 <= yy < h:
                    rr, gg, bb = px[xx, yy]
                    if rr < 90 and gg < 90 and bb < 90:
                        ring += 1
        if ring >= 10:
            candidates.append((x, y, ring, bright))

candidates.sort(key=lambda t: -t[2])
holes = []
for c in candidates:
    if all(math.hypot(c[0] - h0[0], c[1] - h0[1]) > 8 for h0 in holes):
        holes.append(c)
print("detected hole marks (px):", len(holes))

cx_plate = (plate_left + plate_right) / 2
# estimate vertical center of plate
row = defaultdict(int)
for x, y in dark:
    if plate_left <= x <= plate_right:
        row[y] += 1
rows = [y for y, c in row.items() if c > 20]
plate_top, plate_bot = min(rows), max(rows)
cy_plate = (plate_top + plate_bot) / 2
print("plate y", plate_top, plate_bot, "cy", cy_plate, "h_px", plate_bot - plate_top)
mm_per_px_y = 94.0 / (plate_bot - plate_top)
print("mm_per_px_y", mm_per_px_y)

for x, y, ring, br in sorted(holes, key=lambda t: (t[1], t[0])):
    mx = (x - cx_plate) * mm_per_px
    my = (cy_plate - y) * mm_per_px_y  # image y down -> CAD y up
    print(f"  px=({x},{y}) mm=({mx:.1f},{my:.1f}) ring={ring}")

# Map arrows to nearest holes
if reds:
    for name, cluster in [("L", left), ("R", right)]:
        if not cluster:
            continue
        tip = min(cluster, key=lambda p: p[1])
        nearest = min(holes, key=lambda h: math.hypot(h[0] - tip[0], h[1] - tip[1]))
        mx = (nearest[0] - cx_plate) * mm_per_px
        my = (cy_plate - nearest[1]) * mm_per_px_y
        print(f"arrow {name} tip {tip} -> hole px=({nearest[0]},{nearest[1]}) mm=({mx:.1f},{my:.1f})")
