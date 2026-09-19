# S200 前梁 + PCB + X25 — FreeCAD 包

## 怎么打开

### 方法 A（推荐）：宏一键导入分色零件
1. 解压本文件夹到任意路径
2. FreeCAD → **Macro → Macros…** → 选 `Import_S200_beam_PCB_X25.FCMacro` → Execute
3. 会自动导入梁 / PCB / 紧固件 / X25 分色零件并摆好位置

### 方法 B：直接打开网格
FreeCAD → **File → Open**，任选：
- `part_beam.stl` / `part_pcb.stl` / `part_hardware.stl`
- `beam.obj` / `pcb.obj`（同内容，带简单材质色）
- `part_x25_*.stl` 或整块 `part_x25_detailed.stl`

## 说明
- 这是 **网格（Mesh）**，不是 STEP 实体。本机无 FreeCAD/CadQuery，无法从 OpenSCAD 直接出 STEP。
- 单位 **mm**。原点：梁正面中心；+X 右，+Y 上，+Z 出梁面。
- PCB 厚 3 mm、R4；梁空心壁 4 mm、倒角 2 mm；X25 用已有详细分色 STL。
- 若只要单色整机，也可打开上级目录的 `assembly.stl`。

## 文件列表
| 文件 | 内容 |
|------|------|
| part_beam.stl | 空心铝梁 |
| part_pcb.stl | 详细 PCB |
| part_hardware.stl | 通心柱 + M3/M6 钉头 |
| part_x25_body/core/mounts/ports.stl | X25 分色 |
| part_x25_detailed.stl | X25 单色详细 |
| beam.obj / pcb.obj | OBJ（FreeCAD 同样可开） |
| Import_S200_beam_PCB_X25.FCMacro | 一键导入 |
