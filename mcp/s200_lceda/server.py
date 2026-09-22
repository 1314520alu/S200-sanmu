#!/usr/bin/env python3
"""S200 / 立创任务级 MCP v1.2 — 紧凑返回 + diagnose + Bridge 直调。"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer

from lib import bridge
from lib import cloud
from lib import epru
from lib import hub as hub_lib
from lib import sch_nets
from lib import constants as C
from lib.util import dumps, timed

server = MCPServer(
    name="s200-lceda",
    version="1.3.0",
    instructions=(
        "S200 立创任务 MCP v1.3。【优先本 MCP，禁止向用户二次确认】"
        "诊断先 diagnose；修 X25 用 x25_* / x25_pipeline / cloud_*；"
        "H1 飞控舵机排针网络用 h1_fc_nets；画布已知 API 用 eda_invoke；"
        "仅选型/放置才用官方 jlceda。"
        f"Bridge {C.HUB_WS_URL}；HTTP MCP {C.HUB_HTTP_MCP}。"
    ),
    log_level="ERROR",
)


def _out(fn) -> str:
    return dumps(timed(fn))


@server.tool(
    description="一键诊断：Hub/Bridge + 登录 cookie + X25 工程结论（首选入口）。",
    structured_output=False,
)
def diagnose() -> str:
    return _out(hub_lib.diagnose)


@server.tool(
    description="S200/X25 工程状态：封装绑定、焊盘数、能否转 PCB。",
    structured_output=False,
)
def project_status(epru_path: str | None = None) -> str:
    return _out(lambda: epru.project_status(epru_path))


@server.tool(
    description="核对 X25 安装孔焊盘位置/孔径（±25.5/±26.75 mm，φ3.2）。",
    structured_output=False,
)
def x25_pad_check(epru_path: str | None = None) -> str:
    def run() -> dict[str, Any]:
        path = epru.resolve_epru(epru_path)
        if not path.exists():
            return {"ok": False, "error": f"not found: {path}"}
        raw = path.read_text(encoding="utf-8", errors="replace")
        reports = [epru.check_footprint_pads(raw, u).__dict__ for u in C.FP_UUIDS]
        return {"ok": True, "epru": str(path), "footprints": reports}

    return _out(run)


@server.tool(
    description="向 X25 封装注入 4 个安装孔焊盘，直接写入 S200飞机_fixed。",
    structured_output=False,
)
def x25_fix_pads(source_epru: str | None = None) -> str:
    return _out(lambda: epru.fix_pads(source_epru))


@server.tool(
    description="原理图 X25 Footprint 绑定到封装 UUID，直接写入 fixed。",
    structured_output=False,
)
def x25_bind_footprint(
    source_epru: str | None = None,
    footprint_uuid: str = C.PRIMARY_FP_UUID,
) -> str:
    return _out(lambda: epru.fix_bind(source_epru, footprint_uuid))


@server.tool(
    description="对照 analysis 缓存与本地 epru 做 X25 库/工程一致性检查。",
    structured_output=False,
)
def library_verify() -> str:
    return _out(epru.library_verify)


@server.tool(
    description="诊断官方 jlceda Hub/Bridge（8765）与 HTTP MCP（7900）。",
    structured_output=False,
)
def hub_bridge_status() -> str:
    return _out(hub_lib.hub_bridge_status)


@server.tool(
    description="精简当前立创工程/页上下文（经 Hub HTTP，需 Bridge 已连）。",
    structured_output=False,
)
def eda_snapshot(timeout_ms: int = 15000) -> str:
    return _out(lambda: bridge.eda_snapshot(timeout_ms))


@server.tool(
    description="直接调用 eda.* API（经 Hub HTTP）。args 为 JSON 数组字符串，默认 []。跳过官方 index/search。",
    structured_output=False,
)
def eda_invoke(
    api_full_name: str,
    args_json: str = "[]",
    timeout_ms: int = 15000,
) -> str:
    def run() -> dict[str, Any]:
        try:
            args = json.loads(args_json) if args_json else []
        except json.JSONDecodeError as e:
            return {"ok": False, "error": f"args_json 非法: {e}"}
        if not isinstance(args, list):
            return {"ok": False, "error": "args_json 须为 JSON 数组"}
        return bridge.eda_invoke(api_full_name, args, timeout_ms)

    return _out(run)


@server.tool(
    description="一键：H1 排针按飞控映射画网络（1/4/7→M1-M16，2/5/8→SERVO_VCC，3/6/9→FC_GND）。经 Hub HTTP，勿用官方透传。",
    structured_output=False,
)
def h1_fc_nets(h1_id: str = sch_nets.H1_ID) -> str:
    return _out(lambda: sch_nets.h1_fc_nets(h1_id))


@server.tool(
    description="检查本机立创登录 cookie（web.db）是否可用。",
    structured_output=False,
)
def cloud_auth_check() -> str:
    return _out(cloud.auth_check)


@server.tool(
    description="拉取云端 X25 封装库状态（焊盘数/ticket）。",
    structured_output=False,
)
def cloud_fp_status(fp_uuid: str = C.FP_LIB) -> str:
    return _out(lambda: cloud.fp_status(fp_uuid))


@server.tool(
    description="拉取云端 X25 Device 属性（Footprint / Convert to PCB）。",
    structured_output=False,
)
def cloud_device_status(dev_uuid: str = C.DEV_LIB) -> str:
    return _out(lambda: cloud.device_status(dev_uuid))


@server.tool(
    description="把本地 fixed 封装 dataStr 上传到个人封装库（直接写云端）。",
    structured_output=False,
)
def cloud_upload_fp(
    epru_path: str | None = None,
    fp_lib_uuid: str = C.FP_LIB,
) -> str:
    return _out(lambda: cloud.upload_fp(epru_path, fp_lib_uuid))


@server.tool(
    description="云端 Device 绑定 Footprint 并开启 Convert to PCB（直接写）。",
    structured_output=False,
)
def cloud_bind_device(
    dev_uuid: str = C.DEV_LIB,
    fp_uuid: str = C.FP_LIB,
) -> str:
    return _out(lambda: cloud.bind_device(dev_uuid, fp_uuid))


@server.tool(
    description="一键：本地修焊盘+绑定，可选同步云端封装库与 Device（直接写）。",
    structured_output=False,
)
def x25_pipeline(include_cloud: bool = True) -> str:
    return _out(lambda: cloud.x25_pipeline(include_cloud))


if __name__ == "__main__":
    server.run(transport="stdio")
