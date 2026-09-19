"""Recalibrate using centerline + known 110/69 dimensions on drawing."""
import math
from pathlib import Path
from collections import Counter

from PIL import Image, ImageDraw

img = Image.open(Path(r"G:/soft/S200工程/tools/beam_drawing2.png")).convert("RGB")
w, h = img.size
px = img.load()

# Find vertical centerline: dashed dark vertical near image center
col_dark = Counter()
for y in range(80, 300):
    for x in range(400, 700):
        r, g, b = px[x, y]
        if r < 90 and g < 90 and b < 90:
            col_dark[x] += 1
# Peak near middle
peaks = col_dark.most_common(20)
print("vertical dark peaks:", peaks[:10])
cx = max(peaks, key=lambda t: t[1])[0]
print("cx from centerline dens", cx)

# Find horizontal centerline
row_dark = Counter()
for y in range(120, 250):
    for x in range(160, 940):
        r, g, b = px[x, y]
        if r < 90 and g < 90 and b < 90:
            row_dark[y] += 1
ypeaks = row_dark.most_common(10)
print("horizontal dark peaks:", ypeaks)
cy = max(ypeaks, key=lambda t: t[1])[0]
print("cy", cy)

# Find "110" dimension extension: look for the two vertical dim lines of the 110 span
# Simpler: detect hole marks only near y = cy ± expected row
# First get mm scale from overall 310 width using plate sides near cy

def is_dark(x, y, thr=95):
    if not (0 <= x < w and 0 <= y < h):
        return False
    r, g, b = px[x, y]
    return r < thr and g < thr and b < thr

# Plate left/right at cy: first/last solid vertical edge
left = None
right = None
for x in range(w):
    if is_dark(x, cy) and is_dark(x, cy - 2) and is_dark(x, cy + 2):
        # check continuity upward a bit (side wall)
        if sum(is_dark(x, cy + dy) for dy in range(-20, 21)) > 25:
            left = x
            break
for x in range(w - 1, -1, -1):
    if sum(is_dark(x, cy + dy) for dy in range(-20, 21)) > 25:
        right = x
        break
print("plate sides at cy", left, right, "width_px", right - left if left and right else None)
mm = 310.0 / (right - left)
print("mm/px", mm)

# Detect holes on top and bottom rows using circle+cross, restricted y bands
# Row y from 69mm spacing: ±34.5 mm
row_dy = 34.5 / mm
print("row_dy px", row_dy)
y_top = cy - row_dy
y_bot = cy + row_dy
print("expected row y", y_top, y_bot)

def detect_row(y_row, tol=8):
    hits = []
    y0, y1 = int(y_row - tol), int(y_row + tol)
    for y in range(y0, y1 + 1):
        for x in range(left + 8, right - 8):
            # cross arms
            arm = 0
            for d in range(1, 5):
                for xx, yy in ((x + d, y), (x - d, y), (x, y + d), (x, y - d)):
                    if is_dark(xx, yy):
                        arm += 1
            ring = 0
            for a in range(0, 360, 30):
                rad = math.radians(a)
                for rr in (3, 4):
                    if is_dark(int(x + rr * math.cos(rad)), int(y + rr * math.sin(rad))):
                        ring += 1
            if arm >= 8 and ring >= 5:
                hits.append((arm + ring, x, y))
    hits.sort(key=lambda t: -t[0])
    kept = []
    for s, x, y in hits:
        if all(abs(x - kx) > 8 for _, kx, ky in kept):
            kept.append((s, x, y))
    # convert
    out = []
    for s, x, y in kept:
        mx = (x - cx) * mm
        my = (cy - y) * mm
        out.append((round(mx, 2), round(my, 2), x, y, s))
    out.sort(key=lambda t: t[0])
    return out

top = detect_row(y_top)
bot = detect_row(y_bot)
print("\nTOP holes:")
for t in top:
    print(" ", t)
print("\nBOT holes:")
for t in bot:
    print(" ", t)

# Identify which bot holes are inside ±55 and not part of known model set
model_xs = {-132, -102, -55, 55, 102, 132}  # approx existing
print("\nBottom holes with |x|<55 (candidates for missing):")
for t in bot:
    if abs(t[0]) < 55:
        print(" ", t)

# Also refine: find exact ±55 by closest to ±55
def nearest(lst, target):
    return min(lst, key=lambda t: abs(t[0] - target))

print("\nClosest to ±55:")
for tgt in (-55, 55):
    for name, lst in [("top", top), ("bot", bot)]:
        if lst:
            n = nearest(lst, tgt)
            print(f"  {name} near {tgt}: {n}")

# Annotate
out = img.copy()
dr = ImageDraw.Draw(out)
for lst, color in ((top, (0, 200, 0)), (bot, (0, 100, 255))):
    for mx, my, x, y, s in lst:
        dr.ellipse([x - 7, y - 7, x + 7, y + 7], outline=color, width=2)
        if abs(mx) < 55:
            dr.ellipse([x - 11, y - 11, x + 11, y + 11], outline=(255, 0, 0), width=2)
dr.line([(cx, y_top - 20), (cx, y_bot + 20)], fill=(255, 128, 0), width=1)
out.save(Path(r"G:/soft/S200工程/tools/beam_rows_annot.png"))
print("saved beam_rows_annot.png")
