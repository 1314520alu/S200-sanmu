#!/usr/bin/env python3
"""Fetch P1 sch page + inject H1 FC nets via cloud API (no Bridge)."""
from __future__ import annotations

import json
import math
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from lib import cloud
from lib import constants as C
from lib.sch_nets import net_for_h1_pin, PIN_CACHE

PROJ = C.PROJECT_UUID
PAGE = "d688acf5296ad5d7"
OUT = C.ANALYSIS_DIR / "live_sch_page_p1.json"
WIRE_OUT = 24


def tip(x, y, rot, length):
    rad = math.radians(rot or 0)
    return x + length * math.cos(rad), y + length * math.sin(rad)


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def build_wire_net(x0, y0, x1, y1, net: str, z: int) -> list[dict]:
    """Match existing CAN wire shape in docfull: WIRE + LINE + Relevance ATTR + NET ATTR."""
    wire_id = new_id()
    line_id = new_id()
    rel_id = new_id()
    net_id = new_id()
    return [
        {"type": "WIRE", "ticket": 0, "id": wire_id},
        {"zIndex": z},
        {"type": "LINE", "ticket": 0, "id": line_id},
        {
            "fillColor": None,
            "fillStyle": None,
            "strokeColor": None,
            "strokeStyle": None,
            "strokeWidth": None,
            "startX": x0,
            "startY": y0,
            "endX": x1,
            "endY": y1,
            "lineGroup": wire_id,
        },
        {"type": "ATTR", "ticket": 0, "id": rel_id},
        {
            "x": None,
            "y": None,
            "rotation": None,
            "color": None,
            "fontFamily": None,
            "fontSize": None,
            "fontWeight": None,
            "italic": None,
            "underline": None,
            "align": None,
            "value": "[]",
            "keyVisible": None,
            "valueVisible": None,
            "key": "Relevance",
            "fillColor": None,
            "parentId": wire_id,
            "zIndex": None,
        },
        {"type": "ATTR", "ticket": 0, "id": net_id},
        {
            "x": x1,
            "y": y1,
            "rotation": 0,
            "color": None,
            "fontFamily": None,
            "fontSize": None,
            "fontWeight": None,
            "italic": None,
            "underline": None,
            "align": None,
            "value": net,
            "keyVisible": False,
            "valueVisible": True,
            "key": "NET",
            "fillColor": None,
            "parentId": wire_id,
            "zIndex": 3,
        },
    ]


def parse_content(content):
    if isinstance(content, str):
        return json.loads(content)
    return content


def main() -> int:
    st, j = cloud.call("GET", f"/api/v4/projects/{PROJ}/documents/{PAGE}", timeout=90)
    if st != 200 or not isinstance(j, dict) or not j.get("success"):
        print(json.dumps({"ok": False, "step": "get", "st": st, "j": j}, ensure_ascii=False)[:2000])
        return 1

    res = j["result"]
    content = parse_content(res.get("content"))
    OUT.write_text(
        json.dumps({"meta": {k: res[k] for k in res if k != "content"}, "content": content}, ensure_ascii=False),
        encoding="utf-8",
    )

    # content is typically a list of primitive dicts (EasyEDA style)
    if not isinstance(content, list):
        print(json.dumps({"ok": False, "step": "content_type", "type": type(content).__name__, "keys": list(content)[:20] if isinstance(content, dict) else None}, ensure_ascii=False))
        return 1

    pins = json.loads(PIN_CACHE.read_text(encoding="utf-8"))
    # detect existing H1 fc nets we already added
    existing_nets = set()
    for i, item in enumerate(content):
        if isinstance(item, dict) and item.get("key") == "NET":
            existing_nets.add(item.get("value"))

    already = {n for n in existing_nets if n in {f"M{i}" for i in range(1, 17)} | {"SERVO_VCC", "FC_GND"}}
    max_z = 100
    for item in content:
        if isinstance(item, dict) and isinstance(item.get("zIndex"), int):
            max_z = max(max_z, item["zIndex"])

    added = []
    chunks = []
    for p in sorted(pins, key=lambda x: int(x["pinNumber"])):
        n = int(p["pinNumber"])
        net = net_for_h1_pin(n)
        # skip if this exact pin already has a short stub — hard to detect; skip whole net if SERVO/GND already and M already present
        if net.startswith("M") and net in already:
            continue
        x0, y0 = tip(p["x"], p["y"], p["rotation"], p["pinLength"])
        x1, y1 = tip(p["x"], p["y"], p["rotation"], p["pinLength"] + WIRE_OUT)
        max_z += 1
        chunks.extend(build_wire_net(round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2), net, max_z))
        added.append({"pin": n, "net": net})

    if not added:
        print(json.dumps({"ok": True, "skipped": True, "reason": "nets already present", "already": sorted(already)}, ensure_ascii=False))
        return 0

    new_content = content + chunks
    now = int(time.time() * 1000)

    # probe update endpoints
    body_candidates = []
    # common v4 document update shapes
    body_candidates.append(
        (
            "PUT",
            f"/api/v4/projects/{PROJ}/documents/{PAGE}",
            {
                "uuid": PAGE,
                "name": res.get("name") or "P1",
                "content": json.dumps(new_content, ensure_ascii=False, separators=(",", ":")),
                "version": res.get("version"),
                "updateTime": now,
            },
        )
    )
    body_candidates.append(
        (
            "POST",
            f"/api/v4/projects/{PROJ}/documents/{PAGE}/update",
            {
                "uuid": PAGE,
                "content": json.dumps(new_content, ensure_ascii=False, separators=(",", ":")),
                "version": res.get("version"),
                "updateTime": now,
            },
        )
    )
    body_candidates.append(
        (
            "POST",
            f"/api/v4/projects/{PROJ}/documents/update",
            {
                "uuid": PAGE,
                "content": json.dumps(new_content, ensure_ascii=False, separators=(",", ":")),
                "version": res.get("version"),
                "updateTime": now,
            },
        )
    )

    results = []
    for method, path, body in body_candidates:
        st2, j2 = cloud.call(method, path, body, timeout=90)
        ok = st2 in (200, 201) and isinstance(j2, dict) and (j2.get("success") is True or j2.get("code") in (0, 200))
        results.append({"method": method, "path": path, "st": st2, "ok": ok, "preview": str(j2)[:300]})
        if ok:
            by_net = {}
            for a in added:
                by_net.setdefault(a["net"], []).append(a["pin"])
            print(
                json.dumps(
                    {
                        "ok": True,
                        "via": f"{method} {path}",
                        "added": len(added),
                        "nets": by_net,
                        "hint": "云端已写；立创里重新打开/刷新 P1 可见",
                    },
                    ensure_ascii=False,
                )
            )
            return 0

    print(json.dumps({"ok": False, "step": "update", "tried": results}, ensure_ascii=False))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
