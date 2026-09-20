#!/usr/bin/env python3
"""S200 / 立创任务级 MCP — 一次调用办一件工程事（直接写入）。"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# MCP stdio: keep stdout clean for JSON-RPC only
logging.basicConfig(stream=sys.stderr, level=logging.ERROR)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcp.server.mcpserver import MCPServer

from lib import cloud
from lib import epru
from lib import hub as hub_lib
from lib import constants as C

server = MCPServer(
    name="s200-lceda",
    version="1.1.1",
    instructions=(
        "S200 飞机立创工程任务 MCP v1.1。"
        "优先用本工具做 X25 封装/焊盘/绑定/云端库同步/状态诊断；"
        "器件选型与放置仍用官方 jlceda。"
        "写操作会直接落盘或直接调用立创云端 API。"
        "一键完整修复用 x25_pipeline。"
        "云端工具：cloud_auth_check / cloud_fp_status / cloud_device_status / "
        "cloud_upload_fp / cloud_bind_device / x25_pipeline。"
    ),
    log_level="ERROR",
)


def _j(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@server.tool(
    description="S200/X25 工程状态：封装绑定、焊盘数、能否转 PCB。",
    structured_output=False,
)
def project_status(epru_path: str | None = None) -> str:
    """epru_path 可选；默认优先 fixed，否则 backup。"""
    return _j(epru.project_status(epru_path))


@server.tool(
    description="核对 X25 安装孔焊盘位置/孔径（±25.5/±26.75 mm，φ3.2）。",
    structured_output=False,
)
def x25_pad_check(epru_path: str | None = None) -> str:
    path = epru.resolve_epru(epru_path)
    if not path.exists():
        return _j({"ok": False, "error": f"not found: {path}"})
    raw = path.read_text(encoding="utf-8", errors="replace")
    reports = [epru.check_footprint_pads(raw, u).__dict__ for u in C.FP_UUIDS]
    return _j({"ok": True, "epru": str(path), "footprints": reports})


@server.tool(
    description="向 X25 封装注入 4 个安装孔焊盘，直接写入 S200飞机_fixed。",
    structured_output=False,
)
def x25_fix_pads(source_epru: str | None = None) -> str:
    """默认从 backup 读取；结果写到 fixed。"""
    return _j(epru.fix_pads(source_epru))


@server.tool(
    description="原理图 X25 Footprint 绑定到封装 UUID，直接写入 fixed。",
    structured_output=False,
)
def x25_bind_footprint(
    source_epru: str | None = None,
    footprint_uuid: str = C.PRIMARY_FP_UUID,
) -> str:
    return _j(epru.fix_bind(source_epru, footprint_uuid))


@server.tool(
    description="对照 analysis 缓存与本地 epru 做 X25 库/工程一致性检查。",
    structured_output=False,
)
def library_verify() -> str:
    return _j(epru.library_verify())


@server.tool(
    description="诊断官方 jlceda Hub/Bridge（端口 8900、客户端数、透传开关）。",
    structured_output=False,
)
def hub_bridge_status() -> str:
    return _j(hub_lib.hub_bridge_status())


@server.tool(
    description="检查本机立创登录 cookie（web.db）是否可用。",
    structured_output=False,
)
def cloud_auth_check() -> str:
    return _j(cloud.auth_check())


@server.tool(
    description="拉取云端 X25 封装库状态（焊盘数/ticket）。",
    structured_output=False,
)
def cloud_fp_status(fp_uuid: str = C.FP_LIB) -> str:
    return _j(cloud.fp_status(fp_uuid))


@server.tool(
    description="拉取云端 X25 Device 属性（Footprint / Convert to PCB）。",
    structured_output=False,
)
def cloud_device_status(dev_uuid: str = C.DEV_LIB) -> str:
    return _j(cloud.device_status(dev_uuid))


@server.tool(
    description="把本地 fixed 封装 dataStr 上传到个人封装库（直接写云端）。",
    structured_output=False,
)
def cloud_upload_fp(
    epru_path: str | None = None,
    fp_lib_uuid: str = C.FP_LIB,
) -> str:
    return _j(cloud.upload_fp(epru_path, fp_lib_uuid))


@server.tool(
    description="云端 Device 绑定 Footprint 并开启 Convert to PCB（直接写）。",
    structured_output=False,
)
def cloud_bind_device(
    dev_uuid: str = C.DEV_LIB,
    fp_uuid: str = C.FP_LIB,
) -> str:
    return _j(cloud.bind_device(dev_uuid, fp_uuid))


@server.tool(
    description="一键：本地修焊盘+绑定，可选同步云端封装库与 Device（直接写）。",
    structured_output=False,
)
def x25_pipeline(include_cloud: bool = True) -> str:
    return _j(cloud.x25_pipeline(include_cloud))


if __name__ == "__main__":
    server.run(transport="stdio")
