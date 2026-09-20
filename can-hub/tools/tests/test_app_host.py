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


def _run_firmware_host() -> subprocess.CompletedProcess[str]:
    exe = _compile_host_test()
    if exe is None:
        raise RuntimeError("gcc not available")
    return subprocess.run([str(exe)], check=True, capture_output=True, text=True)


def _parse_firmware_samples(stdout: str) -> dict[str, dict]:
    samples: dict[str, dict] = {}
    for line in stdout.splitlines():
        if not line.startswith("SAMPLE "):
            continue
        _, label, payload = line.split(" ", 2)
        samples[label] = json.loads(payload.strip())
    return samples


def test_firmware_protocol_field_names():
    """Protocol keys come from app_host.c via the host compile/run harness."""
    try:
        result = _run_firmware_host()
    except RuntimeError:
        return

    assert "app_host_host: ok" in result.stdout
    samples = _parse_firmware_samples(result.stdout)

    ping = samples["ping"]
    assert ping["ok"] is True and ping["cmd"] == "ping"

    cfg = samples["get_config"]
    assert cfg["cmd"] == "get_config" and len(cfg["enable"]) == 8

    status = samples["get_status"]
    assert status["ok"] is True and status["cmd"] == "get_status"
    assert len(status["ports"]) == 8
    for port in status["ports"]:
        assert set(port.keys()) == {"tx", "rx", "err", "fault"}

    assert samples["locked"]["err"] == "locked"
    assert samples["bad_json"]["err"] == "bad_json"
