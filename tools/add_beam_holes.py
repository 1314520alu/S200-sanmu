"""Add two missing M3 holes on S200 front beam bottom row at (±30, -34.5)."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(r"G:\soft\S200工程")
HOLES = [(-30.0, -34.5), (30.0, -34.5)]  # mm, plate center origin
HOLE_D = 3.0
HOLE_R = HOLE_D / 2
# Existing front-face holes span z=0 .. -4
Z0, Z1 = 0.5, -4.5  # slight overcut for clean boolean


def load_ascii_stl(path: Path) -> trimesh.Trimesh:
    text = path.read_text(encoding="utf-8", errors="ignore")
    verts = []
    faces = []
    for block in re.finditer(
        r"facet normal\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+"
        r"outer loop\s+"
        r"vertex\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+"
        r"vertex\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+"
        r"vertex\s+([-\d.eE]+)\s+([-\d.eE]+)\s+([-\d.eE]+)\s+"
        r"endloop\s+endfacet",
        text,
        re.I | re.S,
    ):
        g = block.groups()
        i0 = len(verts)
        for k in range(3):
            verts.append([float(g[3 + 3 * k]), float(g[4 + 3 * k]), float(g[5 + 3 * k])])
        faces.append([i0, i0 + 1, i0 + 2])
    mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=True)
    print(f"loaded {path.name}: v={len(mesh.vertices)} f={len(mesh.faces)} watertight={mesh.is_watertight}")
    return mesh


def hole_cutters() -> trimesh.Trimesh:
    parts = []
    height = abs(Z0 - Z1)
    for x, y in HOLES:
        cyl = trimesh.creation.cylinder(radius=HOLE_R, height=height, sections=48)
        # cylinder default along Z centered at 0; move to mid of [Z0,Z1]
        zmid = (Z0 + Z1) / 2
        cyl.apply_translation([x, y, zmid])
        parts.append(cyl)
    return trimesh.util.concatenate(parts)


def punch(mesh: trimesh.Trimesh) -> trimesh.Trimesh:
    cutters = hole_cutters()
    print(f"cutters bounds {cutters.bounds}")
    # Prefer manifold engine
    try:
        result = mesh.difference(cutters, engine="manifold")
    except Exception as e:
        print("manifold failed:", e)
        result = mesh.difference(cutters)
    if isinstance(result, list):
        result = trimesh.util.concatenate(result)
    print(f"result v={len(result.vertices)} f={len(result.faces)} watertight={result.is_watertight}")
    return result


def write_ascii_stl(mesh: trimesh.Trimesh, path: Path, name: str = "OpenSCAD_Model"):
    v = mesh.vertices
    f = mesh.faces
    lines = [f"solid {name}"]
    for face in f:
        tri = v[face]
        n = np.cross(tri[1] - tri[0], tri[2] - tri[0])
        nn = np.linalg.norm(n)
        if nn > 1e-12:
            n = n / nn
        else:
            n = np.array([0.0, 0.0, 1.0])
        lines.append(f"  facet normal {n[0]:.6e} {n[1]:.6e} {n[2]:.6e}")
        lines.append("    outer loop")
        for p in tri:
            lines.append(f"      vertex {p[0]:.6e} {p[1]:.6e} {p[2]:.6e}")
        lines.append("    endloop")
        lines.append("  endfacet")
    lines.append(f"endsolid {name}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def write_obj(mesh: trimesh.Trimesh, path: Path, mtl_name: str, usemtl: str):
    v = mesh.vertices
    f = mesh.faces
    lines = [f"mtllib {mtl_name}", f"usemtl {usemtl}", f"g {usemtl}"]
    for p in v:
        lines.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")
    for face in f:
        a, b, c = face + 1
        lines.append(f"f {a} {b} {c}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def replace_obj_group(assembly_path: Path, group: str, new_mesh: trimesh.Trimesh, out_path: Path):
    """Replace one named group in a multi-group OBJ, keeping other groups intact."""
    text = assembly_path.read_text(encoding="utf-8", errors="ignore")
    # strip BOM
    if text.startswith("\ufeff"):
        text = text[1:]

    all_v: list[tuple[float, float, float]] = []
    # Parse into segments: preamble + groups
    lines = text.splitlines()
    # Collect all vertices first (global index space)
    for line in lines:
        if line.startswith("v "):
            p = line.split()
            all_v.append((float(p[1]), float(p[2]), float(p[3])))

    # Find group spans by line index
    groups = []  # (name, start_line, end_line)
    cur = None
    start = 0
    for i, line in enumerate(lines):
        if line.startswith("g "):
            if cur is not None:
                groups.append((cur, start, i))
            cur = line[2:].strip()
            start = i
    if cur is not None:
        groups.append((cur, start, len(lines)))

    print("groups:", [(n, b, e) for n, b, e in groups])

    # Faces for each group reference global vertex indices
    # Rebuild: vertices = [other verts in order of appearance except replaced group verts] 
    # Simpler strategy: rebuild whole file from groups using extracted meshes.

    def faces_of_group(gname: str):
        for n, b, e in groups:
            if n == gname:
                faces = []
                usemtl = None
                for line in lines[b:e]:
                    if line.startswith("usemtl "):
                        usemtl = line.split(None, 1)[1]
                    elif line.startswith("f "):
                        ids = [int(t.split("/")[0]) for t in line.split()[1:]]
                        faces.append(ids)
                return usemtl, faces
        raise KeyError(gname)

    # Build new vertex list: walk groups in order, emit verts used by each group
    # Map old index -> new index
    new_lines = []
    # keep header comments / mtllib
    for line in lines:
        if line.startswith("v ") or line.startswith("f ") or line.startswith("g ") or line.startswith("usemtl "):
            break
        new_lines.append(line)
    if not any(l.startswith("mtllib") for l in new_lines):
        # find mtllib
        for line in lines:
            if line.startswith("mtllib"):
                new_lines.insert(0, line)
                break

    new_v: list[tuple[float, float, float]] = []

    def emit_mesh(name: str, usemtl: str, mesh: trimesh.Trimesh):
        new_lines.append(f"g {name}")
        if usemtl:
            new_lines.append(f"usemtl {usemtl}")
        base = len(new_v)
        for p in mesh.vertices:
            new_v.append((float(p[0]), float(p[1]), float(p[2])))
            new_lines.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")
        # Actually OBJ usually lists all v first then faces — three.js OBJLoader accepts interleaved
        # but safer: collect all v then all groups faces. Let's do classic: all vertices then groups with faces only.
        return base

    # Classic OBJ: all vertices, then groups with faces
    # Rebuild meshes per group
    group_meshes = []
    for n, b, e in groups:
        usemtl, faces = faces_of_group(n)
        if n == group:
            group_meshes.append((n, usemtl or group, new_mesh))
        else:
            # extract submesh
            used = sorted({i for face in faces for i in face})
            remap = {old: i for i, old in enumerate(used)}
            verts = np.array([all_v[i - 1] for i in used])
            fidx = np.array([[remap[i] for i in face] for face in faces])
            m = trimesh.Trimesh(vertices=verts, faces=fidx, process=False)
            group_meshes.append((n, usemtl or n, m))

    # Write classic layout
    out = []
    # header
    for line in lines:
        if line.startswith("#") or line.startswith("mtllib"):
            out.append(line)
        elif line.startswith("v ") or line.startswith("g ") or line.startswith("usemtl") or line.startswith("f "):
            break
        elif line.strip() == "":
            out.append(line)

    # ensure mtllib
    if not any(l.startswith("mtllib") for l in out):
        for line in lines:
            if line.startswith("mtllib"):
                out.append(line)
                break

    # vertices concatenated
    v_offsets = []
    all_new_v = []
    for n, usemtl, mesh in group_meshes:
        v_offsets.append(len(all_new_v))
        for p in mesh.vertices:
            all_new_v.append(p)
    for p in all_new_v:
        out.append(f"v {p[0]:.5f} {p[1]:.5f} {p[2]:.5f}")

    for gi, (n, usemtl, mesh) in enumerate(group_meshes):
        out.append(f"g {n}")
        out.append(f"usemtl {usemtl}")
        off = v_offsets[gi]
        for face in mesh.faces:
            a, b, c = (face + off + 1).tolist()
            out.append(f"f {a} {b} {c}")

    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote assembly {out_path} groups={len(group_meshes)} verts={len(all_new_v)}")


def verify_holes(mesh: trimesh.Trimesh):
    # Count vertices on hole cylinder walls (r≈1.5 around centers)
    v = mesh.vertices
    for x, y in HOLES:
        d = np.hypot(v[:, 0] - x, v[:, 1] - y)
        ring = int(np.sum((d >= 1.3) & (d <= 1.7) & (v[:, 2] > -5) & (v[:, 2] < 1)))
        inner = int(np.sum((d < 1.0) & (np.abs(v[:, 2]) < 0.2)))
        print(f"hole ({x},{y}): wall_verts={ring} front_inner={inner}")


def main():
    src = ROOT / "FreeCAD" / "part_beam.stl"
    mesh = load_ascii_stl(src)
    print("bounds", mesh.bounds)
    punched = punch(mesh)
    verify_holes(punched)

    # outputs
    write_ascii_stl(punched, ROOT / "FreeCAD" / "part_beam.stl")
    write_obj(punched, ROOT / "FreeCAD" / "beam.obj", "beam.mtl", "beam")

    asm_in = ROOT / "viewer" / "models" / "assembly_hi.obj"
    asm_out = asm_in
    replace_obj_group(asm_in, "beam_hollow", punched, asm_out)

    # also sync models colored assembly if present
    colored = ROOT / "models" / "S200_beam_PCB_X25_assembly_colored.obj"
    if colored.exists():
        replace_obj_group(colored, "beam_hollow", punched, colored)

    # save hole note
    note = ROOT / "tools" / "beam_added_holes.txt"
    note.write_text(
        "Added M3 (d=3) holes on front beam from drawing measurement:\n"
        "  (±30.0, -34.5) mm, plate-center origin, bottom row only\n"
        "  Calibrated from 310×94 plate + 110/69 dims; measured ≈±30.15\n",
        encoding="utf-8",
    )
    print("done")


if __name__ == "__main__":
    main()
