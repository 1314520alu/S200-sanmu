"""Shared helpers: compact JSON + timing."""
from __future__ import annotations

import json
import time
from typing import Any, Callable


def dumps(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def timed(fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    t0 = time.perf_counter()
    try:
        out = fn()
    except Exception as e:
        return {"ok": False, "error": str(e), "ms": round((time.perf_counter() - t0) * 1000)}
    if not isinstance(out, dict):
        out = {"ok": True, "result": out}
    out.setdefault("ms", round((time.perf_counter() - t0) * 1000))
    return out
