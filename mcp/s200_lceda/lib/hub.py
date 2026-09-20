"""Official jlceda Hub / Bridge diagnostics (no EDA control)."""
from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from . import constants as C


def tcp_open(host: str, port: int, timeout: float = 1.0) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def hub_bridge_status() -> dict[str, Any]:
    status: dict[str, Any] = {
        "expected_bridge_url": C.HUB_WS_URL,
        "hub_port_open": tcp_open(C.HUB_HOST, C.HUB_PORT),
        "port_8765_open": tcp_open("127.0.0.1", 8765),
        "note_8765": "若 8765 被 GCS com-bridge 占用，EDA Bridge 必须改连 8900",
        "raw_api_tools_enabled": None,
        "runtime": None,
    }
    if C.HUB_RAW_API_FLAG.exists():
        status["raw_api_tools_enabled"] = C.HUB_RAW_API_FLAG.read_text(encoding="utf-8").strip() == "1"
    if C.HUB_STATUS.exists():
        try:
            status["runtime"] = json.loads(C.HUB_STATUS.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            status["runtime_error"] = str(e)
    else:
        status["runtime"] = {"missing": str(C.HUB_STATUS)}

    rt = status.get("runtime") or {}
    count = rt.get("bridgeClientCount") if isinstance(rt, dict) else None
    if count == 0:
        status["advice"] = (
            f"Hub 在线但 Bridge 未连接。请在立创 EDA → MCP Bridge 设置地址为 {C.HUB_WS_URL}"
        )
    elif isinstance(count, int) and count > 0:
        status["advice"] = "Bridge 已连接，可用官方 jlceda 透传工具"
    elif not status["hub_port_open"]:
        status["advice"] = "Hub 未监听 8900，请在 Cursor 中启用 jlceda MCP"
    return status
