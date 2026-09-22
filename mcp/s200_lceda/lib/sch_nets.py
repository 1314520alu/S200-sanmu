"""Schematic net helpers via Hub HTTP (no official multi-step passthrough)."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from . import bridge

H1_ID = "c33cb9b2a93ab545"
WIRE_OUT = 24
PIN_CACHE = Path(__file__).with_name("h1_pins_cache.json")


def net_for_h1_pin(n: int) -> str:
    """1/4/7…→M1-M16；2/5/8…→SERVO_VCC；3/6/9…→FC_GND。"""
    rem = n % 3
    if rem == 1:
        return f"M{(n + 2) // 3}"
    if rem == 2:
        return "SERVO_VCC"
    return "FC_GND"


def _tip(x: float, y: float, rot: float, length: float) -> tuple[float, float]:
    rad = math.radians(rot or 0)
    return x + length * math.cos(rad), y + length * math.sin(rad)


def _pins_list(raw: Any) -> list[dict[str, Any]] | None:
    if isinstance(raw, dict):
        if raw.get("timeout"):
            return None
        raw = raw.get("result") or raw.get("data") or raw
    if not isinstance(raw, list):
        return None
    return [p for p in raw if isinstance(p, dict) and p.get("pinNumber") is not None]


def _load_pin_cache() -> list[dict[str, Any]] | None:
    if not PIN_CACHE.exists():
        return None
    try:
        data = json.loads(PIN_CACHE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _pins_list(data)


def h1_fc_nets(h1_id: str = H1_ID, wire_out: float = WIRE_OUT) -> dict[str, Any]:
    """一次性给 H1 画出飞控舵机排针网络。"""
    pins: list[dict[str, Any]] | None = None
    source = "live"
    pins_r: dict[str, Any] = {}

    pins_r = bridge.eda_invoke(
        "eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId",
        [h1_id],
        20000,
    )
    if pins_r.get("ok"):
        pins = _pins_list(pins_r.get("result"))
        if pins:
            try:
                slim = [
                    {
                        "x": p["x"],
                        "y": p["y"],
                        "pinNumber": p["pinNumber"],
                        "rotation": p.get("rotation", 0),
                        "pinLength": p.get("pinLength", 10),
                    }
                    for p in pins
                ]
                PIN_CACHE.write_text(json.dumps(slim, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass

    if not pins:
        pins = _load_pin_cache()
        source = "cache"
    if not pins:
        return {
            "ok": False,
            "step": "getPins",
            "error": pins_r.get("error") if isinstance(pins_r, dict) else "no pins",
            "advice": "Bridge 无响应；请在立创重连 MCP Bridge 后重试 h1_fc_nets",
            "expected_bridge_url": "ws://127.0.0.1:9050/bridge/ws",
        }

    pins = sorted(pins, key=lambda p: int(p["pinNumber"]))
    created: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    labeled_shared: set[str] = set()

    for p in pins:
        n = int(p["pinNumber"])
        net = net_for_h1_pin(n)
        plen = float(p.get("pinLength") or 10)
        rot = float(p.get("rotation") or 0)
        x0, y0 = _tip(float(p["x"]), float(p["y"]), rot, plen)
        x1, y1 = _tip(float(p["x"]), float(p["y"]), rot, plen + wire_out)

        wr = bridge.eda_invoke(
            "eda.sch_PrimitiveWire.create",
            [[x0, y0, x1, y1], net],
            15000,
        )
        if not wr.get("ok"):
            failed.append({"pin": n, "net": net, "err": wr.get("error") or wr})
            if wr.get("timeout") or "超时" in str(wr.get("error") or ""):
                break
            continue

        need_label = net.startswith("M") or net not in labeled_shared
        via = "wire"
        if need_label:
            lr = bridge.eda_invoke(
                "eda.sch_PrimitiveAttribute.createNetLabel",
                [x1, y1, net],
                15000,
            )
            if lr.get("ok"):
                via = "wire+label"
                if not net.startswith("M"):
                    labeled_shared.add(net)

        created.append({"pin": n, "net": net, "via": via})

    by_net: dict[str, list[int]] = {}
    for c in created:
        by_net.setdefault(c["net"], []).append(c["pin"])

    def sort_key(name: str) -> tuple:
        if name.startswith("M") and name[1:].isdigit():
            return (0, int(name[1:]))
        return (1, name)

    return {
        "ok": len(failed) == 0 and len(created) == len(pins),
        "h1_id": h1_id,
        "pin_source": source,
        "created": len(created),
        "failed_count": len(failed),
        "nets": {k: by_net[k] for k in sorted(by_net, key=sort_key)},
        "errors": failed[:5],
        "rule": "pin%3==1→M#; ==2→SERVO_VCC; ==0→FC_GND",
    }
