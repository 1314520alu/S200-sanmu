"""Export CUAV X25 MEGA 3D model for 立创EDA / EasyEDA Pro.

LCEDA 3D library accepts: step/stp/obj/wrl/zip (mm).
Origin: XY at model center, Z=0 at bottom (sits on PCB top).
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import numpy as np
import trimesh
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from detect_beam_holes import load_obj_group

ROOT = Path(r"G:\soft\S200工程")
OUT = ROOT / "export" / "lceda_x25"
ASM = ROOT / "viewer" / "models" / "assembly_hi.obj"
DETAILED = ROOT / "models" / "CUAV_X25_MEGA_detailed.stl"

# Colors matching viewer materials (RGB 0-1)
COLORS = {
    "x25_body": (0.14, 0.14, 0.16),
    "x25_core": (0.62, 0.68, 0.78),
    "x25_mounts": (0.09, 0.09, 0.10),
    "x25_ports": (0.96, 0.96, 0.94),
}


def write_mtl(path: Path):
    lines = ["# CUAV X25 MEGA materials for LCEDA"]
    for name, (r, g, b) in COLORS.items():
        lines += [
            f"newmtl {name}",
            f"Kd {r:.3f} {g:.3f} {b:.3f}",
            "Ka 0.05 0.05 0.05",
            "Ks 0.25 0.25 0.25",
            "Ns 40",
            "d 1.0",
            "illum 2",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")


def mesh_from_group(group: str) -> trimesh.Trimesh:
    verts = np.array(load_obj_group(ASM, group), dtype=np.float64)
    # Build faces from assembly by re-reading faces for this group
    # Simpler: convex? No — use point cloud ball pivoting is overkill.
    # Re-parse faces from OBJ for this group.
    all_v = []
    faces = []
    cur = None
    for line in ASM.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("g "):
            cur = line[2:].strip()
        elif line.startswith("v "):
            p = line.split()
            all_v.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("f ") and cur == group:
            ids = [int(t.split("/")[0]) for t in line.split()[1:]]
            if len(ids) >= 3:
                # triangulate fan
                for i in range(1, len(ids) - 1):
                    faces.append([ids[0] - 1, ids[i] - 1, ids[i + 1] - 1])
    used = sorted({i for f in faces for i in f})
    remap = {old: i for i, old in enumerate(used)}
    v = np.array([all_v[i] for i in used], dtype=np.float64)
    f = np.array([[remap[a], remap[b], remap[c]] for a, b, c in faces], dtype=np.int64)
    return trimesh.Trimesh(vertices=v, faces=f, process=True)


def write_colored_obj(meshes: dict[str, trimesh.Trimesh], path: Path, mtl_name: str):
    lines = [f"mtllib {mtl_name}", "# CUAV X25 MEGA — LCEDA 3D (mm)", "# Origin: center XY, Z=0 bottom"]
    v_off = 0
    for name, mesh in meshes.items():
        lines.append(f"g {name}")
        lines.append(f"usemtl {name}")
        for p in mesh.vertices:
            lines.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")
        for face in mesh.faces:
            a, b, c = (face + v_off + 1).tolist()
            lines.append(f"f {a} {b} {c}")
        v_off += len(mesh.vertices)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # --- 1) Detailed single mesh OBJ (best geometry) ---
    detailed = trimesh.load(str(DETAILED), force="mesh")
    # Already Z=0 bottom; ensure
    zmin = detailed.bounds[0][2]
    if abs(zmin) > 1e-6:
        detailed.apply_translation([0, 0, -zmin])
    # Center XY on bounding box center (already near 0)
    cx = 0.5 * (detailed.bounds[0][0] + detailed.bounds[1][0])
    cy = 0.5 * (detailed.bounds[0][1] + detailed.bounds[1][1])
    detailed.apply_translation([-cx, -cy, 0])

    obj_detail = OUT / "CUAV_X25_MEGA.obj"
    mtl_detail = OUT / "CUAV_X25_MEGA.mtl"
    # single material OBJ
    mtl_detail.write_text(
        "\n".join(
            [
                "newmtl x25",
                "Kd 0.18 0.18 0.20",
                "Ka 0.05 0.05 0.05",
                "Ks 0.3 0.3 0.3",
                "Ns 50",
                "d 1.0",
                "illum 2",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lines = ["mtllib CUAV_X25_MEGA.mtl", "g x25", "usemtl x25"]
    for p in detailed.vertices:
        lines.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")
    for face in detailed.faces:
        a, b, c = (face + 1).tolist()
        lines.append(f"f {a} {b} {c}")
    obj_detail.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", obj_detail, "verts", len(detailed.vertices), "size", detailed.extents)

    # Also STL companion (for other CAD; LCEDA prefers OBJ/STEP)
    stl_out = OUT / "CUAV_X25_MEGA.stl"
    detailed.export(str(stl_out))
    print("wrote", stl_out)

    # --- 2) Colored multi-part OBJ from assembly ---
    meshes = {}
    z0 = None
    for name in COLORS:
        m = mesh_from_group(name)
        meshes[name] = m
        z0 = m.bounds[0][2] if z0 is None else min(z0, m.bounds[0][2])
    # shift all so bottom at 0, center XY
    all_min = np.min([m.bounds[0] for m in meshes.values()], axis=0)
    all_max = np.max([m.bounds[1] for m in meshes.values()], axis=0)
    shift = np.array(
        [
            -0.5 * (all_min[0] + all_max[0]),
            -0.5 * (all_min[1] + all_max[1]),
            -all_min[2],
        ]
    )
    for m in meshes.values():
        m.apply_translation(shift)

    write_mtl(OUT / "CUAV_X25_MEGA_colored.mtl")
    write_colored_obj(meshes, OUT / "CUAV_X25_MEGA_colored.obj", "CUAV_X25_MEGA_colored.mtl")
    size = all_max - all_min
    print("colored size", size)

    # --- 3) ZIP for LCEDA batch 3D import ---
    zip_path = OUT / "CUAV_X25_MEGA_for_LCEDA.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in [
            "CUAV_X25_MEGA.obj",
            "CUAV_X25_MEGA.mtl",
            "CUAV_X25_MEGA_colored.obj",
            "CUAV_X25_MEGA_colored.mtl",
        ]:
            zf.write(OUT / f, f)
    print("wrote", zip_path)

    # --- 4) README ---
    readme = OUT / "立创EDA导入说明.md"
    readme.write_text(
        f"""# CUAV X25 MEGA — 立创EDA 3D 模型

