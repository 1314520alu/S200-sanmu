"""Calibrate using 110mm span between the 4X hole verticals, then list all row holes."""
import math
from pathlib import Path
from collections import Counter

from PIL import Image, ImageDraw

img = Image.open(Path(r"G:/soft/S200工程/tools/beam_drawing2.png")).convert("RGB")
w, h = img.size
px = img.load()


def is_dark(x, y, thr=95):
    if not (0 <= x < w and 0 <= y < h):
        return False
    r, g, b = px[x, y]
    return r < thr and g < thr and b < thr


# Strong verticals from the 110 dimension (through-holes A1-A4)
col = Counter()
for y in range(90, 280):
    for x in range(350, 850):
        if is_dark(x, y):
            col[x] += 1

# Find two strongest peaks ~110mm apart
peaks = sorted(col.items(), key=lambda t: -t[1])[:30]
print("top verticals:", peaks[:15])

# Pick pair of peaks with high counts and separation matching ~110mm later
cands = [x for x, c in peaks if c > 40]
print("strong cols", sorted(cands))

# The 4X holes: left vertical around where "110" left extension is, right similarly
# From prior: 498 and 690 were strong — verify
for x in (498, 621, 690):
    print(f"col {x} count={col[x]}")

left110, right110 = 498, 690
mm = 110.0 / (right110 - left110)
cx = (left110 + right110) / 2
print(f"calibrated from 110: mm/px={mm:.5f} cx={cx:.1f}")

# Horizontal: use 69 between rows. Find top/bot hole y via dark density near expected
# First find cy from horizontal centerline
row = Counter()
for y in range(140, 230):
    for x in range(200, 900):
        if is_dark(x, y):
            row[y] += 1
cy = max(row.items(), key=lambda t: t[1])[0]
print("cy", cy, "count", row[cy])

# Detect holes along top and bottom using calibrated mm
# Row y from ±34.5
# But also search empirically for y with most hole-like marks


def detect_at_y(y_row, tol=6):
    hits = []
    for y in range(int(y_row - tol), int(y_row + tol) + 1):
        for x in range(160, 940):
            arm = sum(
                1
                for d in range(1, 5)
                for xx, yy in ((x + d, y), (x - d, y), (x, y + d), (x, y - d))
                if is_dark(xx, yy)
            )
            ring = 0
            for a in range(0, 360, 30):
                rad = math.radians(a)
                for rr in (3, 4):
                    if is_dark(int(x + rr * math.cos(rad)), int(y + rr * math.sin(rad))):
                        ring += 1
            if arm >= 8 and ring >= 5:
                hits.append((arm + ring * 0.5, x, y))
    hits.sort(key=lambda t: -t[0])
    kept = []
    for s, x, y in hits:
        if all(abs(x - kx) > 10 for _, kx, _ in kept):
            kept.append((s, x, y))
    out = []
    for s, x, y in sorted(kept, key=lambda t: t[1]):
        mx = (x - cx) * mm
        my = (cy - y) * mm
        out.append((round(mx, 2), round(my, 2), x, y, round(s, 1)))
    return out


# Scan which y band has most hits near expected rows
best_bands = []
for y_row in range(95, 120):
    n = len(detect_at_y(y_row, tol=2))
    best_bands.append((n, y_row))
best_bands.sort(reverse=True)
print("best top bands", best_bands[:5])
for y_row in range(250, 280):
    n = len(detect_at_y(y_row, tol=2))
    best_bands.append((n, y_row))
best_bands.sort(reverse=True)
print("best bands overall top5", best_bands[:8])

y_top = 34.5 / mm  # relative — use cy - 34.5/mm
y_top_px = cy - 34.5 / mm
y_bot_px = cy + 34.5 / mm
print(f"row px from 69/2: top={y_top_px:.1f} bot={y_bot_px:.1f}")

top = detect_at_y(y_top_px, tol=8)
bot = detect_at_y(y_bot_px, tol=8)
print("\nTOP:")
for t in top:
    print(" ", t)
print("\nBOT:")
for t in bot:
    print(" ", t)

print("\n=== Bottom holes inside |x|<55 (missing candidates) ===")
for t in bot:
    if abs(t[0]) < 52:
        print(" ", t)

print("\n=== All bottom unique X rounded to 0.5 ===")
xs = sorted({round(t[0] * 2) / 2 for t in bot})
print(xs)

# Cross-check plate width
# left/right edges
sides = []
for x in range(100, 200):
    if sum(is_dark(x, cy + dy) for dy in range(-30, 31)) > 40:
        sides.append(x)
        break
for x in range(950, 850, -1):
    if sum(is_dark(x, cy + dy) for dy in range(-30, 31)) > 40:
        sides.append(x)
        break
if len(sides) == 2:
    width_mm = (sides[1] - sides[0]) * mm
    print(f"plate width check: px {sides} -> {width_mm:.1f} mm (expect 310)")

out = img.copy()
dr = ImageDraw.Draw(out)
dr.line([(cx, 70), (cx, 300)], fill=(255, 140, 0), width=1)
dr.line([(left110, 70), (left110, 300)], fill=(200, 0, 200), width=1)
dr.line([(right110, 70), (right110, 300)], fill=(200, 0, 200), width=1)
for t in bot:
    x, y = t[2], t[3]
    colr = (255, 0, 0) if abs(t[0]) < 52 else (0, 120, 255)
    dr.ellipse([x - 8, y - 8, x + 8, y + 8], outline=colr, width=2)
for t in top:
    x, y = t[2], t[3]
    dr.ellipse([x - 8, y - 8, x + 8, y + 8], outline=(0, 180, 0), width=2)
out.save(Path(r"G:/soft/S200工程/tools/beam_cal110.png"))
print("saved beam_cal110.png")
