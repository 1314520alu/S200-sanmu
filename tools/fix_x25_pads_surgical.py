#!/usr/bin/env python3
"""Surgical patch: inject X25 pads + bind SCH Footprint without full re-serialize."""
from __future__ import annotations

import json
import re
import shutil
import time
from pathlib import Path

ROOT = Path(r"G:\soft\S200工程")
SRC = ROOT / "lceda_project" / "S200飞机_backup" / "S200飞机.epru"
OUT_DIR = ROOT / "lceda_project" / "S200飞机_fixed"
OUT_EPRU = OUT_DIR / "S200飞机.epru"
BACKUP_DIR = Path(r"C:\Users\alu\Documents\LCEDA-Pro\online-projects-backup\S200飞机")

MM = 39.37008
HX = round(25.5 * MM, 4)
HY = round(26.75 * MM, 4)
HOLE = round(3.2 * MM, 4)
PAD_OD = round(6.0 * MM, 4)

FP_UUIDS = ("64c5a8ceeba634d8", "4e5392818c02f692")


def dumps(o: dict) -> str:
    return json.dumps(o, ensure_ascii=False, separators=(",", ":"))


def pad_block(start_ticket: int, z0: int) -> str:
    parts: list[str] = []
    t = start_ticket
    parts.append(dumps({"type": "ELE_PLACEHOLDER", "ticket": t, "id": "x25_pad_ph"}))
    parts.append(dumps({"dataType": "PAD", "max": z0 + 10}))
    t += 1
    positions = [("1", -HX, HY), ("2", HX, HY), ("3", -HX, -HY), ("4", HX, -HY)]
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
    # Join as META||PAYLOAD|META||PAYLOAD...
    paired = []
    i = 0
    while i < len(parts):
        paired.append(f"{parts[i]}||{parts[i+1]}")
        i += 2
    return "|\n".join(paired) + "|\n"


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


def inject_into_footprint(raw: str, uuid: str) -> str:
    # Locate footprint doc head
    marker = f'"uuid":"{uuid}"'
    pos = raw.find(marker)
    if pos < 0:
        print(f"  footprint {uuid} not found")
        return raw
    # Ensure this is FOOTPRINT head nearby
    head_start = raw.rfind("{", 0, pos)
    head_end = find_json_object_end(raw, head_start)
    head = json.loads(raw[head_start:head_end])
    if head.get("docType") != "FOOTPRINT":
        print(f"  uuid {uuid} not FOOTPRINT, skip")
        return raw

    # Already has PAD in this doc region? Find next DOCHEAD after this head
    next_doc = raw.find('{"type":"DOCHEAD"}', head_end)
    region_end = next_doc if next_doc > 0 else len(raw)
    region = raw[head_start:region_end]
    if '"type":"PAD"' in region:
        print(f"  footprint {uuid} already has PAD")
        return raw

    # Insert before META of this footprint: look for last META before region_end
    # Pattern: {"type":"META","ticket":N,"id":"META"}||{title...}
    meta_pat = re.compile(
        r'\{"type":"META","ticket":\d+,"id":"META"\}\|\|'
    )
    metas = list(meta_pat.finditer(raw, head_end, region_end))
    if not metas:
        print(f"  no META in footprint {uuid}")
        return raw
    insert_at = metas[-1].start()

    block = pad_block(180, 200)
    print(f"  inject pads into {uuid} at {insert_at}, block_len={len(block)}")
    return raw[:insert_at] + block + raw[insert_at:]


