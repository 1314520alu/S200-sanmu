#!/usr/bin/env python3
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
FP_LIB = "f0c0c271af94472d905c395236a4c10a"
DEV_LIB = "c448d4e8f4bd4dac9bda22e039fc5058"


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
    st, j = call("POST", "/api/v2/components/searchByIds", {"uuids": [FP_LIB]})
    items = j.get("result") or []
    print("n", len(items))
    for it in items:
        ds = it.get("dataStr") or ""
        print(
            it.get("uuid"),
            "ticket",
            it.get("ticket"),
            "dataStr",
            len(ds),
            "PAD",
            ds.count('"type":"PAD"'),
            "updateTime",
            it.get("updateTime"),
        )
        (OUT / "lib_fp_searchByIds.json").write_text(
            json.dumps(it, ensure_ascii=False, indent=2)[:200000], encoding="utf-8"
        )
        if ds:
            (OUT / "lib_fp_live.datastr.txt").write_text(ds, encoding="utf-8")

    # device confirm
    st, j = call("GET", f"/api/devices/{DEV_LIB}")
    res = j.get("result") or {}
    print("device attrs", res.get("attributes"))
    print("device title", res.get("title"), res.get("display_title"))

    # Ensure Convert to PCB enabled if such attr exists
    attrs = dict(res.get("attributes") or {})
    attrs["Footprint"] = FP_LIB
    attrs["Symbol"] = attrs.get("Symbol") or "8344162c58f54de596ddaf533c85ed31"
    # clear bogus Device self-pointer if present
    if attrs.get("Device") and attrs.get("Device") != DEV_LIB:
        print("note: Device attr was", attrs.get("Device"))

    body = {
        "uuid": DEV_LIB,
        "title": res.get("title") or "cuav_x25_mega_colored",
        "display_title": res.get("display_title") or "CUAV_X25_MEGA_colored",
        "attributes": attrs,
        "ticket": int(res.get("ticket") or 0) + 1,
        "updateTime": int(time.time() * 1000),
    }
    for path in [
        f"/api/devices/{DEV_LIB}",
        "/api/devices/upload",
        "/api/devices/updateMany",
    ]:
        payload = body if "updateMany" not in path else [body]
        st, resp = call("POST", path, payload)
        print("device update", path, st, resp.get("success"), resp.get("message") or resp.get("code"))
        if resp.get("success"):
            break

    # Final verification via searchByIds again
    st, j = call("POST", "/api/v2/components/searchByIds", {"uuids": [FP_LIB]})
    it = (j.get("result") or [{}])[0]
    ds = it.get("dataStr") or ""
    print("FINAL PAD", ds.count('"type":"PAD"'), "len", len(ds), "ticket", it.get("ticket"))


if __name__ == "__main__":
    main()
