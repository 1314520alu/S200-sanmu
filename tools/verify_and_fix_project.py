#!/usr/bin/env python3
"""Verify library pads and update S200 project schematic Footprint binding."""
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
PROJECT = "6798d283322f489e966f8c310276b491"
SCH_COMP = "99a200c10781d133"
DEVICE = "537727934d365244"


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
            return e.code, {"raw": raw[:1500]}


def main():
    # verify from last canvas response file
    for name in ("canvas_simple", "canvas_full"):
        p = OUT / f"canvas_{name}.json"
        if not p.exists():
            continue
        j = json.loads(p.read_text(encoding="utf-8"))
        ds = (j.get("result") or {}).get("dataStr") or ""
        print(name, "PAD", ds.count('"type":"PAD"'), "centers", ds.count("1003.937"))

    # re-fetch via update_canvas noop? or GET might still strip - use history
    st, j = call("GET", f"/api/v2/components/{FP_LIB}", extra_headers={"path": "f4d2341cf4484ec7a4e1b0e1ff4fbab1"})
    print("GET after", "ticket", (j.get("result") or {}).get("ticket"))

    # project branches
    st, j = call("GET", f"/api/v4/projects/{PROJECT}/branches")
    print("branches", st, json.dumps(j, ensure_ascii=False)[:800])
    (OUT / "project_branches.json").write_text(json.dumps(j, ensure_ascii=False, indent=2), encoding="utf-8")
    branches = (j.get("result") or {}).get("lists") or j.get("result") or []
    if isinstance(branches, dict):
        branches = branches.get("lists") or []
    branch = None
    if isinstance(branches, list) and branches:
        branch = branches[0].get("uuid")
        print("branch0", branch, branches[0].get("name"))

    # schematic list variants
    for method, path, body in [
        ("GET", f"/api/schematic/lists?project_uuid={PROJECT}", None),
        ("POST", "/api/schematic/lists", {"project_uuid": PROJECT}),
        ("POST", "/api/v2/documents/lists", {"project_uuid": PROJECT}),
        ("GET", f"/api/v2/schematic/{PROJECT}/documents", None),
    ]:
        st, resp = call(method, path, body)
        print(method, path, st, str(resp)[:250].replace("\n", " "))

    if branch:
        st, j = call("GET", f"/api/v4/projects/{PROJECT}/branches/{branch}/structures")
        print("structures", st, str(j)[:500])
        (OUT / "project_structures.json").write_text(
            json.dumps(j, ensure_ascii=False, indent=2)[:300000], encoding="utf-8"
        )

        # checkout docs?
        st, j = call("POST", f"/api/v4/documents/checkout/{PROJECT}/{branch}", {})
        print("checkout", st, str(j)[:500])


if __name__ == "__main__":
    main()
