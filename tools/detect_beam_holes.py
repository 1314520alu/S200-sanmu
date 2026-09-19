import math
import re
from collections import defaultdict
from pathlib import Path


def load_obj_xy(path: Path, until_group=None):
    verts = []
    group = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("g "):
            group = line[2:].strip()
            if until_group and verts and group != until_group and until_group in (group or ""):
                pass
        if until_group and group and group != until_group and verts:
            # stop after leaving target group if we already collected
            if group != until_group and any(True for _ in [0]):
                # continue scanning only target
                pass
        if line.startswith("v "):
            if until_group and group and group != until_group:
                continue
            parts = line.split()
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
    return verts


def load_obj_group(path: Path, group_name: str):
    verts = []
    in_group = False
    idx_map = {}  # obj is global indices; easier read all then filter faces
    # Simpler: parse all v, then faces belonging to group
    all_v = []
    faces = []
    cur = None
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("g "):
            cur = line[2:].strip()
        elif line.startswith("v "):
            p = line.split()
            all_v.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f ") and cur == group_name:
            ids = []
            for tok in line.split()[1:]:
                ids.append(int(tok.split("/")[0]))
            faces.append(ids)
    used = set()
    for f in faces:
        for i in f:
            used.add(i)
    return [all_v[i - 1] for i in sorted(used)]


def detect_holes(coords, y_abs_list, r_lo=1.2, r_hi=1.9, min_cnt=6):
    kept = []
    for y_abs in y_abs_list:
        row_pts = [(x, y) for x, y, z in coords if abs(abs(y) - y_abs) < 3.0]
        for y_sign in (1, -1):
            y0 = y_sign * y_abs
            for xi in range(-320, 321):
                x0 = xi * 0.5
                cnt = 0
                for x, y in row_pts:
                    if abs(y - y0) > 2.5:
                        continue
                    d = math.hypot(x - x0, y - y0)
                    if r_lo <= d <= r_hi:
                        cnt += 1
                if cnt >= min_cnt:
                    kept.append((round(x0, 2), round(y0, 2), cnt))
    kept.sort(key=lambda t: -t[2])
    final = []
    for c in kept:
        if all(math.hypot(c[0] - k[0], c[1] - k[1]) > 3 for k in final):
            final.append(c)
    return sorted(final, key=lambda t: (round(t[1], 1), t[0]))


def main():
    path = Path(r"G:\soft\S200工程\viewer\models\assembly_hi.obj")
    verts = load_obj_group(path, "beam_hollow")
    print("beam verts", len(verts))
    xs, ys, zs = zip(*verts)
    print("bbox", min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))
    print("size", max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    coords = [(x - cx, y - cy, z) for x, y, z in verts]

    y_hist = defaultdict(int)
    for _, y, _ in coords:
        y_hist[round(abs(y), 1)] += 1
    peaks = sorted(y_hist.items(), key=lambda t: -t[1])[:20]
    print("abs(y) peaks:", peaks)

    y_abs_list = sorted({y for y, c in peaks if 20 <= y <= 50})[:6] or [34.5]
    print("using y_abs", y_abs_list)
    holes = detect_holes(coords, y_abs_list)
    print("small holes:")
    for h in holes:
        print(h)

    # large
    large = []
    for xi in range(-320, 321):
        x0 = xi * 0.5
        cnt = sum(1 for x, y, z in coords if abs(y) < 3 and 18 <= math.hypot(x - x0, y) <= 30)
        if cnt >= 20:
            large.append((x0, 0.0, cnt))
    large.sort(key=lambda t: -t[2])
    kept_l = []
    for c in large:
        if all(abs(c[0] - k[0]) > 15 for k in kept_l):
            kept_l.append((round(c[0], 2), c[1], c[2]))
    print("large:", kept_l)


if __name__ == "__main__":
    main()
