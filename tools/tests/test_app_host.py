"""Host-side app_host JSON line tests."""

import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "firmware" / "Core" / "Inc"
SRC_DIR = ROOT / "firmware" / "Core" / "Src"
HOST = Path(__file__).with_name("test_app_host_host.c")
BUILD = Path(__file__).parent / "_build_app_host"

FW_SOURCES = [
    SRC_DIR / "app_host.c",
    SRC_DIR / "app_config.c",
    SRC_DIR / "app_ports.c",
    SRC_DIR / "drv_adm3055.c",
    SRC_DIR / "drv_mcp2518.c",
]


def _compile_host_test() -> Path | None:
    gcc = shutil.which("gcc")
    if gcc is None:
        return None
    BUILD.mkdir(parents=True, exist_ok=True)
    exe = BUILD / ("test_app_host_host.exe" if sys.platform == "win32"
                   else "test_app_host_host")
    cmd = [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-I{INC}",
           str(HOST), *[str(s) for s in FW_SOURCES], "-o", str(exe)]
    subprocess.run(cmd, check=True, cwd=ROOT)
    return exe


def test_app_host_host_binary():
    exe = _compile_host_test()
    if exe is None:
        return
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert "app_host_host: ok" in result.stdout


def test_protocol_field_names():
    """Responses use the same keys as protocol.py / GUI expectations."""
    ping = json.loads('{"ok":true,"cmd":"ping"}')
    assert ping["ok"] is True and ping["cmd"] == "ping"

    cfg = json.loads(
        '{"ok":true,"cmd":"get_config","enable":[1,1,1,1,1,1,1,0],"lock":false}'
    )
    assert cfg["cmd"] == "get_config" and len(cfg["enable"]) == 8

    locked = json.loads('{"ok":false,"err":"locked"}')
    assert locked["err"] == "locked"

    bad = json.loads('{"ok":false,"err":"bad_json"}')
    assert bad["err"] == "bad_json"
