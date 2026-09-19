"""Locate hardware (screw) XY centers — they mark existing beam holes."""
import math
from pathlib import Path
import sys

sys.path.insert(0, r"G:\soft\S200工程\tools")
from detect_beam_holes import load_obj_group


def centers_of_group(path, group):
    verts = load_obj_group(path, group)
    # cluster connected components roughly by grid
    xs, ys, zs = zip(*verts)
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    pts = [(x - cx, y - cy, z) for x, y, z in verts]
    # hardware are small screws — find local clusters
    # bin by 2mm
    bins = {}
    for x, y, z in pts:
        key = (round(x / 2) * 2, round(y / 2) * 2)
        bins.setdefault(key, []).append((x, y, z))
    clusters = []
    for (bx, by), vp in bins.items():
        if len(vp) < 8:
            continue
        ax = sum(p[0] for p in vp) / len(vp)
        ay = sum(p[1] for p in vp) / len(vp)
        az = sum(p[2] for p in vp) / len(vp)
        clusters.append((round(ax, 1), round(ay, 1), round(az, 1), len(vp)))
    # NMS
    clusters.sort(key=lambda t: -t[3])
    kept = []
    for c in clusters:
        if all(math.hypot(c[0] - k[0], c[1] - k[1]) > 5 for k in kept):
            kept.append(c)
    return sorted(kept, key=lambda t: (t[1], t[0]))


path = Path(r"G:\soft\S200工程\viewer\models\assembly_hi.obj")
print("hardware clusters:")
for c in centers_of_group(path, "hardware"):
    print(c)
print("x25_mounts clusters:")
for c in centers_of_group(path, "x25_mounts"):
    print(c)
