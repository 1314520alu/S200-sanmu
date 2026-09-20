"""立创云端 API：cookie 来自本机 web.db，直接写入库器件/封装。"""
from __future__ import annotations

import json
import sqlite3
import ssl
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import constants as C
from . import epru


def cookies() -> dict[str, str]:
    if not C.WEB_DB.exists():
        raise FileNotFoundError(f"web.db missing: {C.WEB_DB}（请先登录立创 EDA 专业版）")
    con = sqlite3.connect(str(C.WEB_DB))
    try:
        return {
            n: v
            for d, n, v in con.execute(
                "SELECT domain, name, value FROM web_cookies "
                "WHERE domain LIKE '%lceda%' OR domain LIKE '%jlc%'"
            )
        }
    finally:
        con.close()


def auth_check() -> dict[str, Any]:
    try:
        c = cookies()
    except Exception as e:
        return {"ok": False, "error": str(e)}
    keys = sorted(c.keys())
    interesting = [k for k in keys if any(x in k.lower() for x in ("token", "session", "user", "csrf"))]
    return {
        "ok": bool(c),
        "cookie_count": len(c),
        "has_csrf": "csrf_token" in c,
        "interesting_keys": interesting,
        "web_db": str(C.WEB_DB),
    }


def call(
    method: str,
    path: str,
    body: Any = None,
    *,
    extra_headers: dict[str, str] | None = None,
    timeout: float = 120,
) -> tuple[int, dict[str, Any]]:
    c = cookies()
    headers = {
        "User-Agent": "Mozilla/5.0 s200-lceda-mcp",
        "Accept": "application/json, text/plain, */*",
        "Origin": C.LCEDA_API_BASE,
        "Referer": C.LCEDA_API_BASE + "/",
        "Cookie": "; ".join(f"{k}={v}" for k, v in c.items()),
        "path": C.LCEDA_LIB_PATH,
    }
    if extra_headers:
        headers.update(extra_headers)
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json;charset=UTF-8"
    if "csrf_token" in c:
        headers["X-CSRF-TOKEN"] = c["csrf_token"]
    req = Request(C.LCEDA_API_BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        raw = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, {"raw": raw[:2000]}
    except URLError as e:
        return 0, {"error": str(e.reason if hasattr(e, "reason") else e)}


def _summarize_fp(item: dict[str, Any]) -> dict[str, Any]:
    ds = item.get("dataStr") or ""
    return {
        "uuid": item.get("uuid"),
        "title": item.get("display_title") or item.get("title"),
        "ticket": item.get("ticket"),
        "updateTime": item.get("updateTime"),
        "dataStr_len": len(ds),
        "pad_count": ds.count('"type":"PAD"'),
        "has_pad": '"type":"PAD"' in ds,
    }


def fp_status(fp_uuid: str = C.FP_LIB) -> dict[str, Any]:
    # Prefer /api/components — v2 GET often returns empty dataStr even when pads exist.
    st, j = call("GET", f"/api/components/{fp_uuid}")
    res = j.get("result") if isinstance(j, dict) else None
    source = "api/components"
    if not isinstance(res, dict) or not (res.get("dataStr") or "").strip():
        st2, j2 = call("GET", f"/api/v2/components/{fp_uuid}")
        res2 = j2.get("result") if isinstance(j2, dict) else None
        if isinstance(res2, dict) and (res2.get("dataStr") or "").strip():
            st, j, res, source = st2, j2, res2, "api/v2/components"
        elif not isinstance(res, dict):
            st3, j3 = call("POST", "/api/v2/components/searchByIds", {"uuids": [fp_uuid]})
            items = j3.get("result") or []
            res3 = items[0] if items else None
            if isinstance(res3, dict):
                st, j, res, source = st3, j3, res3, "searchByIds"
    if not isinstance(res, dict):
        return {"ok": False, "http": st, "error": "component not found", "raw": j}
    summary = _summarize_fp(res)
    C.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    meta = {k: res.get(k) for k in res if k != "dataStr"}
    meta["dataStr_len"] = len(res.get("dataStr") or "")
    meta["pad_count"] = summary["pad_count"]
    (C.ANALYSIS_DIR / f"cloud_fp_{fp_uuid[:8]}.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2)[:200000], encoding="utf-8"
    )
    return {
        "ok": True,
        "http": st,
        "source": source,
        "success": j.get("success", True),
        **summary,
        "ready_for_pcb": summary["pad_count"] >= 4,
    }


def device_status(dev_uuid: str = C.DEV_LIB) -> dict[str, Any]:
    st, j = call("GET", f"/api/devices/{dev_uuid}")
    res = j.get("result") or {}
    if not res:
        return {"ok": False, "http": st, "error": "device not found", "raw": j}
    attrs = res.get("attributes") or {}
    return {
        "ok": True,
        "http": st,
        "uuid": res.get("uuid"),
        "title": res.get("display_title") or res.get("title"),
        "ticket": res.get("ticket"),
        "attributes": {
            "Footprint": attrs.get("Footprint"),
            "Symbol": attrs.get("Symbol"),
            "Convert to PCB": attrs.get("Convert to PCB"),
            "Device": attrs.get("Device"),
        },
        "footprint_ok": attrs.get("Footprint") in (C.FP_LIB, C.PRIMARY_FP_UUID),
        "convert_yes": str(attrs.get("Convert to PCB", "")).lower() in ("yes", "true", "1"),
    }


def extract_fp_datastr(
    epru_path: Path | None = None,
    proj_fp_uuid: str = C.PRIMARY_FP_UUID,
) -> dict[str, Any]:
    src = epru_path or (C.FIXED_EPRU if C.FIXED_EPRU.exists() else C.BACKUP_EPRU)
    if not src.exists():
        return {"ok": False, "error": f"epru not found: {src}"}
    raw = src.read_text(encoding="utf-8", errors="replace")
    region_info = epru.footprint_region(raw, proj_fp_uuid)
    if not region_info:
        return {"ok": False, "error": f"footprint {proj_fp_uuid} not in {src}"}
    head_start, region_end, _ = region_info
    head_end = epru.find_json_object_end(raw, head_start)
    body = raw[head_end:region_end].lstrip("|\n\r ")
    first = body.find("{")
    if first >= 0:
        body = body[first:]
    # ensure pads present in dataStr body
    if '"type":"PAD"' not in body:
        # inject using same pad_block as local fix
        from .epru import pad_block
        import re

        metas = list(re.finditer(r'\{"type":"META","ticket":\d+,"id":"META"\}\|\|', body))
        if not metas:
            return {"ok": False, "error": "no META in footprint body; cannot inject pads"}
        at = metas[-1].start()
        body = body[:at] + pad_block() + body[at:]
    C.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    out = C.ANALYSIS_DIR / "upload_fp.datastr.txt"
    out.write_text(body, encoding="utf-8")
    return {
        "ok": True,
        "source": str(src),
        "proj_fp_uuid": proj_fp_uuid,
        "datastr_path": str(out),
        "len": len(body),
        "pad_count": body.count('"type":"PAD"'),
        "dataStr": body,
    }


def upload_fp(
    epru_path: str | None = None,
    fp_lib_uuid: str = C.FP_LIB,
    proj_fp_uuid: str = C.PRIMARY_FP_UUID,
) -> dict[str, Any]:
    src = Path(epru_path) if epru_path else None
    if src and not src.is_absolute():
        src = C.ROOT / src
    extracted = extract_fp_datastr(src, proj_fp_uuid)
    if not extracted.get("ok"):
        return extracted
    data_str = extracted["dataStr"]

    st, meta_j = call("GET", f"/api/components/{fp_lib_uuid}")
    fp = meta_j.get("result") or {}
    if not fp:
        st, meta_j = call("GET", f"/api/v2/components/{fp_lib_uuid}")
        fp = meta_j.get("result") or {}
    if not fp:
        return {"ok": False, "error": "GET library footprint failed", "http": st, "raw": meta_j}
    ticket = int(fp.get("ticket") or 0)
    now = int(time.time() * 1000)
    title = fp.get("title") or "cuav_x25_mega_colored"
    display = fp.get("display_title") or "CUAV_X25_MEGA_colored"

    attempts = [
        (
            "update",
            f"/api/v2/components/{fp_lib_uuid}/update",
            {
                "uuid": fp_lib_uuid,
                "title": title,
                "display_title": display,
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
            f"/api/v2/components/{fp_lib_uuid}/update_canvas",
            {
                "uuid": fp_lib_uuid,
                "dataStr": data_str,
                "ticket": ticket + 1,
                "updateTime": now,
            },
        ),
        (
            "upload",
            "/api/v2/components/upload",
            {
                "uuid": fp_lib_uuid,
                "title": title,
                "display_title": display,
                "description": "",
                "docType": 4,
                "dataStr": data_str,
                "ticket": ticket + 1,
                "updateTime": now,
                "public": True,
                "type": 3,
                "path": C.LCEDA_LIB_PATH,
            },
        ),
    ]

    results = []
    succeeded = None
    for name, path, body in attempts:
        st, resp = call("POST", path, body)
        entry = {
            "method": name,
            "http": st,
            "success": bool(resp.get("success")),
            "code": resp.get("code"),
            "message": resp.get("message") or resp.get("msg"),
        }
        results.append(entry)
        C.ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
        (C.ANALYSIS_DIR / f"upload_{name}_resp.json").write_text(
            json.dumps(resp, ensure_ascii=False, indent=2)[:100000], encoding="utf-8"
        )
        if resp.get("success"):
            succeeded = name
            break

    verify = fp_status(fp_lib_uuid)
    return {
        "ok": succeeded is not None and bool(verify.get("ready_for_pcb")),
        "succeeded_via": succeeded,
        "attempts": results,
        "extracted": {k: extracted[k] for k in extracted if k != "dataStr"},
        "verify": verify,
    }


def bind_device(
    dev_uuid: str = C.DEV_LIB,
    fp_uuid: str = C.FP_LIB,
    symbol_uuid: str = C.SYM_LIB,
    convert_to_pcb: bool = True,
) -> dict[str, Any]:
    st, j = call("GET", f"/api/devices/{dev_uuid}")
    res = j.get("result") or {}
    if not res:
        return {"ok": False, "error": "device GET failed", "http": st, "raw": j}
    attrs = dict(res.get("attributes") or {})
    attrs["Footprint"] = fp_uuid
    attrs["Symbol"] = symbol_uuid or attrs.get("Symbol") or C.SYM_LIB
    if convert_to_pcb:
        attrs["Convert to PCB"] = "yes"
    attrs.pop("Device", None)

    body = {
        "uuid": dev_uuid,
        "title": res.get("title") or "cuav_x25_mega_colored",
        "display_title": res.get("display_title") or "CUAV_X25_MEGA_colored",
        "description": res.get("description") or "",
        "attributes": attrs,
        "ticket": int(res.get("ticket") or 0) + 1,
        "updateTime": int(time.time()),
        "images": res.get("images") or [""],
    }

    attempts = []
    succeeded = None
    for path in (f"/api/devices/{dev_uuid}", "/api/devices/upload"):
        st, resp = call("POST", path, body)
        entry = {
            "path": path,
            "http": st,
            "success": bool(resp.get("success")),
            "message": resp.get("message") or resp.get("code"),
        }
        attempts.append(entry)
        if resp.get("success"):
            succeeded = path
            break

    after = device_status(dev_uuid)
    return {
        "ok": succeeded is not None and after.get("footprint_ok", False),
        "succeeded_via": succeeded,
        "attempts": attempts,
        "after": after,
    }


def x25_pipeline(include_cloud: bool = True) -> dict[str, Any]:
    """Local fix pads + bind, then optional cloud upload + device bind."""
    steps: dict[str, Any] = {}
    steps["fix_pads"] = epru.fix_pads()
    steps["bind"] = epru.fix_bind()
    steps["local_status"] = epru.project_status(str(C.FIXED_EPRU))
    if include_cloud:
        steps["cloud_upload_fp"] = upload_fp()
        steps["cloud_bind_device"] = bind_device()
        steps["cloud_fp_status"] = fp_status()
    ok = bool(steps["local_status"].get("can_convert_x25_to_pcb"))
    if include_cloud:
        ok = ok and bool(steps.get("cloud_upload_fp", {}).get("ok")) and bool(
            steps.get("cloud_bind_device", {}).get("ok")
        )
    return {"ok": ok, "steps": steps}
