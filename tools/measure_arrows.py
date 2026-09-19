"""Zoom analysis around red arrow tips to find pointed hole centers."""
import math
from PIL import Image, ImageDraw

img = Image.open(r"G:\soft\S200工程\tools\beam_drawing.png").convert("RGB")
w, h = img.size
px = img.load()

# Red pixels
reds = [(x, y) for y in range(h) for x in range(w)
        if px[x, y][0] > 180 and px[x, y][1] < 100 and px[x, y][2] < 100]
left = [p for p in reds if p[0] < w / 2]
right = [p for p in reds if p[0] >= w / 2]

# Plate bounds from earlier
plate_left, plate_right = 17, 841
cx = (plate_left + plate_right) / 2
mm = 310.0 / (plate_right - plate_left)

# For each arrow, find tip (min y) and search ABOVE for a dark ring hole
out = ImageDraw.Draw(img)
for name, cluster, color in [("L", left, (0, 200, 0)), ("R", right, (0, 0, 255))]:
    tip = min(cluster, key=lambda p: p[1])
    print(f"\n{name} tip {tip}")
    # Search upward and slightly sideways for hole center (bright inside, dark ring)
    best = None
    for y in range(tip[1], max(0, tip[1] - 80), -1):
        for x in range(tip[0] - 40, tip[0] + 41):
            if not (0 <= x < w and 0 <= y < h):
                continue
            r, g, b = px[x, y]
            if (r + g + b) / 3 < 150:
                continue
            ring = 0
            for a in range(0, 360, 20):
                rad = math.radians(a)
                for rr in (2, 3, 4):
                    xx = int(x + rr * math.cos(rad))
                    yy = int(y + rr * math.sin(rad))
                    if 0 <= xx < w and 0 <= yy < h:
                        rr_, gg, bb = px[xx, yy]
                        if rr_ < 100 and gg < 100 and bb < 100:
                            ring += 1
            score = ring - 0.05 * abs(x - tip[0]) - 0.02 * abs(y - tip[1])
            if ring >= 8 and (best is None or score > best[0]):
                best = (score, x, y, ring)
    if best:
        _, x, y, ring = best
        mx = (x - cx) * mm
        print(f"  best hole px=({x},{y}) ring={ring} mm_x={mx:.2f}")
        out.ellipse([x - 5, y - 5, x + 5, y + 5], outline=color, width=2)
        out.line([tip, (x, y)], fill=color, width=2)

# Also mark all bottom-row-ish holes by scanning a band
# Estimate bottom hole row y from known geometry: plate height 94, holes at -34.5 from center
# Need plate cy in px. Use vertical dark outline of plate body only.
# Find longest horizontal dark runs
print("\nScanning bottom hole row candidates across plate...")
# Use y from 150 to 230 (around arrows)
row_hits = []
for y in range(140, 220):
    for x in range(plate_left + 20, plate_right - 20):
        r, g, b = px[x, y]
        if (r + g + b) / 3 < 140:
            continue
        ring = 0
        for a in range(0, 360, 30):
            rad = math.radians(a)
            xx = int(x + 3.5 * math.cos(rad))
            yy = int(y + 3.5 * math.sin(rad))
            if 0 <= xx < w and 0 <= yy < h:
                rr, gg, bb = px[xx, yy]
                if rr < 90 and gg < 90 and bb < 90:
                    ring += 1
        if ring >= 8:
            row_hits.append((x, y, ring))

row_hits.sort(key=lambda t: -t[2])
final = []
for c in row_hits:
    if all(math.hypot(c[0] - k[0], c[1] - k[1]) > 12 for k in final):
        final.append(c)
for x, y, ring in sorted(final, key=lambda t: t[0]):
    mx = (x - cx) * mm
    print(f"  hole px=({x},{y}) mm_x={mx:.1f} ring={ring}")
    out.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 128, 0), width=1)

img.save(r"G:\soft\S200工程\tools\beam_drawing_annotated.png")
print("\nsaved annotated")