def bind_sch_footprint(raw: str) -> str:
    """Set X25 component Footprint null -> uuid. Match by nearby Device uuid."""
    # Find the Footprint ATTR payload that belongs to X25 (Device 537727934d365244)
    # Structure nearby:
    # ..."key":"Device"..."value":"537727934d365244"...
    # ..."key":"Footprint"..."value":null...
    device = "537727934d365244"
    dpos = raw.find(f'"value":"{device}"')
    if dpos < 0:
        print("  SCH Device ref not found")
        return raw
    # Search forward a bit for Footprint null
    window = raw[dpos : dpos + 800]
    m = re.search(
        r'("key":"Footprint"[^\}]*?"value":)null',
        window,
    )
    # Footprint payload may have value before key depending on order
    if not m:
        m = re.search(
            r'("value":)null(,"keyVisible":false,"valueVisible":null,"key":"Footprint")',
            window,
        )
    if not m:
        # broader: any Footprint null near parent after device
        m = re.search(
            r'("value":)null(,"keyVisible":[^\}]*?"key":"Footprint"[^\}]*?"parentId":"99a200c10781d133")',
            raw,
        )
    if not m:
        # try exact known payload snippet from analysis
        old = '"value":null,"keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"99a200c10781d133"'
        new = '"value":"64c5a8ceeba634d8","keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"99a200c10781d133"'
        if old in raw:
            print("  SCH Footprint bound via exact snippet")
            return raw.replace(old, new, 1)
        print("  SCH Footprint null not found; dump window:")
        print(window[:500])
        return raw

    start = (dpos if m.start() < 800 else 0) + m.start(1)
    # m is relative to window when first patterns; handle carefully
    if m.re.pattern.startswith('("key"') or '"key":"Footprint"' in m.re.pattern[:30]:
        abs_start = dpos + m.start(1)
        abs_end = dpos + m.end(1)
        # group1 ends before null; null follows
        if raw[abs_end:abs_end + 4] == "null":
            raw = raw[:abs_end] + '"64c5a8ceeba634d8"' + raw[abs_end + 4 :]
            print("  SCH Footprint bound (pattern A)")
            return raw
    # fallback exact
    old = '"value":null,"keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"99a200c10781d133"'
    new = '"value":"64c5a8ceeba634d8","keyVisible":false,"valueVisible":null,"key":"Footprint","fillColor":null,"parentId":"99a200c10781d133"'
    if old in raw:
        print("  SCH Footprint bound via exact snippet")
        return raw.replace(old, new, 1)
    print("  failed to bind SCH Footprint")
    return raw


def main() -> None:
    raw = SRC.read_text(encoding="utf-8", errors="replace")
    print("src bytes", len(raw))

    for uuid in FP_UUIDS:
        raw = inject_into_footprint(raw, uuid)

    raw = bind_sch_footprint(raw)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_EPRU.write_text(raw, encoding="utf-8")
    print("wrote", OUT_EPRU, "bytes", len(raw))

    # verify
    for uuid in FP_UUIDS:
        # crude: count PAD after uuid until next DOCHEAD
        p = raw.find(f'"uuid":"{uuid}"')
        nxt = raw.find('{"type":"DOCHEAD"}', p)
        region = raw[p:nxt]
        print(uuid, "PAD metas", region.count('"type":"PAD"'))

    if '"parentId":"99a200c10781d133"' in raw:
        idx = raw.find('"parentId":"99a200c10781d133"')
        # find Footprint near it - search backwards for key Footprint
        chunk = raw[idx - 200 : idx + 50]
        print("SCH attr chunk:", chunk)

    pack_dir = OUT_DIR / "pack" / "S200飞机"
    if pack_dir.exists():
        shutil.rmtree(pack_dir)
    pack_dir.mkdir(parents=True)
    shutil.copy2(OUT_EPRU, pack_dir / "S200飞机.epru")
    (pack_dir / "使用说明.txt").write_text(
        "\n".join(
            [
                "已修复内容：",
                "1. 给 CUAV_X25_MEGA_colored 封装补了 4 个安装孔焊盘（±25.5 / ±26.75 mm，M3，孔径3.2，焊盘外径6.0）",
                "2. 原理图里 X25 的 Footprint 已绑定到封装 UUID 64c5a8ceeba634d8",
                "",
                "导入步骤：",
                "1. 打开立创EDA专业版",
                "2. 文件 → 导入 → 工程（选择本目录的 zip，或直接用 S200飞机.epru）",
                "3. 打开原理图 → 设计 → 更新 PCB / 原理图转PCB",
                "4. PCB 上应出现 X25（4个安装孔）",
                "",
                "注意：若云端工程仍是旧版，请用本修复包导入为新工程，或从备份目录恢复 FIXED zip。",
            ]
        ),
        encoding="utf-8",
    )
    zip_base = OUT_DIR / "S200飞机_fixed"
    if Path(str(zip_base) + ".zip").exists():
        Path(str(zip_base) + ".zip").unlink()
    shutil.make_archive(str(zip_base), "zip", root_dir=OUT_DIR / "pack", base_dir="S200飞机")
    print("zip", str(zip_base) + ".zip")

    if BACKUP_DIR.exists():
        dest = BACKUP_DIR / f"S200飞机_FIXED_{time.strftime('%Y-%m-%d-%H-%M-%S')}.zip"
        shutil.copy2(str(zip_base) + ".zip", dest)
        print("backup copy", dest)


if __name__ == "__main__":
    main()
