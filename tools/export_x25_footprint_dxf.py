"""Export X25 top-view footprint DXF + pad CSV for 立创EDA."""
from __future__ import annotations

import math
import zipfile
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(r"G:\soft\S200工程")
OUT = ROOT / "export" / "lceda_x25_footprint"
STL = ROOT / "export" / "lceda_x25" / "CUAV_X25_MEGA.stl"

# Mounting hole centers (mm), model center origin — measured from assembly
# Pitch 51.0 × 53.5
MOUNT_HOLES = [
    ("1", -25.50, -26.75),  # BL
    ("2", 25.50, -26.75),   # BR
    ("3", 25.50, 26.75),    # TR
    ("4", -25.50, 26.75),   # TL  (counterclockwise from 1 for footprint convention)
]
# M3 clearance hole for FC mounting screws
HOLE_D = 3.2
PAD_D = 6.0  # copper pad diameter suggestion

# Layers for LCEDA-friendly DXF (names are hints when mapping import layers)
LAYER_OUTLINE = "SILK_OUTLINE"      # 丝印外框 / 文档
LAYER_BODY = "BODY"                 # 本体投影
LAYER_HOLE = "MOUNT_HOLE"           # 安装孔圆 → 导入边框层可变过孔/参考
LAYER_PAD = "PAD_HINT"              # 焊盘外径参考圆
LAYER_COURTYARD = "COURTYARD"       # 封装院子
LAYER_ORIGIN = "ORIGIN"
LAYER_TEXT = "DOC"


def dxf_header():
    # Minimal R12/LT2 DXF, units mm (INSUNITS=4)
    return """0
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
8
0
LAYER
2
0
70
0
62
7
6
CONTINUOUS
0
LAYER
2
SILK_OUTLINE
70
0
62
3
6
CONTINUOUS
0
LAYER
2
BODY
70
0
62
8
6
CONTINUOUS
0
LAYER
2
MOUNT_HOLE
70
0
62
1
6
CONTINUOUS
0
LAYER
2
PAD_HINT
70
0
62
4
6
CONTINUOUS
0
LAYER
2
COURTYARD
70
0
62
5
6
CONTINUOUS
0
LAYER
2
ORIGIN
70
0
62
2
6
CONTINUOUS
0
LAYER
2
DOC
70
0
62
7
6
CONTINUOUS
0
ENDTAB
0
ENDSEC
0
SECTION
2
ENTITIES
"""


def dxf_footer():
    return """0
ENDSEC
0
EOF
"""


def circle(layer: str, x: float, y: float, r: float) -> str:
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


def line(layer: str, x1, y1, x2, y2) -> str:
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


def polyline_closed(layer: str, pts: list[tuple[float, float]]) -> str:
    # LWPOLYLINE
    n = len(pts)
    body = f"""0
LWPOLYLINE
8
{layer}
90
{n}
70
1
"""
    for x, y in pts:
        body += f"""10
{x:.5f}
20
{y:.5f}
"""
    return body


def text(layer: str, x, y, h, s: str) -> str:
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


def rounded_rect(cx, cy, w, h, r, n_arc=8):
    """Closed polyline for rounded rectangle centered at cx,cy."""
    hw, hh = w / 2, h / 2
    r = min(r, hw, hh)
    pts = []
    # go CCW from bottom-right-ish
    corners = [
        (cx + hw - r, cy - hh + r, 0),      # BR arc center, start angle 270
        (cx + hw - r, cy + hh - r, 90),     # TR
        (cx - hw + r, cy + hh - r, 180),    # TL
        (cx - hw + r, cy - hh + r, 270),    # BL
    ]
    # simpler: straight rect if r~0
    if r < 0.2:
        return [
            (cx - hw, cy - hh),
            (cx + hw, cy - hh),
            (cx + hw, cy + hh),
            (cx - hw, cy + hh),
        ]
    for i, (ox, oy, a0) in enumerate(corners):
        for k in range(n_arc + 1):
            ang = math.radians(a0 + 90 * k / n_arc)
            # corner centers and outward arcs
            # BR: center (hw-r, -hh+r), angles -90 to 0
            pass
    # Build properly
    arcs = [
        ((cx + hw - r, cy - hh + r), -90, 0),
        ((cx + hw - r, cy + hh - r), 0, 90),
        ((cx - hw + r, cy + hh - r), 90, 180),
        ((cx - hw + r, cy - hh + r), 180, 270),
    ]
    pts = []
    for (ox, oy), a0, a1 in arcs:
        for k in range(n_arc + 1):
            ang = math.radians(a0 + (a1 - a0) * k / n_arc)
            pts.append((ox + r * math.cos(ang), oy + r * math.sin(ang)))
    return pts


def alpha_outline_2d(vertices_xy: np.ndarray, pitch=0.5):
    """Grid-based outer contour (axis-aligned silhouette)."""
    xs, ys = vertices_xy[:, 0], vertices_xy[:, 1]
    xmin, xmax = xs.min(), xs.max()
    ymin, ymax = ys.min(), ys.max()
    # Use bounding rounded rect estimate from extremes + corner sampling
    return xmin, ymin, xmax, ymax


