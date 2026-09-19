# S200 三目 / 前梁 · PCB · X25

S200 前梁装配、3D 预览与立创 EDA 导出资料。

## 目录

| 路径 | 说明 |
|------|------|
| `viewer/` | 本地 Three.js 组合体预览（`start_viewer.bat`） |
| `FreeCAD/` | 分件 STL/OBJ + 导入宏 |
| `models/` | 装配体 OBJ/STL/3MF/FCStd |
| `export/lceda_x25/` | X25 飞控 3D 模型（OBJ，立创可导入） |
| `export/lceda_x25_footprint/` | X25 **真实俯视** DXF 封装（含安装脚） |
| `tools/` | 网格处理 / 导出脚本 |

## 快速预览

```bat
cd viewer
start_viewer.bat
```

浏览器打开：http://127.0.0.1:18765/index.html

## 立创 EDA

- **3D**：`export/lceda_x25/CUAV_X25_MEGA.obj`（或 zip）
- **封装俯视**：`export/lceda_x25_footprint/CUAV_X25_MEGA_TRUE_TOP.dxf`  
  图层含 `OUTLINE` / `FEET` / `MOUNT_HOLE` 等，单位 mm

## PCB 关键尺寸（板左下角为原点）

- 板框：190 × 85 mm  
- A1–A4：`(40,77)` `(150,77)` `(40,8)` `(150,8)`  
- X25 安装孔：孔距 51 × 53.5，中心约 `(±25.5, ±26.75)`（相对板心）
