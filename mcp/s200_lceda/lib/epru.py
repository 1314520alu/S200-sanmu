"""Local .epru scan / pad inject / footprint bind."""
from __future__ import annotations

import json
import re
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import constants as C


def dumps(o: dict) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def find_json_object_end(s: str, start: int) -> int:
    depth = 0
    in_str = False
    esc = False
    for j in range(start, len(s)):
        ch = s[j]
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
                return j + 1
    raise ValueError("unclosed json")


def resolve_epru(path: str | None = None) -> Path:
    if path:
        p = Path(path)
        if not p.is_absolute():
            p = C.ROOT / p
        return p
    if C.FIXED_EPRU.exists():
        return C.FIXED_EPRU
    return C.BACKUP_EPRU


def footprint_region(raw: str, uuid: str) -> tuple[int, int, dict] | None:
    marker = f'"uuid":"{uuid}"'
    pos = raw.find(marker)
    if pos < 0:
        return None
    head_start = raw.rfind("{", 0, pos)
    head_end = find_json_object_end(raw, head_start)
    head = json.loads(raw[head_start:head_end])
    if head.get("docType") != "FOOTPRINT":
        return None
    next_doc = raw.find('{"type":"DOCHEAD"}', head_end)
    region_end = next_doc if next_doc > 0 else len(raw)
    return head_start, region_end, head


def extract_pads(region: str) -> list[dict[str, Any]]:
    pads: list[dict[str, Any]] = []
    for m in re.finditer(r'\{"type":"PAD","ticket":\d+,"id":"[^"]+"\}\|\|(\{.*?\})(?=\|\n|\|$)', region, re.S):
        try:
            pads.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    if pads:
        return pads
    # fallback: looser payload scan
    for m in re.finditer(r'"type":"PAD".{0,40}\|\|(\{[^|]+?\})\|', region):
        try:
            obj = json.loads(m.group(1))
            if "centerX" in obj or "num" in obj:
                pads.append(obj)
        except json.JSONDecodeError:
            continue
    return pads


def mill_to_mm(v: float) -> float:
    return round(v / C.MM, 4)


@dataclass
class FootprintPadReport:
    uuid: str
    found: bool
    pad_count: int
    pads_mm: list[dict[str, Any]]
    matches_expected: bool
    issues: list[str]


def check_footprint_pads(raw: str, uuid: str) -> FootprintPadReport:
    region_info = footprint_region(raw, uuid)
    if not region_info:
        return FootprintPadReport(uuid, False, 0, [], False, ["footprint not found in epru"])
    start, end, _ = region_info
    region = raw[start:end]
    pads = extract_pads(region)
    pads_mm = []
    issues: list[str] = []
    for p in pads:
        cx = p.get("centerX")
        cy = p.get("centerY")
        hole = (p.get("hole") or {}).get("width")
        pads_mm.append(
            {
                "num": p.get("num"),
                "x_mm": mill_to_mm(cx) if cx is not None else None,
                "y_mm": mill_to_mm(cy) if cy is not None else None,
                "hole_mm": mill_to_mm(hole) if hole is not None else None,
            }
        )
    if len(pads) == 0:
        issues.append("0 PAD — will not convert to PCB")
    elif len(pads) != 4:
        issues.append(f"expected 4 mount pads, got {len(pads)}")

    expected = {(round(x, 2), round(y, 2)) for x, y in C.EXPECTED_PAD_XY_MM}
    got = {
        (round(p["x_mm"], 2), round(p["y_mm"], 2))
        for p in pads_mm
        if p["x_mm"] is not None and p["y_mm"] is not None
    }
    matches = len(pads) >= 4 and expected.issubset(got)
    if pads and not matches:
        issues.append(f"pad XY mismatch; got={sorted(got)} expected={sorted(expected)}")
    for p in pads_mm:
        if p.get("hole_mm") is not None and abs(p["hole_mm"] - 3.2) > 0.15:
            issues.append(f"pad {p.get('num')} hole {p['hole_mm']}mm != 3.2mm")

    return FootprintPadReport(uuid, True, len(pads), pads_mm, matches and not issues, issues)


