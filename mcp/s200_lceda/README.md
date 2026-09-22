# s200-lceda MCP v1.3

S200 / 立创任务级 MCP：一次工具调用完成一件工程事。写操作直接落盘/写云端。

## 优先用法

1. `diagnose` — Hub + 登录 + X25 结论（首选）  
2. 本地/云端修复 — `x25_*` / `cloud_*` / `x25_pipeline`  
3. H1 飞控排针网络 — `h1_fc_nets`（一次画完 M1–M16 / SERVO_VCC / FC_GND）  
4. 画布其它 — `eda_snapshot` / `eda_invoke`（已知 `eda.*`，跳过官方多轮透传）  
5. 选型放置 — 仍用官方 `jlceda`

## 工具

| 工具 | 作用 |
|------|------|
| `diagnose` | Hub/Bridge + cookie + 工程结论 |
| `project_status` / `x25_pad_check` / `x25_fix_pads` / `x25_bind_footprint` | 本地 epru |
| `library_verify` | analysis + epru 一致性 |
| `hub_bridge_status` | Hub:8765 / HTTP:7900 |
| `eda_snapshot` | 精简画布上下文（需 Bridge） |
| `eda_invoke` | 直调 `eda.*`（`args_json` 为 JSON 数组） |
| `h1_fc_nets` | H1→M1-M16 / SERVO_VCC / FC_GND 一键画网 |
| `cloud_*` / `x25_pipeline` | 云端库 + 一键流水线 |

返回均为**紧凑 JSON**，带 `ms`。

Bridge：`ws://127.0.0.1:8765/bridge/ws`  
HTTP MCP：`http://127.0.0.1:7900/mcp`

## Cursor

`~/.cursor/mcp.json` → `s200-lceda`。改代码后 Settings → MCP → Restart。