def extract_silhouette(mesh: trimesh.Trimesh):
    """Project all verts to XY — full body top view extent."""
    v = mesh.vertices
    return v[:, 0], v[:, 1]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mesh = trimesh.load(str(STL), force="mesh")
    # Ensure centered Z0
    b = mesh.bounds
    print("mesh bounds", b)

    xs, ys = extract_silhouette(mesh)
    xmin, xmax = float(xs.min()), float(xs.max())
    ymin, ymax = float(ys.min()), float(ys.max())
    w, h = xmax - xmin, ymax - ymin
    print(f"top-view outline {w:.3f} x {h:.3f} mm")

    # Body outline: use mounts layer approx = full extent rectangle with slight corner radius
    # Detect corner radius from bottom slab (z < 8)
    bottom = mesh.vertices[mesh.vertices[:, 2] < 8.0]
    # try R≈2 for plastic housing aesthetic; measure
    cr = 2.0

    # Core top square (z near top)
    zmax = b[1][2]
    top = mesh.vertices[np.abs(mesh.vertices[:, 2] - zmax) < 1.0]
    if len(top) > 10:
        core = (float(top[:, 0].min()), float(top[:, 1].min()), float(top[:, 0].max()), float(top[:, 1].max()))
    else:
        core = (-18.5, -18.5, 18.5, 18.5)
    print("core top", core)

    body_pts = rounded_rect(0, 0, w, h, cr, n_arc=6)
    # courtyard +1mm each side
    court_pts = rounded_rect(0, 0, w + 2.0, h + 2.0, cr + 0.5, n_arc=6)
    core_w = core[2] - core[0]
    core_h = core[3] - core[1]
    core_cx = 0.5 * (core[0] + core[2])
    core_cy = 0.5 * (core[1] + core[3])
    core_pts = rounded_rect(core_cx, core_cy, core_w, core_h, 1.0, n_arc=4)

    ents = []
    ents.append(polyline_closed(LAYER_BODY, body_pts))
    ents.append(polyline_closed(LAYER_COURTYARD, court_pts))
    ents.append(polyline_closed(LAYER_BODY, core_pts))  # inner core outline

    # origin cross
    ents.append(line(LAYER_ORIGIN, -2, 0, 2, 0))
    ents.append(line(LAYER_ORIGIN, 0, -2, 0, 2))
    ents.append(circle(LAYER_ORIGIN, 0, 0, 0.3))

    for name, x, y in MOUNT_HOLES:
        ents.append(circle(LAYER_HOLE, x, y, HOLE_D / 2))
        ents.append(circle(LAYER_PAD, x, y, PAD_D / 2))
        ents.append(text(LAYER_TEXT, x + 2.2, y + 1.2, 1.2, name))

    ents.append(text(LAYER_TEXT, -w / 2, h / 2 + 3, 2.0, "CUAV X25 MEGA TOP"))
    ents.append(text(LAYER_TEXT, -w / 2, -h / 2 - 5, 1.5, f"{w:.2f}x{h:.2f}mm  hole d={HOLE_D}"))
    ents.append(text(LAYER_TEXT, -w / 2, -h / 2 - 7.5, 1.2, "pitch 51.00 x 53.50  origin=center"))

    dxf = dxf_header() + "".join(ents) + dxf_footer()
    dxf_path = OUT / "CUAV_X25_MEGA_footprint_top.dxf"
    dxf_path.write_text(dxf, encoding="utf-8")
    print("wrote", dxf_path)

    # Also a holes-only DXF (for 边框层导入 → 圆变过孔参考)
    ents2 = [polyline_closed("SILK_OUTLINE", body_pts), polyline_closed("COURTYARD", court_pts)]
    ents2 += [line(LAYER_ORIGIN, -2, 0, 2, 0), line(LAYER_ORIGIN, 0, -2, 0, 2)]
    for name, x, y in MOUNT_HOLES:
        ents2.append(circle("MOUNT_HOLE", x, y, HOLE_D / 2))
    dxf2 = dxf_header() + "".join(ents2) + dxf_footer()
    dxf2_path = OUT / "CUAV_X25_MEGA_outline_holes.dxf"
    dxf2_path.write_text(dxf2, encoding="utf-8")

    # Pad coordinate CSV for 立创EDA「导入焊盘坐标文件」
    # Template-like: designator, x, y, pad shape hints
    csv_path = OUT / "CUAV_X25_MEGA_pads.csv"
    # EasyEDA Pro pad import — provide clear columns; user maps to template
    rows = [
        "Designator,X(mm),Y(mm),Pad Type,Shape,Width(mm),Height(mm),Hole(mm),Layer,Rotation",
    ]
    for name, x, y in MOUNT_HOLES:
        rows.append(
            f"{name},{x:.3f},{y:.3f},THROUGH,CIRCLE,{PAD_D:.2f},{PAD_D:.2f},{HOLE_D:.2f},MUL,{0}"
        )
    csv_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("wrote", csv_path)

    # Dimensions doc
    doc = OUT / "封装尺寸说明.md"
    doc.write_text(
        f"""# CUAV X25 MEGA 封装俯视图（立创EDA）

## 坐标系

- 单位：mm
- **原点：封装中心**（推荐，便于旋转放置）
- +X 右，+Y 上
- 俯视图：从上往下看

## 外形

| 项目 | 尺寸 |
|------|------|
| 本体投影 | **{w:.2f} × {h:.2f} mm** |
| 建议院子 | {(w+2):.2f} × {(h+2):.2f} mm（外扩 1mm） |
| 顶部核心区 | 约 {core_w:.2f} × {core_h:.2f} mm |

## 安装孔（4×M3，建议孔径 ⌀{HOLE_D}）

| 编号 | X | Y | 说明 |
|------|------|------|------|
| 1 | {-25.50:.2f} | {-26.75:.2f} | 左下 |
| 2 | {25.50:.2f} | {-26.75:.2f} | 右下 |
| 3 | {25.50:.2f} | {26.75:.2f} | 右上 |
| 4 | {-25.50:.2f} | {26.75:.2f} | 左上 |

孔距：**51.00 × 53.50 mm**

建议焊盘外径：**⌀{PAD_D} mm**（非金属化安装孔也可做成 ⌀{HOLE_D} 挖槽）

## 导入立创EDA

### 方法 A：DXF 作参考轮廓

1. 新建封装库
2. **文件 → 导入 → DXF**，选 `CUAV_X25_MEGA_footprint_top.dxf`
3. 单位 **mm**，比例 **1**
4. 将外框映射到 **顶层丝印** / 文档层
5. 按坐标放置 4 个多层焊盘（或导入 `CUAV_X25_MEGA_pads.csv` 后按模板调整）
6. 删除多余参考线，设封装原点为中心

### 方法 B：焊盘坐标

1. 封装编辑器 → **文件 → 导入 → 焊盘坐标文件**
2. 先下载官方模板，把 `CUAV_X25_MEGA_pads.csv` 中的坐标填入
3. 再导入 DXF 画丝印外框

### 3D 绑定

同目录上级的 `export/lceda_x25/CUAV_X25_MEGA.obj` 可绑到此封装。
""",
        encoding="utf-8",
    )

    # Simple SVG preview
    scale = 4.0
    svg_w = (w + 20) * scale
    svg_h = (h + 24) * scale

    def sx(x):
        return (x - xmin + 10) * scale

    def sy(y):
        return (ymax + 12 - y) * scale  # flip Y for SVG

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w:.0f}" height="{svg_h:.0f}">',
        f'<rect width="100%" height="100%" fill="#1a1e24"/>',
        f'<g fill="none" stroke="#8ad4a4" stroke-width="1.5">',
    ]
    # body
    path = "M " + " L ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in body_pts) + " Z"
    svg.append(f'<path d="{path}" stroke="#aab0bb"/>')
    path2 = "M " + " L ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in court_pts) + " Z"
    svg.append(f'<path d="{path2}" stroke="#5b8def" stroke-dasharray="4 3"/>')
    for name, x, y in MOUNT_HOLES:
        svg.append(
            f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="{HOLE_D/2*scale:.1f}" stroke="#ff6b6b"/>'
        )
        svg.append(
            f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="{PAD_D/2*scale:.1f}" stroke="#f0c36d" stroke-dasharray="2 2"/>'
        )
        svg.append(
            f'<text x="{sx(x)+8:.1f}" y="{sy(y)-6:.1f}" fill="#eee" font-size="12">{name}</text>'
        )
    svg.append(
        f'<line x1="{sx(-2):.1f}" y1="{sy(0):.1f}" x2="{sx(2):.1f}" y2="{sy(0):.1f}" stroke="#f0c36d"/>'
    )
    svg.append(
        f'<line x1="{sx(0):.1f}" y1="{sy(-2):.1f}" x2="{sx(0):.1f}" y2="{sy(2):.1f}" stroke="#f0c36d"/>'
    )
    svg.append(
        f'<text x="20" y="24" fill="#8ad4a4" font-size="16">CUAV X25 MEGA TOP  {w:.1f}x{h:.1f}mm</text>'
    )
    svg.append("</g></svg>")
    (OUT / "CUAV_X25_MEGA_top_preview.svg").write_text("\n".join(svg), encoding="utf-8")

    zip_path = OUT / "CUAV_X25_MEGA_footprint_for_LCEDA.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in OUT.iterdir():
            if f.suffix.lower() in {".dxf", ".csv", ".md", ".svg"}:
                zf.write(f, f.name)
    print("wrote", zip_path)
    print("OUT", OUT)


if __name__ == "__main__":
    main()
