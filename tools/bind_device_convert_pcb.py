#!/usr/bin/env python3
"""Point project-related device footprint to library FP; set Convert to PCB."""
from __future__ import annotations

import json
import sqlite3
import ssl
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = "https://pro.lceda.cn"
FP_LIB = "f0c0c271af94472d905c395236a4c10a"
DEV_LIB = "c448d4e8f4bd4dac9bda22e039fc5058"
DEV_PROJ = "537727934d365244"


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
        "path": "f4d2341cf4484ec7a4e1b0e1ff4fbab1",
    }
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode()
        headers["Content-Type"] = "application/json;charset=UTF-8"
    if "csrf_token" in c:
        headers["X-CSRF-TOKEN"] = c["csrf_token"]
    r = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(r, timeout=60, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read().decode())
    except HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:1000]}


def main():
    st, j = call("POST", "/api/devices/searchByIds", {"uuids": [DEV_LIB, DEV_PROJ]})
    print("devices found", len(j.get("result") or []))
    for d in j.get("result") or []:
        print(d.get("uuid"), d.get("attributes"))

    # Update library device: Footprint=lib FP, Convert to PCB=yes
    st, j = call("GET", f"/api/devices/{DEV_LIB}")
    res = j.get("result") or {}
    attrs = dict(res.get("attributes") or {})
    attrs["Footprint"] = FP_LIB
    attrs["Symbol"] = "8344162c58f54de596ddaf533c85ed31"
    attrs["Convert to PCB"] = "yes"
    # Remove confusing Device pointer to project uuid
    attrs.pop("Device", None)

    body = {
        "uuid": DEV_LIB,
        "title": res.get("title") or "cuav_x25_mega_colored",
        "display_title": res.get("display_title") or "CUAV_X25_MEGA_colored",
        "description": res.get("description") or "",
        "attributes": attrs,
        "ticket": int(res.get("ticket") or 0) + 1,
        "updateTime": int(time.time()),
        "images": res.get("images") or [""],
    }
    st, resp = call("POST", f"/api/devices/{DEV_LIB}", body)
    print("update device", st, resp.get("success"), resp.get("result", {}).get("attributes") if isinstance(resp.get("result"), dict) else resp)

    # Re-open footprint via update_canvas with same data to bump visibility / cache
    from pathlib import Path

    data = Path(r"G:\soft\S200工程\lceda_project\analysis\upload_fp.datastr.txt").read_text(
        encoding="utf-8"
    )
    st, meta = call("GET", f"/api/v2/components/{FP_LIB}")
    ticket = int((meta.get("result") or {}).get("ticket") or 0)
    st, resp = call(
        "POST",
        f"/api/v2/components/{FP_LIB}/update_canvas",
        {
            "uuid": FP_LIB,
            "dataStr": data,
            "ticket": ticket + 1,
            "updateTime": int(time.time() * 1000),
            "docType": 4,
        },
    )
    ds = (resp.get("result") or {}).get("dataStr") or ""
    print(
        "canvas refresh",
        st,
        resp.get("success"),
        "PAD",
        ds.count('"type":"PAD"'),
        "ticket",
        (resp.get("result") or {}).get("ticket"),
    )

if __name__ == "__main__":
    main()
