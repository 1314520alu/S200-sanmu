#!/usr/bin/env python3
"""One-shot: H1 → M1-M16 / SERVO_VCC / FC_GND（经 Hub HTTP，一次跑完）."""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import bridge

H1_ID = "c33cb9b2a93ab545"
OUT = 24  # 出脚后再延伸的导线长度


def net_for_pin(n: int) -> str:
    rem = n % 3
    if rem == 1:
        return f"M{(n + 2) // 3}"
    if rem == 2:
        return "SERVO_VCC"
    return "FC_GND"


def tip(x: float, y: float, rot: float, length: float) -> tuple[float, float]:
    rad = math.radians(rot or 0)
    return x + length * math.cos(rad), y + length * math.sin(rad)


def invoke(api: str, args: list, timeout_ms: int = 20000) -> dict:
    """直调 Hub HTTP，跳过 status 文件里常过期的 bridgeClientCount 门闩。"""
    raw = bridge._http_mcp(
        "tools/call",
        {
            "name": "api_invoke",
            "arguments": {
                "apiFullName": api,
                "args": args,
                "timeoutMs": timeout_ms,
            },
        },
        timeout=timeout_ms / 1000 + 2,
    )
    if not raw.get("ok"):
        return {**raw, "api": api}
    return {"ok": True, "api": api, "result": raw.get("data")}


def main() -> int:
    pins_r = invoke(
        "eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId",
        [H1_ID],
        45000,
    )
    if not pins_r.get("ok"):
        print(json.dumps({"ok": False, "step": "getPins", **pins_r}, ensure_ascii=False, default=str))
        return 1

    raw = pins_r.get("result")
    if isinstance(raw, dict):
        raw = raw.get("result") or raw.get("data") or raw
    if not isinstance(raw, list) or not raw:
        print(json.dumps({"ok": False, "step": "parsePins", "raw": raw}, ensure_ascii=False, default=str)[:3000])
        return 1

    pins = sorted(raw, key=lambda p: int(p["pinNumber"]))
    created = []
    failed = []
    labeled_shared: set[str] = set()

    for p in pins:
        n = int(p["pinNumber"])
        net = net_for_pin(n)
        x0, y0 = tip(p["x"], p["y"], p["rotation"], p["pinLength"])
        x1, y1 = tip(p["x"], p["y"], p["rotation"], p["pinLength"] + OUT)

        wr = invoke("eda.sch_PrimitiveWire.create", [[x0, y0, x1, y1], net])
        if not wr.get("ok"):
            failed.append({"pin": n, "net": net, "err": wr})
            continue

        # M1-M16 每脚都打标签；SERVO_VCC / FC_GND 各打一次即可（其余靠同名导线连通）
        need_label = net.startswith("M") or net not in labeled_shared
        if need_label:
            lr = invoke("eda.sch_PrimitiveAttribute.createNetLabel", [x1, y1, net])
            if lr.get("ok") and not net.startswith("M"):
                labeled_shared.add(net)
            via = "wire+label" if lr.get("ok") else "wire"
        else:
            via = "wire"

        created.append({"pin": n, "net": net, "via": via})

    by_net: dict[str, list[int]] = {}
    for c in created:
        by_net.setdefault(c["net"], []).append(c["pin"])

    def sort_key(name: str):
        if name.startswith("M") and name[1:].isdigit():
            return (0, int(name[1:]))
        return (1, name)

    print(
        json.dumps(
            {
                "ok": len(failed) == 0 and len(created) == 48,
                "created": len(created),
                "failed": len(failed),
                "nets": {k: by_net[k] for k in sorted(by_net, key=sort_key)},
                "errors": failed[:3],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not failed else 2


if __name__ == "__main__":
    raise SystemExit(main())
