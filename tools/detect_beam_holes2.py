"""Detect ø3 hole centers on OpenSCAD ASCII STL / OBJ more reliably."""
import math
import re
from pathlib import Path


def load_ascii_stl(path: Path):
    text = path.read_text(encoding="utf-8", errors="ignore")
    verts = []
    for m in re.finditer(r"vertex\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)", text):
        verts.append((float(m.group(1)), float(m.group(2)), float(m.group(3))))
    return verts


def load_obj(path: Path):
    verts = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("v "):
            p = line.split()
            verts.append((float(p[1]), float(p[2]), float(p[3])))
    return verts


def find_holes(verts, label):
    xs, ys, zs = zip(*verts)
    print(f"\n=== {label} ===")
    print("size", round(max(xs) - min(xs), 2), round(max(ys) - min(ys), 2), round(max(zs) - min(zs), 2))
    print("bbox Y", round(min(ys), 2), round(max(ys), 2), "Z", round(min(zs), 2), round(max(zs), 2))
    cx = (min(xs) + max(xs)) / 2
    cy = (min(ys) + max(ys)) / 2
    uniq = list({(round(x - cx, 2), round(y - cy, 2), round(z, 2)) for x, y, z in verts})

    # Only look at front face sheet: z near 0 (assembly beam z -60..0, face at 0)
    # For FreeCAD beam may differ
    z_face = max(z for _, _, z in uniq)
    face = [(x, y) for x, y, z in uniq if abs(z - z_face) < 1.5]
    print("face z", z_face, "face pts", len(face))

    # Also include cylinder wall points near y=±34.5
    band = [(x, y, z) for x, y, z in uniq if abs(abs(y) - 34.5) < 1.2]
    print("y±34.5 band pts", len(band))

    centers = []
    for y0 in (34.5, -34.5):
        for xi in range(-155, 156):
            x0 = float(xi)
            # count points on circle r=1.5 in XY
            cnt = 0
            for x, y, z in band:
                if abs(y - y0) > 1.2:
                    continue
                d = math.hypot(x - x0, y - y0)
                if 1.3 <= d <= 1.7:
                    cnt += 1
            if cnt >= 4:
                centers.append((x0, y0, cnt))

    centers.sort(key=lambda t: -t[2])
    final = []
    for c in centers:
        if all(math.hypot(c[0] - k[0], c[1] - k[1]) > 4 for k in final):
            final.append(c)
    print("holes at y=±34.5:")
    for h in sorted(final, key=lambda t: (t[1], t[0])):
        print(" ", h)

    # Check specifically for ±55 and near-center
    for x_t in (0, 20, 25, 30, 35, 40, 45, 50, 55):
        for y0 in (34.5, -34.5):
            cnt = sum(
                1
                for x, y, z in band
                if abs(y - y0) <= 1.2 and 1.3 <= math.hypot(x - x_t, y - y0) <= 1.7
            )
            cntn = sum(
                1
                for x, y, z in band
                if abs(y - y0) <= 1.2 and 1.3 <= math.hypot(x + x_t, y - y0) <= 1.7
            )
            if cnt >= 3 or cntn >= 3:
                print(f"  probe ±{x_t},{y0}: +x cnt={cnt} -x cnt={cntn}")


def main():
    find_holes(load_ascii_stl(Path(r"G:\soft\S200工程\FreeCAD\part_beam.stl")), "part_beam.stl")
    find_holes(load_obj(Path(r"G:\soft\S200工程\FreeCAD\beam.obj")), "beam.obj")
    # assembly beam group only
    from detect_beam_holes import load_obj_group

    find_holes(
        load_obj_group(Path(r"G:\soft\S200工程\viewer\models\assembly_hi.obj"), "beam_hollow"),
        "assembly beam_hollow",
    )


if __name__ == "__main__":
    main()
