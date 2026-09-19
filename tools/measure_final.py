"""Robust hole finder: plate 310 scale + dashed centerline + circle detection."""
import math
from pathlib import Path
from collections import defaultdict

from PIL import Image, ImageDraw

img = Image.open(Path(r"G:/soft/S200工程/tools/beam_drawing2.png")).convert("RGB")
w, h = img.size
px = img.load()


def dark(x, y, thr=100):
    if not (0 <= x < w and 0 <= y < h):
        return False
    r, g, b = px[x, y]
    return r < thr and g < thr and b < thr


# Plate outer box: longest near-continuous top/bottom horizontals of the plate body
# Use y where a long dark run exists AND there is a matching parallel edge ~94mm away later

def long_runs_at_y(y, min_len=500):
    runs = []
    run = 0
    x0 = 0
    for x in range(w):
        if dark(x, y, 90):
            if run == 0:
                x0 = x
            run += 1
        else:
            if run >= min_len:
                runs.append((run, x0, x - 1))
            run = 0
    if run >= min_len:
        runs.append((run, x0, w - 1))
    return runs


# Find plate top: first y with long run in upper area that's the plate (not outer frame)
plate_edges = []
for y in range(60, 120):
    runs = long_runs_at_y(y, 600)
    for run in runs:
        plate_edges.append((y, run))
for y in range(250, 320):
    runs = long_runs_at_y(y, 600)
    for run in runs:
        plate_edges.append((y, run))

print("plate edge candidates:")
for e in plate_edges[:20]:
    print(" ", e)

# Pick top = min y with run~690-800, bot = max
tops = [e for e in plate_edges if e[0] < 150]
bots = [e for e in plate_edges if e[0] > 200]
# Prefer run length matching
if tops and bots:
    # use most common x0/x1
    top = min(tops, key=lambda e: e[0])
    bot = max(bots, key=lambda e: e[0])
    # refine: among tops with similar x span to bot
    def span(e):
        return e[1][2] - e[1][1]

    bot_span = span(bot)
    tops_f = [t for t in tops if abs(span(t) - bot_span) < 30]
    bots_f = [b for b in bots if abs(span(b) - bot_span) < 30]
    top = min(tops_f or tops, key=lambda e: e[0])
    bot = max(bots_f or bots, key=lambda e: e[0])
    y_top, (_, x_left, x_right) = top[0], top[1]
    y_bot = bot[0]
    # use intersection of x ranges
    x_left = max(top[1][1], bot[1][1])
    x_right = min(top[1][2], bot[1][2])
    print(f"PLATE y[{y_top},{y_bot}] x[{x_left},{x_right}]")
    mm = 310.0 / (x_right - x_left)
    mmy = 94.0 / (y_bot - y_top)
    cx = (x_left + x_right) / 2
    cy = (y_top + y_bot) / 2
    print(f"mm/px x={mm:.5f} y={mmy:.5f} (aspect check y/x={mmy/mm:.3f})")
    print(f"center ({cx:.1f},{cy:.1f})")

# Find dashed vertical centerline: intermittent dark near cx
# Score each x by dashed pattern (alternating dark/light vertically)
def dash_score(x):
    darks = 0
    gaps = 0
    prev = False
    for y in range(y_top + 5, y_bot - 5):
        d = dark(x, y, 110)
        if d:
            darks += 1
            if not prev:
                gaps += 1  # new segment
        prev = d
    # centerline: moderate darks, multiple segments
    if darks < 15:
        return 0
    return gaps * 10 + min(darks, 80)


best_cx = max(range(int(cx - 40), int(cx + 41)), key=dash_score)
print(f"dashed centerline x={best_cx} score={dash_score(best_cx)} (box cx={cx})")
cx = best_cx

# Circle detection via radial darkness variance — look for small circles r~3-6px
def circle_score(x, y):
    # interior should be lighter than ring
    ring_d = 0
    ring_n = 0
    inn_d = 0
    inn_n = 0
    for a in range(0, 360, 15):
        rad = math.radians(a)
        for rr, bucket in ((2, "in"), (3.5, "ring"), (4.5, "ring")):
            xx = int(round(x + rr * math.cos(rad)))
            yy = int(round(y + rr * math.sin(rad)))
            if dark(xx, yy, 110):
                if bucket == "ring":
                    ring_d += 1
                else:
                    inn_d += 1
            if bucket == "ring":
                ring_n += 1
            else:
                inn_n += 1
    # also crosshair arms
    arm = sum(
        1
        for d in range(2, 7)
        for xx, yy in ((x + d, y), (x - d, y), (x, y + d), (x, y - d))
        if dark(xx, yy, 110)
    )
    return ring_d - inn_d * 0.5 + arm * 0.3, ring_d, inn_d, arm


# Search only near top/bottom hole rows
y_top_h = cy - 34.5 / mmy
y_bot_h = cy + 34.5 / mmy
print(f"hole rows y: top={y_top_h:.1f} bot={y_bot_h:.1f}")


def find_holes(y_row, tol=10):
    hits = []
    for y in range(int(y_row - tol), int(y_row + tol) + 1):
        for x in range(x_left + 10, x_right - 10):
            sc, ring, inn, arm = circle_score(x, y)
            if ring >= 10 and arm >= 4 and sc > 12:
                hits.append((sc, x, y, ring, arm))
    hits.sort(key=lambda t: -t[0])
    kept = []
    for h0 in hits:
        if all(math.hypot(h0[1] - k[1], h0[2] - k[2]) > 12 for k in kept):
            kept.append(h0)
    out = []
    for sc, x, y, ring, arm in sorted(kept, key=lambda t: t[1]):
        mx = (x - cx) * mm
        my = (cy - y) * mmy
        out.append((round(mx, 2), round(my, 2), x, y, round(sc, 1), ring, arm))
    return out


top = find_holes(y_top_h)
bot = find_holes(y_bot_h)
print(f"\nTOP ({len(top)}):")
for t in top:
    print(" ", t)
print(f"\nBOT ({len(bot)}):")
for t in bot:
    print(" ", t)

print("\nBOT |x|<60:")
for t in bot:
    if abs(t[0]) < 60:
        print(" ", t)

# Expected model holes for comparison
print("\nDistance of each bot hole to nearest model X in {55,102,132}:")
model = [55, 102, 132]
for t in bot:
    d = min(abs(abs(t[0]) - m) for m in model)
    tag = "KNOWN" if d < 6 else "NEW?"
    print(f"  x={t[0]:7.2f} dist_to_known={d:.1f} {tag}")

out = img.copy()
dr = ImageDraw.Draw(out)
dr.line([(cx, y_top), (cx, y_bot)], fill=(255, 140, 0), width=1)
for t in top:
    x, y = t[2], t[3]
    dr.ellipse([x - 7, y - 7, x + 7, y + 7], outline=(0, 180, 0), width=2)
for t in bot:
    x, y = t[2], t[3]
    colr = (255, 0, 0) if abs(t[0]) < 50 else (0, 100, 255)
    dr.ellipse([x - 7, y - 7, x + 7, y + 7], outline=colr, width=2)
# mark expected ±55
for sx in (-55, 55):
    x = cx + sx / mm
    y = y_bot_h
    dr.rectangle([x - 3, y - 3, x + 3, y + 3], outline=(255, 0, 255))
out.save(Path(r"G:/soft/S200工程/tools/beam_final_meas.png"))
print("saved beam_final_meas.png")
