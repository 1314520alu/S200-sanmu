"""Official jlceda Hub / Bridge diagnostics + combined diagnose."""
from __future__ import annotations

import json
import socket
from typing import Any

from . import constants as C
from . import cloud
from . import epru


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
        "http_mcp_open": tcp_open(C.HUB_HOST, C.HUB_HTTP_PORT),
        "note": "Hub:9050 Bridge WS；HTTP MCP:7900（eda_snapshot/eda_invoke 走此口）",
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
            f"Hub 在线但 Bridge 未连接。立创 MCP Bridge 地址设为 {C.HUB_WS_URL}"
        )
    elif isinstance(count, int) and count > 0:
        status["advice"] = "Bridge 已连接；画布操作用 eda_snapshot / eda_invoke"
    elif not status["hub_port_open"]:
        status["advice"] = "Hub 未监听 9050，请在 Cursor 中启用/重载 jlceda MCP"
    return status


def diagnose() -> dict[str, Any]:
    """One-shot: Hub + auth + local X25 project verdict."""
    hub = hub_bridge_status()
    rt = hub.get("runtime") if isinstance(hub.get("runtime"), dict) else {}
    auth = cloud.auth_check()
    proj = epru.project_status()
    bridge_ok = isinstance(rt.get("bridgeClientCount"), int) and rt["bridgeClientCount"] > 0
    local_ok = bool(proj.get("can_convert_x25_to_pcb"))
    return {
        "ok": bool(hub.get("hub_port_open")) and bool(auth.get("ok")),
        "verdict": (
            "ready"
            if local_ok and bridge_ok
            else ("local_ok_bridge_down" if local_ok else "blocked")
        ),
        "hub": {
            "port_open": hub.get("hub_port_open"),
            "http_mcp_open": hub.get("http_mcp_open"),
            "bridge_clients": rt.get("bridgeClientCount"),
            "url": hub.get("expected_bridge_url"),
            "advice": hub.get("advice"),
        },
        "auth": {
            "ok": auth.get("ok"),
            "cookie_count": auth.get("cookie_count"),
            "has_csrf": auth.get("has_csrf"),
        },
        "project": {
            "epru": proj.get("epru"),
            "can_convert_x25_to_pcb": proj.get("can_convert_x25_to_pcb"),
            "summary": proj.get("summary"),
            "blockers": proj.get("blockers"),
            "binding": proj.get("binding"),
        },
        "next": (
            "用 x25_pipeline 修本地/云端"
            if not local_ok
            else (
                "本地 OK；Bridge 未连则只做离线/云端，画布请先连 Bridge"
                if not bridge_ok
                else "可用 eda_snapshot / eda_invoke 或继续云端工具"
            )
        ),
    }
