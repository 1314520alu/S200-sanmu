# s200-lceda MCP

S200 / 立创任务级 MCP：一次工具调用完成状态诊断、本地修复或云端库同步。

## 工具

### 本地工程

| 工具 | 作用 |
|------|------|
| `project_status` | X25 绑定/焊盘/能否转 PCB |
| `x25_pad_check` | 安装孔几何核对 |
| `x25_fix_pads` | 注入 4 焊盘 → `lceda_project/S200飞机_fixed/` |
| `x25_bind_footprint` | 原理图 Footprint 绑定 |
| `library_verify` | analysis + epru 一致性 |
| `hub_bridge_status` | 官方 Hub:8900 / Bridge 诊断 |

### 云端库（需已登录立创专业版）

| 工具 | 作用 |
|------|------|
| `cloud_auth_check` | 检查 web.db cookie |
| `cloud_fp_status` | 云端封装焊盘数 |
| `cloud_device_status` | Device 属性 |
| `cloud_upload_fp` | 上传 fixed 封装到个人库 |
| `cloud_bind_device` | Device 绑 Footprint + Convert to PCB |
| `x25_pipeline` | 本地修复 + 可选云端同步一键跑通 |

写策略：**直接写入**（无 confirm 开关）。

## 本地运行

```bat
"C:\Users\alu\AppData\Local\Programs\Python\Python311\python.exe" server.py
```

依赖：`mcp>=2.2`（本机 Python 3.11）。

## Cursor

`~/.cursor/mcp.json` 中 `s200-lceda` 条目。改代码后若工具列表未刷新，在 Settings → MCP 里 Restart 该服务。
