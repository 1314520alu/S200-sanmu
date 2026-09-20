#!/usr/bin/env python3
"""Upload fixed X25 footprint dataStr into personal library component."""
from __future__ import annotations

import json
import re
import sqlite3
import ssl
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "https://pro.lceda.cn"
OUT = Path(r"G:\soft\S200工程\lceda_project\analysis")
FP_LIB = "f0c0c271af94472d905c395236a4c10a"
SYM_LIB = "8344162c58f54de596ddaf533c85ed31"
DEVICE_LIB = "c448d4e8f4bd4dac9bda22e039fc5058"
# project-local copies inside epru
FP_PROJ = "64c5a8ceeba634d8"
SRC_EPRU = Path(r"G:\soft\S200工程\lceda_project\S200飞机_fixed\S200飞机.epru")
# fallback original
SRC_EPRU_ORIG = Path(r"G:\soft\S200工程\lceda_project\S200飞机_backup\S200飞机.epru")

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


def call(method, path, body=None, extra_headers=None):
    c = cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 lceda-pro",
        "Accept": "application/json, text/plain, */*",
        "Origin": BASE,
        "Referer": BASE + "/",
        "Cookie": "; ".join(f"{k}={v}" for k, v in c.items()),
        "path": "f4d2341cf4484ec7a4e1b0e1ff4fbab1",
    }
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    if "csrf_token" in c:
        headers["X-CSRF-TOKEN"] = c["csrf_token"]
    r = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(r, timeout=120, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:2000]}


def dumps(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def pad_block(start_ticket=180, z0=200):
    parts = []
    t = start_ticket
    parts += [
        dumps({"type": "ELE_PLACEHOLDER", "ticket": t, "id": "x25_pad_ph"}),
        dumps({"dataType": "PAD", "max": z0 + 10}),
    ]
    t += 1
    for n, (num, cx, cy) in enumerate(
        [("1", -HX, HY), ("2", HX, HY), ("3", -HX, -HY), ("4", HX, -HY)]
    ):
        parts += [
            dumps({"type": "PAD", "ticket": t, "id": f"x25pad{num}"}),
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
            ),
        ]
        t += 1
    paired = []
    for i in range(0, len(parts), 2):
        paired.append(f"{parts[i]}||{parts[i+1]}")
    return "|\n".join(paired) + "|\n"


def inject_pads(data_str: str) -> str:
    if '"type":"PAD"' in data_str:
        return data_str
    metas = list(re.finditer(r'\{"type":"META","ticket":\d+,"id":"META"\}\|\|', data_str))
    if not metas:
        raise RuntimeError("no META")
    at = metas[-1].start()
    return data_str[:at] + pad_block() + data_str[at:]


def extract_doc_datastr(epru_path: Path, uuid: str) -> str:
    """Extract one document body from epru as dataStr (without leading DOCHEAD pairing quirks).

    dataStr format in LCEDA components is typically newline-separated records similar to epru body
    starting after the doc head. We'll take the region from FOOTPRINT head through before next DOCHEAD,
    but component dataStr usually does NOT include the outer docType head — it starts with ATTR/LAYER.
    """
    raw = epru_path.read_text(encoding="utf-8", errors="replace")
    marker = f'"uuid":"{uuid}"'
    pos = raw.find(marker)
    if pos < 0:
        raise RuntimeError(f"uuid {uuid} not in {epru_path}")
    # find start of doc head object
    head_start = raw.rfind("{", 0, pos)
    # find end of head
    depth = 0
    in_str = False
    esc = False
    head_end = None
    for j in range(head_start, len(raw)):
        ch = raw[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                head_end = j + 1
                break
    assert head_end
    next_doc = raw.find('{"type":"DOCHEAD"}', head_end)
    region_end = next_doc if next_doc > 0 else len(raw)
    # body after head: usually starts with | or |\n then first object
    body = raw[head_end:region_end]
    # strip leading separators
    body = body.lstrip("|\n\r ")
    # component dataStr often includes content from first ATTR/LAYER; keep as-is from first {
    first = body.find("{")
    if first >= 0:
        body = body[first:]
    # ensure pads
    body = inject_pads(body if '"type":"PAD"' in body or True else body)
    # if inject ran on already-padded from fixed epru, inject_pads no-ops when PAD present
    return body


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    src = SRC_EPRU if SRC_EPRU.exists() else SRC_EPRU_ORIG
    print("source", src)
    data_str = extract_doc_datastr(src, FP_PROJ)
    print("extracted len", len(data_str), "PAD", data_str.count('"type":"PAD"'))
    (OUT / "upload_fp.datastr.txt").write_text(data_str, encoding="utf-8")

    # get current meta
    st, j = call("GET", f"/api/v2/components/{FP_LIB}")
    fp = j.get("result") or {}
    ticket = int(fp.get("ticket") or 0)
    now = int(time.time() * 1000)
    print("current ticket", ticket, "version", fp.get("version"))

    bodies = [
        (
            "update",
            f"/api/v2/components/{FP_LIB}/update",
            {
                "uuid": FP_LIB,
                "title": fp.get("title") or "cuav_x25_mega_colored",
                "display_title": fp.get("display_title") or "CUAV_X25_MEGA_colored",
                "description": fp.get("description") or "",
                "docType": 4,
                "dataStr": data_str,
                "ticket": ticket + 1,
                "updateTime": now,
                "version": str(now),
            },
        ),
        (
            "update_canvas",
            f"/api/v2/components/{FP_LIB}/update_canvas",
            {
                "uuid": FP_LIB,
                "dataStr": data_str,
                "ticket": ticket + 1,
                "updateTime": now,
            },
        ),
        (
            "upload",
            "/api/v2/components/upload",
            {
                "uuid": FP_LIB,
                "title": fp.get("title") or "cuav_x25_mega_colored",
                "display_title": fp.get("display_title") or "CUAV_X25_MEGA_colored",
                "description": "",
                "docType": 4,
                "dataStr": data_str,
                "ticket": ticket + 1,
                "updateTime": now,
                "public": True,
                "type": 3,
                "path": "f4d2341cf4484ec7a4e1b0e1ff4fbab1",
            },
        ),
    ]

    ok = False
    for name, path, body in bodies:
        st, resp = call("POST", path, body)
        print(
            f"{name} -> {st} success={resp.get('success')} code={resp.get('code')} "
            f"msg={resp.get('message') or resp.get('msg')} keys={list(resp)[:10]}"
        )
        (OUT / f"upload_{name}_resp.json").write_text(
            json.dumps(resp, ensure_ascii=False, indent=2)[:100000], encoding="utf-8"
        )
        if resp.get("success"):
            ok = True
            break

    # verify
    st, j = call("GET", f"/api/v2/components/{FP_LIB}")
    ds = (j.get("result") or {}).get("dataStr") or ""
    print("VERIFY dataStr len", len(ds), "PAD", ds.count('"type":"PAD"'))
    print("ok", ok)


if __name__ == "__main__":
    main()