def sch_footprint_binding(raw: str) -> dict[str, Any]:
    device = C.DEVICE_UUID
    dpos = raw.find(f'"value":"{device}"')
    bound = None
    if dpos >= 0:
        window = raw[dpos : dpos + 1200]
        m = re.search(
            r'"value":(?:"([0-9a-f]+)"|null),"keyVisible":[^}]*?"key":"Footprint"',
            window,
        )
        if not m:
            m = re.search(
                r'"key":"Footprint"[^}]*?"value":(?:"([0-9a-f]+)"|null)',
                window,
            )
        if m:
            bound = m.group(1)  # None if null group
    # also search exact known snippet
    if bound is None:
        if f'"value":"{C.PRIMARY_FP_UUID}"' in raw and '"key":"Footprint"' in raw:
            # weak signal
            snip = f'"value":"{C.PRIMARY_FP_UUID}","keyVisible":false,"valueVisible":null,"key":"Footprint"'
            if snip in raw:
                bound = C.PRIMARY_FP_UUID
    return {
        "device_uuid": device,
        "footprint_uuid": bound,
        "bound": bool(bound),
        "ok_for_pcb": bound in C.FP_UUIDS if bound else False,
    }


def project_status(path: str | None = None) -> dict[str, Any]:
    epru = resolve_epru(path)
    if not epru.exists():
        return {"ok": False, "error": f"epru not found: {epru}"}
    raw = epru.read_text(encoding="utf-8", errors="replace")
    fps = [asdict(check_footprint_pads(raw, u)) for u in C.FP_UUIDS]
    binding = sch_footprint_binding(raw)
    primary = next((f for f in fps if f["uuid"] == C.PRIMARY_FP_UUID), fps[0] if fps else None)
    can_pcb = bool(binding.get("ok_for_pcb")) and bool(primary and primary["pad_count"] > 0)
    reasons = []
    if not binding.get("bound"):
        reasons.append("原理图 X25 Footprint 未绑定")
    elif not binding.get("ok_for_pcb"):
        reasons.append(f"Footprint 绑定异常: {binding.get('footprint_uuid')}")
    if primary and primary["pad_count"] == 0:
        reasons.append("封装 0 个 PAD，转 PCB 会丢 X25")
    elif primary and not primary["matches_expected"]:
        reasons.extend(primary["issues"])

    return {
        "ok": True,
        "epru": str(epru),
        "bytes": len(raw),
        "binding": binding,
        "footprints": fps,
        "can_convert_x25_to_pcb": can_pcb,
        "blockers": reasons,
        "summary": (
            "X25 可进 PCB" if can_pcb else ("；".join(reasons) if reasons else "状态未知")
        ),
    }


def pad_block(start_ticket: int = 180, z0: int = 200) -> str:
    parts: list[str] = []
    t = start_ticket
    parts.append(dumps({"type": "ELE_PLACEHOLDER", "ticket": t, "id": "x25_pad_ph"}))
    parts.append(dumps({"dataType": "PAD", "max": z0 + 10}))
    t += 1
    positions = [("1", -C.HX, C.HY), ("2", C.HX, C.HY), ("3", -C.HX, -C.HY), ("4", C.HX, -C.HY)]
    for n, (num, cx, cy) in enumerate(positions):
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
                    "hole": {"holeType": "ROUND", "width": C.HOLE, "height": C.HOLE},
                    "defaultPad": {"padType": "ELLIPSE", "width": C.PAD_OD, "height": C.PAD_OD},
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
        paired.append(f"{parts[i]}||{parts[i + 1]}")
        i += 2
    return "|\n".join(paired) + "|\n"


def inject_into_footprint(raw: str, uuid: str) -> tuple[str, str]:
    region_info = footprint_region(raw, uuid)
    if not region_info:
        return raw, f"footprint {uuid} not found"
    head_start, region_end, _ = region_info
    region = raw[head_start:region_end]
    if '"type":"PAD"' in region:
        return raw, f"footprint {uuid} already has PAD"
    meta_pat = re.compile(r'\{"type":"META","ticket":\d+,"id":"META"\}\|\|')
    metas = list(meta_pat.finditer(raw, region_info[0], region_end))
    # metas should start after head; use head_end approx
    head_end = find_json_object_end(raw, head_start)
    metas = list(meta_pat.finditer(raw, head_end, region_end))
    if not metas:
        return raw, f"no META in footprint {uuid}"
    insert_at = metas[-1].start()
    block = pad_block()
    return raw[:insert_at] + block + raw[insert_at:], f"injected 4 pads into {uuid}"


