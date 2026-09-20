#!/usr/bin/env python3
"""Inspect and patch live LCEDA personal-library X25 footprint via API."""
from __future__ import annotations

import json
import sqlite3
import ssl
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "https://pro.lceda.cn"
OUT = Path(r"G:\soft\S200工程\lceda_project\analysis")
FP_LIB = "f0c0c271af94472d905c395236a4c10a"  # personal library footprint
SYM_LIB = "8344162c58f54de596ddaf533c85ed31"
MODEL_LIB = "1f42c6153a22428ca6604af43f231db8"

MM = 39.37008
HX = round(25.5 * MM, 4)
HY = round(26.75 * MM, 4)
HOLE = round(3.2 * MM, 4)
PAD_OD = round(6.0 * MM, 4)


def cookies():
    con = sqlite3.connect(r"C:\Users\alu\Documents\LCEDA-Pro\database\web.db")
    return {
        n: v
        for d, n, v in con.execute(
            "SELECT domain, name, value FROM web_cookies WHERE domain LIKE '%lceda%' OR domain LIKE '%jlc%'"
        )
    }


def call(method, path, body=None):
    c = cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 lceda-pro",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "Referer": BASE + "/",
        "Cookie": "; ".join(f"{k}={v}" for k, v in c.items()),
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    if "csrf_token" in c:
        headers["X-CSRF-TOKEN"] = c["csrf_token"]
    r = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(r, timeout=60, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:1000]}


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def pad_block(start_ticket=180, z0=200):
    parts = []
    t = start_ticket
    parts.append(dumps({"type": "ELE_PLACEHOLDER", "ticket": t, "id": "x25_pad_ph"}))
    parts.append(dumps({"dataType": "PAD", "max": z0 + 10}))
    t += 1
    for n, (num, cx, cy) in enumerate(
        [("1", -HX, HY), ("2", HX, HY), ("3", -HX, -HY), ("4", HX, -HY)]
    ):
        parts.append(dumps({"type": "PAD", "ticket": t, "id": f"x25pad{num}"}))
        parts.append(
            dumps(
                {
                    "groupId": 0,
                    "netName": "",
                    "layerId": 12,
                    "num": num,
                    "centerX": cx,
                    "centerY": cy,
                    "padAngle": 0,
                    "hole": {"holeType": "ROUND", "width": HOLE, "height": HOLE},
                    "defaultPad": {"padType": "ELLIPSE", "width": PAD_OD, "height": PAD_OD},
                    "specialPad": [],
                    "padOffsetX": 0,
                    "padOffsetY": 0,
                    "relativeAngle": 0,
                    "plated": True,
                    "padType": "NORMAL",
                    "topSolderExpansion": None,
                    "bottomSolderExpansion": None,
                    "topPasteExpansion": None,
                    "bottomPasteExpansion": None,
                    "locked": False,
                    "zIndex": z0 + n,
                    "connectMode": None,
                    "spokeSpace": None,
                    "spokeWidth": None,
                    "spokeAngle": None,
                    "padLen": 0,
                }
            )
        )
        t += 1
    paired = []
    i = 0
    while i < len(parts):
        paired.append(f"{parts[i]}||{parts[i+1]}")
        i += 2
    return "|\n".join(paired) + "|\n"


def inject_pads(data_str: str) -> str:
    if '"type":"PAD"' in data_str:
        print("already has PAD")
        return data_str
    import re

    metas = list(
        re.finditer(r'\{"type":"META","ticket":\d+,"id":"META"\}\|\|', data_str)
    )
    if not metas:
        raise RuntimeError("META not found in dataStr")
    insert_at = metas[-1].start()
    block = pad_block()
    print("inject at", insert_at, "block", len(block))
    return data_str[:insert_at] + block + data_str[insert_at:]


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    # devices search
    st, j = call("POST", "/api/devices/search", {"wd": "CUAV_X25", "page": 1, "pageSize": 20})
    print("device search", st, json.dumps(j, ensure_ascii=False)[:500])
    (OUT / "api_devices_x25.json").write_text(
        json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    st, j = call("GET", f"/api/v2/components/{FP_LIB}")
    print("GET fp", st, "success", j.get("success"))
    fp = j.get("result") or {}
    ds = fp.get("dataStr") or ""
    print(
        "title",
        fp.get("title"),
        "ticket",
        fp.get("ticket"),
        "dataStr",
        len(ds),
        "PAD",
        ds.count('"type":"PAD"'),
    )
    (OUT / "lib_fp_before.json").write_text(
        json.dumps(fp, ensure_ascii=False, indent=2)[:200000], encoding="utf-8"
    )
    (OUT / "lib_fp_before.datastr.txt").write_text(ds, encoding="utf-8")

    if not ds:
        raise SystemExit("empty dataStr")

    new_ds = inject_pads(ds)
    print("new PAD count", new_ds.count('"type":"PAD"'), "len", len(new_ds))

    # Build update body: try multiple shapes used by LCEDA
    now = int(time.time() * 1000)
    candidates = [
        (
            "update",
            "POST",
            f"/api/v2/components/{FP_LIB}/update",
            {
                "uuid": FP_LIB,
                "dataStr": new_ds,
                "ticket": (fp.get("ticket") or 0) + 1,
                "title": fp.get("title"),
                "display_title": fp.get("display_title") or fp.get("title"),
                "description": fp.get("description") or "",
                "docType": fp.get("docType"),
                "updateTime": now,
            },
        ),
        (
            "update_canvas",
            "POST",
            f"/api/v2/components/{FP_LIB}/update_canvas",
            {
                "uuid": FP_LIB,
                "dataStr": new_ds,
                "ticket": (fp.get("ticket") or 0) + 1,
            },
        ),
        (
            "upload",
            "POST",
            "/api/v2/components/upload",
            {
                **{k: fp[k] for k in fp if k not in ("creator", "modifier", "owner", "tags")},
                "dataStr": new_ds,
                "ticket": (fp.get("ticket") or 0) + 1,
                "updateTime": now,
            },
        ),
    ]

    for name, method, path, body in candidates:
        # strip non-serializable nested
        clean = {}
        for k, v in body.items():
            if isinstance(v, (dict, list)) and k not in ("dataStr",):
                # keep simple
                if k in ("tags", "custom_tags"):
                    clean[k] = v
                continue
            clean[k] = v
        # always keep dataStr
        clean["dataStr"] = new_ds
        clean["uuid"] = FP_LIB
        st, resp = call(method, path, clean)
        print(f"TRY {name} {path} -> {st} success={resp.get('success')} msg={resp.get('message') or resp.get('msg')}")
        (OUT / f"api_update_{name}.json").write_text(
            json.dumps(resp, ensure_ascii=False, indent=2)[:50000], encoding="utf-8"
        )
        if resp.get("success"):
            break

    # verify
    st, j = call("GET", f"/api/v2/components/{FP_LIB}")
    ds2 = (j.get("result") or {}).get("dataStr") or ""
    print("VERIFY PAD", ds2.count('"type":"PAD"'), "len", len(ds2))
    (OUT / "lib_fp_after.datastr.txt").write_text(ds2, encoding="utf-8")


if __name__ == "__main__":
    main()
