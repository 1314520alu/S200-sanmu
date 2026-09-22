"""Call official jlceda Hub over HTTP MCP (port 7900) — skips multi-step agent passthrough."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from . import constants as C
from . import hub as hub_lib


def _http_mcp(method: str, params: dict[str, Any], *, timeout: float = 20) -> dict[str, Any]:
    body = json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        C.HUB_HTTP_MCP,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return {"ok": False, "http": e.code, "error": json.loads(raw)}
        except Exception:
            return {"ok": False, "http": e.code, "error": raw[:500]}
    except Exception as e:
        return {"ok": False, "error": str(e), "hint": "Hub HTTP MCP 不可达，检查 jlceda 是否在跑"}

    if "error" in payload:
        return {"ok": False, "rpc_error": payload["error"]}
    result = payload.get("result")
    if not isinstance(result, dict):
        return {"ok": False, "error": "unexpected MCP result", "raw": result}
    content = result.get("content") or []
    if content and isinstance(content[0], dict) and content[0].get("type") == "text":
        text = content[0].get("text") or ""
        try:
            return {"ok": True, "data": json.loads(text)}
        except json.JSONDecodeError:
            return {"ok": True, "data": text}
    if "structuredContent" in result:
        return {"ok": True, "data": result["structuredContent"]}
    return {"ok": True, "data": result}


def _slim_context(data: dict[str, Any]) -> dict[str, Any]:
    proj = data.get("currentProjectInfo") or {}
    page = data.get("currentSchematicPageInfo") or {}
    doc = data.get("currentDocumentInfo") or {}
    board = data.get("currentBoardInfo") or {}
    return {
        "project": proj.get("friendlyName") or proj.get("name"),
        "project_uuid": proj.get("uuid"),
        "page": page.get("name"),
        "page_uuid": page.get("uuid") or doc.get("uuid"),
        "document_type": doc.get("documentType"),
        "board": board.get("name"),
        "sch_selected": len(data.get("selectedSchPrimitiveIds") or []),
        "pcb_selected": len(data.get("selectedPcbPrimitiveIds") or []),
        "capturedAt": data.get("capturedAt"),
    }


def eda_snapshot(timeout_ms: int = 15000) -> dict[str, Any]:
    st = hub_lib.hub_bridge_status()
    rt = st.get("runtime") if isinstance(st.get("runtime"), dict) else {}
    clients = rt.get("bridgeClientCount")
    if not st.get("hub_port_open"):
        return {"ok": False, "error": "Hub 未监听", "hub": st.get("advice")}
    if clients == 0:
        return {
            "ok": False,
            "error": "Bridge 未连接",
            "advice": st.get("advice"),
            "expected_bridge_url": C.HUB_WS_URL,
        }
    raw = _http_mcp(
        "tools/call",
        {"name": "eda_context", "arguments": {"timeoutMs": timeout_ms}},
        timeout=timeout_ms / 1000 + 2,
    )
    if not raw.get("ok"):
        return raw
    data = raw.get("data")
    if not isinstance(data, dict):
        return {"ok": False, "error": "eda_context 返回非对象", "raw": data}
    return {"ok": True, "snapshot": _slim_context(data)}


def eda_invoke(
    api_full_name: str,
    args: list[Any] | None = None,
    timeout_ms: int = 15000,
) -> dict[str, Any]:
    name = (api_full_name or "").strip()
    if not name:
        return {"ok": False, "error": "api_full_name 为空"}
    if not name.startswith("eda."):
        return {"ok": False, "error": "api_full_name 须以 eda. 开头", "got": name}
    # 不依赖 status 文件里常过期的 bridgeClientCount；直调失败再报未连接
    raw = _http_mcp(
        "tools/call",
        {
            "name": "api_invoke",
            "arguments": {
                "apiFullName": name,
                "args": args or [],
                "timeoutMs": timeout_ms,
            },
        },
        timeout=timeout_ms / 1000 + 2,
    )
    if not raw.get("ok"):
        err = raw.get("error") or raw.get("rpc_error") or ""
        hint = None
        if "Bridge" in str(err) or "bridge" in str(err).lower():
            hint = f"确认立创 MCP Bridge = {C.HUB_WS_URL}"
        return {**raw, "api": name, **({"advice": hint} if hint else {})}
    data = raw.get("data")
    # Hub 可能 HTTP 成功但内层桥接超时
    if isinstance(data, dict) and data.get("timeout"):
        return {
            "ok": False,
            "api": name,
            "error": data.get("message") or "Bridge 回包超时",
            "timeout": data,
            "advice": f"确认立创已开工程且 Bridge={C.HUB_WS_URL}",
        }
    if isinstance(data, dict) and "result" in data and isinstance(data.get("result"), dict):
        inner = data["result"]
        if inner.get("timeout"):
            return {
                "ok": False,
                "api": name,
                "error": inner.get("message") or "Bridge 回包超时",
                "timeout": inner,
                "advice": f"确认立创已开工程且 Bridge={C.HUB_WS_URL}",
            }
    return {"ok": True, "api": name, "result": data}
