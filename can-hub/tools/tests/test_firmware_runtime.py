"""Compile/run firmware router and runtime polling tests when a host GCC exists."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "firmware" / "Core" / "Inc"
SRC = ROOT / "firmware" / "Core" / "Src"
BUILD = Path(__file__).parent / "_build_firmware_runtime"


def _compile_and_run(name: str, sources: list[Path]) -> None:
    gcc = shutil.which("gcc")
    if gcc is None:
        arm_gcc = shutil.which("arm-none-eabi-gcc")
        if arm_gcc is None:
            arm_gcc = (
                r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi"
                r"\14.2 rel1\bin\arm-none-eabi-gcc.exe"
            )
        BUILD.mkdir(parents=True, exist_ok=True)
        for index, source in enumerate(sources):
            subprocess.run(
                [arm_gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
                 f"-I{INC}", "-c", str(source), "-o",
                 str(BUILD / f"{name}_{index}.o")],
                check=True,
                cwd=ROOT,
            )
        return
    BUILD.mkdir(parents=True, exist_ok=True)
    exe = BUILD / (f"{name}.exe" if sys.platform == "win32" else name)
    subprocess.run(
        [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror", f"-I{INC}",
         *map(str, sources), "-o", str(exe)],
        check=True,
        cwd=ROOT,
    )
    result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
    assert f"{name}: ok" in result.stdout


def test_router_firmware_binary():
    _compile_and_run(
        "router_firmware_host",
        [Path(__file__).with_name("test_router_firmware_host.c"),
         SRC / "app_router.c"],
    )


def test_runtime_poll_binary():
    _compile_and_run(
        "app_runtime_host",
        [Path(__file__).with_name("test_app_runtime_host.c"),
         SRC / "app_runtime.c"],
    )


def test_port_fault_binary():
    _compile_and_run(
        "port_fault_host",
        [Path(__file__).with_name("test_port_fault_host.c"),
         SRC / "app_ports.c", SRC / "app_config.c",
         SRC / "drv_adm3055.c", SRC / "drv_mcp2518.c"],
    )
