"""True orthographic TOP view of CUAV X25 for LCEDA footprint DXF.

Projects the real 3D mesh to XY (looking down -Z), unions triangles,
keeps mounting-feet silhouette, holes, and body/core outlines.
"""
from __future__ import annotations

import math
import zipfile
from pathlib import Path

import numpy as np
import trimesh
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union, polygonize

ROOT = Path(r"G:\soft\S200工程")
OUT = ROOT / "export" / "lceda_x25_footprint"
FC = ROOT / "FreeCAD"

# Mounting holes (assembly / model center). Will re-center DXF on hole-pattern center.
MOUNT_HOLES_ASM = np.array(
    [
        [-25.50, -26.75],
        [25.50, -26.75],
        [25.50, 26.75],
        [-25.50, 26.75],
    ],
    dtype=float,
)
HOLE_D = 3.2
PAD_D = 6.0


def load_ascii_or_binary_stl(path: Path) -> trimesh.Trimesh:
    m = trimesh.load(str(path), force="mesh")
    if not isinstance(m, trimesh.Trimesh):
        m = trimesh.util.concatenate(tuple(m.geometry.values()))
    return m


def project_mesh_polygon(mesh: trimesh.Trimesh, simplify_tol=0.15) -> Polygon | MultiPolygon:
    """Boolean-union of all triangle projections onto XY."""
    tris = mesh.triangles  # (n,3,3)
    polys = []
    for t in tris:
        xy = t[:, :2]
        # skip degenerate
        if abs(np.cross(xy[1] - xy[0], xy[2] - xy[0])) < 1e-8:
            continue
        try:
            p = Polygon(xy)
            if p.is_valid and p.area > 1e-6:
                polys.append(p)
            elif not p.is_valid:
                p = p.buffer(0)
                if p.area > 1e-6:
                    polys.append(p)
        except Exception:
            continue
    if not polys:
        raise RuntimeError("no projected polygons")
    print(f"  union {len(polys)} triangles...", flush=True)
    u = unary_union(polys)
    if simplify_tol > 0:
        u = u.simplify(simplify_tol, preserve_topology=True)
    return u


def poly_to_rings(geom) -> list[list[tuple[float, float]]]:
    """Exterior (+ holes) rings as point lists."""
    rings = []
    if geom.is_empty:
        return rings
    if isinstance(geom, Polygon):
        geoms = [geom]
    elif isinstance(geom, MultiPolygon):
        geoms = list(geom.geoms)
    else:
        geoms = [geom]
    for g in geoms:
        if g.is_empty or g.area < 1e-4:
            continue
        ext = list(g.exterior.coords)
        rings.append(ext)
        for hole in g.interiors:
            rings.append(list(hole.coords))
    return rings


def dxf_header(layers: list[tuple[str, int]]):
    s = """0
SECTION
2
HEADER
9
$ACADVER
1
AC1015
9
$INSUNITS
70
4
9
$MEASUREMENT
70
1
0
ENDSEC
0
SECTION
2
TABLES
0
TABLE
2
LTYPE
70
1
0
LTYPE
2
CONTINUOUS
70
0
3
Solid line
72
65
73
0
40
0.0
0
ENDTAB
0
TABLE
2
LAYER
70
"""
    s += f"{len(layers)+1}\n"
    s += """0
LAYER
2
0
70
0
62
7
6
CONTINUOUS
"""
    for name, color in layers:
        s += f"""0
LAYER
2
{name}
70
0
62
{color}
6
CONTINUOUS
"""
    s += """0
ENDTAB
0
ENDSEC
0
SECTION
2
ENTITIES
"""
    return s


def dxf_footer():
    return "0\nENDSEC\n0\nEOF\n"


def lwpoly(layer: str, pts: list[tuple[float, float]], closed=True) -> str:
    # drop duplicate closing point for LWPOLYLINE closed flag
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    body = f"""0
LWPOLYLINE
8
{layer}
90
{len(pts)}
70
{1 if closed else 0}
"""
    for x, y in pts:
        body += f"10\n{x:.5f}\n20\n{y:.5f}\n"
    return body


