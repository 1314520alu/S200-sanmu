"""Fast PCB outline + hole extraction from assembly mesh."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import sys

sys.path.insert(0, r"G:\soft\S200工程\tools")
from detect_beam_holes import load_obj_group

ROOT = Path(r"G:\soft\S200工程")


def load_pcb():
    verts = load_obj_group(ROOT / "viewer" / "models" / "assembly_hi.obj", "pcb")
    v = np.asarray(verts, dtype=np.float64)
    cx = 0.5 * (v[:, 0].min() + v[:, 0].max())
    cy = 0.5 * (v[:, 1].min() + v[:, 1].max())
    v[:, 0] -= cx
    v[:, 1] -= cy
    return v, cx, cy


def detect_holes(xy: np.ndarray, r_list, grid=0.25, min_ring=8):
    """Grid-search hole centers; use spatial binning for speed."""
    # bucket points
    bins = {}
    scale = 1.0 / grid
    for x, y in xy:
        key = (int(math.floor(x * scale)), int(math.floor(y * scale)))
        bins.setdefault(key, []).append((x, y))

    xs = xy[:, 0]
    ys = xy[:, 1]
    x0, x1 = xs.min() + 1, xs.max() - 1
    y0, y1 = ys.min() + 1, ys.max() - 1

    found = []
    for r_nom in r_list:
        # only search near points that could be on a ring: use all points as seed offsets
        # denser: scan grid but only where local point density exists
        xi = x0
        while xi <= x1:
            yi = y0
            while yi <= y1:
                # gather nearby points from bins
                i0 = int(math.floor((xi - r_nom - 0.5) * scale))
                i1 = int(math.floor((xi + r_nom + 0.5) * scale))
                j0 = int(math.floor((yi - r_nom - 0.5) * scale))
                j1 = int(math.floor((yi + r_nom + 0.5) * scale))
                pts = []
                for ii in range(i0, i1 + 1):
                    for jj in range(j0, j1 + 1):
                        pts.extend(bins.get((ii, jj), ()))
                if len(pts) < min_ring:
                    yi += grid
                    continue
                arr = np.asarray(pts)
                d = np.hypot(arr[:, 0] - xi, arr[:, 1] - yi)
                ring = int(np.sum((d >= r_nom - 0.12) & (d <= r_nom + 0.12)))
                inner = int(np.sum(d < max(0.05, r_nom - 0.25)))
                if ring >= min_ring and inner <= 2:
                    found.append((round(xi, 2), round(yi, 2), round(r_nom, 3), ring))
                yi += grid
            xi += grid

    found.sort(key=lambda t: -t[3])
    kept = []
    for h in found:
        if all(math.hypot(h[0] - k[0], h[1] - k[1]) > max(1.2, h[2]) for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda t: (t[1], t[0]))


def outline_from_top(xy: np.ndarray, step=0.5):
    """Axis-aligned outer rectangle + detect corner radius if present."""
    xmin, ymin = xy.min(0)
    xmax, ymax = xy.max(0)
    # Estimate corner radius: for points near a corner, find max inset of quarter-circle
    # Sample left-top corner region
    def corner_r(sx, sy):
        # sx/sy = sign toward corner from center
        cx_c = xmax if sx > 0 else xmin
        cy_c = ymax if sy > 0 else ymin
        # points within 15mm of corner
        near = xy[(np.abs(xy[:, 0] - cx_c) < 15) & (np.abs(xy[:, 1] - cy_c) < 15)]
        if len(near) < 10:
            return 0.0
        # for a rounded rect, the corner arc center is inset by r
        # find r that best fits arc: minimize variance of dist to (cx_c - sx*r, cy_c - sy*r)
        best = (0.0, 1e9)
        for r in np.arange(0.5, 12.0, 0.25):
            ox = cx_c - sx * r
            oy = cy_c - sy * r
            # only arc quadrant points
            q = near[((near[:, 0] - ox) * sx >= -0.2) & ((near[:, 1] - oy) * sy >= -0.2)]
            if len(q) < 5:
                continue
            d = np.hypot(q[:, 0] - ox, q[:, 1] - oy)
            # points on arc should have d≈r; also include edge points
            err = np.mean(np.abs(d - r))
            if err < best[1]:
                best = (float(r), float(err))
        return best[0] if best[1] < 0.8 else 0.0

    rs = [
        corner_r(-1, -1),
        corner_r(1, -1),
        corner_r(-1, 1),
        corner_r(1, 1),
    ]
    r = float(np.median(rs))
    print("corner radii samples", rs, "->", r)
    return xmin, ymin, xmax, ymax, r


def main():
    v, cx, cy = load_pcb()
    print("size", v.max(0) - v.min(0), "center_abs", cx, cy)
    zmax = v[:, 2].max()
    top = v[np.abs(v[:, 2] - zmax) < 0.2]
    xy = np.unique(np.round(top[:, :2], 3), axis=0)
    print("top unique xy", len(xy), "zmax", zmax)

    xmin, ymin, xmax, ymax, cr = outline_from_top(xy)
    print(f"outline ({xmin:.3f},{ymin:.3f})-({xmax:.3f},{ymax:.3f}) size={xmax-xmin:.3f}x{ymax-ymin:.3f} R={cr:.2f}")

    holes = detect_holes(
        xy,
        r_list=[0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5, 1.6],
        grid=0.5,
        min_ring=6,
    )
    print(f"holes {len(holes)}")
    for h in holes:
        kind = "M3?" if 1.4 <= h[2] <= 1.7 else ("via?" if h[2] <= 0.6 else "hole")
        print(f"  ({h[0]:7.2f},{h[1]:7.2f}) r={h[2]:.2f} ring={h[3]} {kind}")

    np.savez(
        ROOT / "tools" / "pcb_extract.npz",
        xy=xy,
        holes=np.array(holes) if holes else np.zeros((0, 4)),
        outline=np.array([xmin, ymin, xmax, ymax, cr]),
        center_abs=np.array([cx, cy]),
        size=np.array([xmax - xmin, ymax - ymin]),
    )
    print("saved")


if __name__ == "__main__":
    main()