## 文件

| 文件 | 说明 |
|------|------|
| `CUAV_X25_MEGA.obj` + `.mtl` | **推荐** 高精度单体模型（mm） |
| `CUAV_X25_MEGA_colored.obj` + `.mtl` | 分色模型（壳体/核心/安装件/接口） |
| `CUAV_X25_MEGA_for_LCEDA.zip` | 可直接在立创EDA「新建3D模型」里选 zip 导入 |
| `CUAV_X25_MEGA.stl` | 备用（立创EDA 3D库不直接支持 STL，请用 OBJ） |

## 坐标系

- 单位：**毫米 (mm)**
- **XY 原点**：模型包围盒中心（接近安装孔中心）
- **Z=0**：飞控底面（贴 PCB 顶面）
- 外形约：**{size[0]:.1f} × {size[1]:.1f} × {detailed.extents[2]:.1f} mm**

PCB 左下角为 (0,0) 时，四颗飞控螺丝中心约为：
`(69.50, 15.75)` `(120.50, 15.75)` `(69.50, 69.25)` `(120.50, 69.25)`

## 立创EDA 专业版导入步骤

1. **文件 → 新建 → 3D模型**
2. 模型单位选 **mm**
3. 选择本目录的 `CUAV_X25_MEGA.obj`，或整个 `CUAV_X25_MEGA_for_LCEDA.zip`
4. 勾选模型 → 确定
5. 在封装/器件里绑定该 3D 模型；用 **工具 → 3D模型管理器** 微调位置与角度

## 标准版

标准版 3D 支持较弱；建议用 **专业版** 导入 OBJ/STEP 并绑定封装。
""",
        encoding="utf-8",
    )
    print("wrote", readme)
    print("OUT DIR:", OUT)


if __name__ == "__main__":
    main()