def bind_sch_footprint(raw: str, fp_uuid: str = C.PRIMARY_FP_UUID) -> tuple[str, str]:
    device = C.DEVICE_UUID
    dpos = raw.find(f'"value":"{device}"')
    old = f'"value":null,"keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"{C.SCH_COMP_PARENT}"'
    new = f'"value":"{fp_uuid}","keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"{C.SCH_COMP_PARENT}"'
    if old in raw:
        return raw.replace(old, new, 1), f"bound Footprint -> {fp_uuid} (exact snippet)"
    if dpos < 0:
        return raw, "SCH Device ref not found"
    window = raw[dpos : dpos + 800]
    m = re.search(r'("value":)null(,"keyVisible":false,"valueVisible":null,"key":"Footprint")', window)
    if m:
        abs_end = dpos + m.end(1)
        if raw[abs_end : abs_end + 4] == "null":
            raw = raw[:abs_end] + f'"{fp_uuid}"' + raw[abs_end + 4 :]
            return raw, f"bound Footprint -> {fp_uuid} (pattern)"
    # already bound?
    if f'"value":"{fp_uuid}"' in window or f'"value":"{fp_uuid}"' in raw[dpos : dpos + 1200]:
        return raw, f"already bound to {fp_uuid}"
    return raw, "failed to bind SCH Footprint"


def write_fixed(raw: str, also_online_backup: bool = True) -> dict[str, Any]:
    C.FIXED_DIR.mkdir(parents=True, exist_ok=True)
    C.FIXED_EPRU.write_text(raw, encoding="utf-8")
    outs = [str(C.FIXED_EPRU)]
    # zip sibling if pack script expects it — keep epru only; optional backup copy
    if also_online_backup and C.ONLINE_BACKUP.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dest = C.ONLINE_BACKUP / f"S200飞机_FIXED_{stamp}.epru"
        shutil.copy2(C.FIXED_EPRU, dest)
        outs.append(str(dest))
    return {"written": outs, "bytes": len(raw)}


def fix_pads(source: str | None = None, uuids: list[str] | None = None) -> dict[str, Any]:
    src = resolve_epru(source) if source else C.BACKUP_EPRU
    if not src.exists():
        return {"ok": False, "error": f"source not found: {src}"}
    raw = src.read_text(encoding="utf-8", errors="replace")
    notes = []
    for uuid in uuids or list(C.FP_UUIDS):
        raw, note = inject_into_footprint(raw, uuid)
        notes.append(note)
    written = write_fixed(raw)
    after = [asdict(check_footprint_pads(raw, u)) for u in (uuids or list(C.FP_UUIDS))]
    return {"ok": True, "source": str(src), "notes": notes, **written, "after": after}


def fix_bind(source: str | None = None, fp_uuid: str = C.PRIMARY_FP_UUID) -> dict[str, Any]:
    # Prefer fixed if exists else backup
    src = Path(source) if source else (C.FIXED_EPRU if C.FIXED_EPRU.exists() else C.BACKUP_EPRU)
    if not src.is_absolute() and source:
        src = C.ROOT / source
    if not src.exists():
        return {"ok": False, "error": f"source not found: {src}"}
    raw = src.read_text(encoding="utf-8", errors="replace")
    raw, note = bind_sch_footprint(raw, fp_uuid)
    written = write_fixed(raw)
    binding = sch_footprint_binding(raw)
    return {"ok": True, "source": str(src), "note": note, **written, "binding": binding}


def library_verify() -> dict[str, Any]:
    """Offline verify from analysis cache + local epru."""
    result: dict[str, Any] = {
        "ok": True,
        "expected": {
            "primary_fp": C.PRIMARY_FP_UUID,
            "device": C.DEVICE_UUID,
            "pad_xy_mm": list(C.EXPECTED_PAD_XY_MM),
            "hole_mm": 3.2,
        },
        "analysis_files": {},
        "epru": project_status(),
    }
    for name in ("canvas_simple.json", "canvas_full.json", "x25_fp_64c5a8ceeba634d8.json"):
        p = C.ANALYSIS_DIR / name
        if not p.exists():
            result["analysis_files"][name] = {"exists": False}
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        pad_count = text.count('"type":"PAD"')
        result["analysis_files"][name] = {
            "exists": True,
            "bytes": len(text),
            "pad_type_mentions": pad_count,
            "has_primary_fp": C.PRIMARY_FP_UUID in text,
        }
    return result
