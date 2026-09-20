# tools/hub_config_gui/protocol.py
from __future__ import annotations
import json
from typing import Any

PORT_NAMES = ["FC", "M1", "M2", "M3", "M4", "M5", "M6", "X"]


def validate_enable(enable: list[int]) -> list[int]:
    if len(enable) != 8:
        raise ValueError("enable must have length 8")
    out = [1 if int(x) else 0 for x in enable]
    out[0] = 1  # CAN_FC always on
    return out


def encode_ping() -> str:
    return json.dumps({"cmd": "ping"}, separators=(",", ":")) + "\n"


def encode_get_config() -> str:
    return json.dumps({"cmd": "get_config"}, separators=(",", ":")) + "\n"


def encode_get_status() -> str:
    return json.dumps({"cmd": "get_status"}, separators=(",", ":")) + "\n"


def encode_set_config(enable: list[int]) -> str:
    enable = validate_enable(enable)
    return json.dumps({"cmd": "set_config", "enable": enable}, separators=(",", ":")) + "\n"


def parse_line(line: str) -> dict[str, Any]:
    return json.loads(line.strip())