def circle(layer, x, y, r):
    return f"""0
CIRCLE
8
{layer}
10
{x:.5f}
20
{y:.5f}
30
0.0
40
{r:.5f}
"""


def line(layer, x1, y1, x2, y2):
    return f"""0
LINE
8
{layer}
10
{x1:.5f}
20
{y1:.5f}
30
0.0
11
{x2:.5f}
21
{y2:.5f}
31
0.0
"""


def text(layer, x, y, h, s):
    return f"""0
TEXT
8
{layer}
10
{x:.5f}
20
{y:.5f}
30
0.0
40
{h:.5f}
1
{s}
"""


def shift_geom(geom, dx, dy):
    from shapely.affinity import translate

    return translate(geom, xoff=dx, yoff=dy)


def rings_shifted(rings, dx, dy):
    return [[(x + dx, y + dy) for x, y in ring] for ring in rings]


def svg_from_rings(path: Path, layers: dict[str, list], holes, size_note: str):
    # compute bounds
    all_pts = []
    for rings in layers.values():
        for ring in rings:
            all_pts.extend(ring)
    for x, y in holes:
        all_pts.append((x, y))
    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    xmin, xmax = min(xs) - 5, max(xs) + 5
    ymin, ymax = min(ys) - 5, max(ys) + 8
    scale = 6.0
    W = (xmax - xmin) * scale
    H = (ymax - ymin) * scale

    def sx(x):
        return (x - xmin) * scale

    def sy(y):
        return (ymax - y) * scale

    colors = {
        "FEET": "#ff8c42",
        "BODY": "#8ad4a4",
        "CORE": "#6ec6ff",
        "PORTS": "#c9a0ff",
        "OUTLINE": "#ffffff",
        "HOLE": "#ff5c5c",
        "PAD": "#f0c36d",
    }
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.0f}" height="{H:.0f}">',
        '<rect width="100%" height="100%" fill="#12151a"/>',
        f'<text x="16" y="28" fill="#8ad4a4" font-size="18" font-family="Segoe UI,Arial">{size_note}</text>',
    ]
    for name, rings in layers.items():
        col = colors.get(name, "#aaa")
        for ring in rings:
            if len(ring) < 3:
                continue
            d = "M " + " L ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in ring) + " Z"
            fill = col if name == "FEET" else "none"
            opacity = "0.35" if name == "FEET" else "1"
            parts.append(
                f'<path d="{d}" fill="{fill}" fill-opacity="{opacity}" stroke="{col}" stroke-width="1.6"/>'
            )
    for x, y in holes:
        parts.append(
            f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="{HOLE_D/2*scale:.1f}" fill="none" stroke="#ff5c5c" stroke-width="1.5"/>'
        )
        parts.append(
            f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="{PAD_D/2*scale:.1f}" fill="none" stroke="#f0c36d" stroke-width="1" stroke-dasharray="3 2"/>'
        )
    # origin
    parts.append(
        f'<line x1="{sx(-2):.1f}" y1="{sy(0):.1f}" x2="{sx(2):.1f}" y2="{sy(0):.1f}" stroke="#f0c36d"/>'
    )
    parts.append(
        f'<line x1="{sx(0):.1f}" y1="{sy(-2):.1f}" x2="{sx(0):.1f}" y2="{sy(2):.1f}" stroke="#f0c36d"/>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    print("Loading parts...")
    mounts = load_ascii_or_binary_stl(FC / "part_x25_mounts.stl")
    body = load_ascii_or_binary_stl(FC / "part_x25_body.stl")
    core = load_ascii_or_binary_stl(FC / "part_x25_core.stl")
    ports = load_ascii_or_binary_stl(FC / "part_x25_ports.stl")
    detailed = load_ascii_or_binary_stl(FC / "part_x25_detailed.stl")

    print("Projecting mounts (feet)...")
    feet_poly = project_mesh_polygon(mounts, simplify_tol=0.12)
    print("Projecting body...")
    body_poly = project_mesh_polygon(body, simplify_tol=0.12)
    print("Projecting core...")
    core_poly = project_mesh_polygon(core, simplify_tol=0.12)
    print("Projecting ports...")
    ports_poly = project_mesh_polygon(ports, simplify_tol=0.15)
    print("Projecting full detailed (true outer outline)...")
    full_poly = project_mesh_polygon(detailed, simplify_tol=0.10)

    # Center on mounting-hole pattern center
    hole_c = MOUNT_HOLES_ASM.mean(axis=0)
    dx, dy = -hole_c[0], -hole_c[1]
    print(f"shift by {-dx:.3f},{-dy:.3f} so hole-pattern center -> origin")

    feet_poly = shift_geom(feet_poly, dx, dy)
    body_poly = shift_geom(body_poly, dx, dy)
    core_poly = shift_geom(core_poly, dx, dy)
    ports_poly = shift_geom(ports_poly, dx, dy)
    full_poly = shift_geom(full_poly, dx, dy)
    holes = MOUNT_HOLES_ASM + np.array([dx, dy])

    feet_rings = poly_to_rings(feet_poly)
    body_rings = poly_to_rings(body_poly)
    core_rings = poly_to_rings(core_poly)
    ports_rings = poly_to_rings(ports_poly)
    outline_rings = poly_to_rings(full_poly)

    print(f"outline rings={len(outline_rings)} feet={len(feet_rings)} body={len(body_rings)}")
    print(f"full bounds {full_poly.bounds}")
    print(f"feet bounds {feet_poly.bounds}")

    layers = [
        ("OUTLINE", 7),
        ("FEET", 30),
        ("BODY", 3),
        ("CORE", 4),
        ("PORTS", 6),
        ("MOUNT_HOLE", 1),
        ("PAD_HINT", 2),
        ("COURTYARD", 5),
        ("ORIGIN", 2),
        ("DOC", 7),
    ]

    ents = []
    # True outer silhouette first
    for ring in outline_rings:
        ents.append(lwpoly("OUTLINE", ring, True))
    # Mounting feet (关键 — user asked for this)
    for ring in feet_rings:
        ents.append(lwpoly("FEET", ring, True))
    for ring in body_rings:
        ents.append(lwpoly("BODY", ring, True))
    for ring in core_rings:
        ents.append(lwpoly("CORE", ring, True))
    for ring in ports_rings:
        ents.append(lwpoly("PORTS", ring, True))

    # courtyard = outline buffer 1mm
    court = full_poly.buffer(1.0).simplify(0.15)
    for ring in poly_to_rings(court):
        ents.append(lwpoly("COURTYARD", ring, True))

    for i, (x, y) in enumerate(holes, 1):
        ents.append(circle("MOUNT_HOLE", x, y, HOLE_D / 2))
        ents.append(circle("PAD_HINT", x, y, PAD_D / 2))
        ents.append(text("DOC", x + 2.0, y + 1.5, 1.2, str(i)))

    ents.append(line("ORIGIN", -2.5, 0, 2.5, 0))
    ents.append(line("ORIGIN", 0, -2.5, 0, 2.5))
    ents.append(circle("ORIGIN", 0, 0, 0.25))

    minx, miny, maxx, maxy = full_poly.bounds
    ents.append(text("DOC", minx, maxy + 3.5, 2.2, "CUAV X25 MEGA TRUE TOP VIEW"))
    ents.append(
        text(
            "DOC",
            minx,
            miny - 4,
            1.4,
            f"outline {maxx-minx:.2f}x{maxy-miny:.2f}mm  holes pitch 51.00x53.50  d={HOLE_D}",
        )
    )
    ents.append(text("DOC", minx, miny - 6.5, 1.2, "layers: OUTLINE FEET BODY CORE PORTS MOUNT_HOLE"))

    dxf = dxf_header(layers) + "".join(ents) + dxf_footer()
    dxf_path = OUT / "CUAV_X25_MEGA_TRUE_TOP.dxf"
    dxf_path.write_text(dxf, encoding="utf-8")
    print("wrote", dxf_path)

    # feet+outline only (cleaner for silk)
    ents2 = []
    for ring in outline_rings:
        ents2.append(lwpoly("OUTLINE", ring, True))
    for ring in feet_rings:
        ents2.append(lwpoly("FEET", ring, True))
    for i, (x, y) in enumerate(holes, 1):
        ents2.append(circle("MOUNT_HOLE", x, y, HOLE_D / 2))
        ents2.append(text("DOC", x + 2.0, y + 1.5, 1.2, str(i)))
    ents2.append(line("ORIGIN", -2.5, 0, 2.5, 0))
    ents2.append(line("ORIGIN", 0, -2.5, 0, 2.5))
    dxf2 = dxf_header(layers) + "".join(ents2) + dxf_footer()
    dxf2_path = OUT / "CUAV_X25_MEGA_TOP_outline_feet_holes.dxf"
    dxf2_path.write_text(dxf2, encoding="utf-8")

    # SVG preview
    svg_layers = {
        "FEET": feet_rings,
        "OUTLINE": outline_rings,
        "BODY": body_rings,
        "CORE": core_rings,
        "PORTS": ports_rings,
    }
    svg_from_rings(
        OUT / "CUAV_X25_MEGA_TRUE_TOP_preview.svg",
        svg_layers,
        holes,
        f"X25 TRUE TOP  {maxx-minx:.1f}x{maxy-miny:.1f}mm (with feet)",
    )

    # pad csv (origin = hole pattern center)
    csv = ["Designator,X(mm),Y(mm),Hole(mm),Pad(mm)"]
    for i, (x, y) in enumerate(holes, 1):
        csv.append(f"{i},{x:.3f},{y:.3f},{HOLE_D:.2f},{PAD_D:.2f}")
    (OUT / "CUAV_X25_MEGA_pads.csv").write_text("\n".join(csv) + "\n", encoding="utf-8")

    (OUT / "真实俯视图说明.md").write_text(
        f"""# CUAV X25 MEGA 真实俯视图（正投影）

本 DXF 由 3D 网格 **从上往下正投影** 后做二维并集得到，不是外接矩形。

## 文件

| 文件 | 内容 |
|------|------|
| `CUAV_X25_MEGA_TRUE_TOP.dxf` | 完整：总轮廓 + **安装脚 FEET** + 壳体 + 核心 + 接口 + 安装孔 |
| `CUAV_X25_MEGA_TOP_outline_feet_holes.dxf` | 精简：总轮廓 + 安装脚 + 孔（画丝印够用） |
| `CUAV_X25_MEGA_TRUE_TOP_preview.svg` | 预览图 |
| `CUAV_X25_MEGA_pads.csv` | 安装孔坐标 |

## 图层

- **OUTLINE** — 整机真实外轮廓（含脚、接口凸出）
- **FEET** — 底部安装脚俯视形状（四角支脚）
- **BODY / CORE / PORTS** — 分体投影参考
- **MOUNT_HOLE** — ⌀{HOLE_D} 安装孔
- **PAD_HINT** — ⌀{PAD_D} 焊盘参考
- **COURTYARD** — 外扩 1mm

## 坐标

- 原点 = **四安装孔中心**
- 孔距 51.00 × 53.50 mm
- 外轮廓约 **{maxx-minx:.2f} × {maxy-miny:.2f} mm**

## 立创EDA

文件 → 导入 → DXF → 单位 mm、比例 1  
丝印用 OUTLINE + FEET；安装孔按坐标放焊盘。
""",
        encoding="utf-8",
    )

    zip_path = OUT / "CUAV_X25_MEGA_TRUE_TOP_for_LCEDA.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name in [
            "CUAV_X25_MEGA_TRUE_TOP.dxf",
            "CUAV_X25_MEGA_TOP_outline_feet_holes.dxf",
            "CUAV_X25_MEGA_TRUE_TOP_preview.svg",
            "CUAV_X25_MEGA_pads.csv",
            "真实俯视图说明.md",
        ]:
            zf.write(OUT / name, name)
    print("wrote", zip_path)
    print("DONE", OUT)


if __name__ == "__main__":
    main()
