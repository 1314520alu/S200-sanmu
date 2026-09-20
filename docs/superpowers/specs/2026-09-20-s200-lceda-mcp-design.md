# S200 立创任务级 MCP 设计

日期：2026-09-20  
状态：已批准（写策略：直接写入）

## 目标

提供任务级 MCP 工具，一次调用完成一件工程事，绕开官方 jlceda 多轮透传与长审查报告。

## 决策

| 项 | 选择 |
|----|------|
| 架构 | 本地 Python MCP + 读写本地 `.epru` / Hub 状态；复用既有修复逻辑 |
| 写策略 | **直接写入**（危险操作由 Agent 口头确认，不强制 `confirm` 参数） |
| 与官方关系 | 并存；选型/放置仍用 `jlceda`；本 MCP 管工程修复与状态 |
| Bridge | 非必需；`hub_bridge_status` 仅诊断官方 Hub |

## 工具（v1）

1. `project_status` — X25 封装绑定、焊盘数、进 PCB 风险摘要  
2. `x25_pad_check` — 核对安装孔 ±25.5/±26.75、φ3.2  
3. `x25_fix_pads` — 注入 4 安装孔焊盘（直接写 fixed 包）  
4. `x25_bind_footprint` — 原理图 Footprint 绑定到目标 UUID（直接写）  
5. `library_verify` — 对照 analysis / 固定 UUID 做一致性检查  
6. `hub_bridge_status` — Hub:8900 / Bridge 客户端数 / 透传 flag  

## 工具（v1.1 云端）

7. `cloud_auth_check` — 本机 web.db 登录态  
8. `cloud_fp_status` / `cloud_device_status` — 云端库只读状态  
9. `cloud_upload_fp` / `cloud_bind_device` — 上传封装、绑 Device（直接写云端）  
10. `x25_pipeline` — 本地修复 + 可选云端同步一键  

## 成功标准

- 状态类工具单次 < 5s  
- 不依赖 EDA Bridge 可跑通本地工具 1–5  
- Agent 问「为何转不出 X25」→ 一次 `project_status` 给出结论  
- 云端工具在已登录立创专业版时可用  

