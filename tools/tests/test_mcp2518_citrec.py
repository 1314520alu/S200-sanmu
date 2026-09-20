"""Host-side CiTREC decode tests (mirrors mcp2518_decode_citrec in drv_mcp2518.c)."""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INC = ROOT / "firmware" / "Core" / "Inc"
SRC = ROOT / "firmware" / "Core" / "Src" / "drv_mcp2518.c"
HOST = Path(__file__).with_name("test_mcp2518_citrec_host.c")
BUILD = Path(__file__).parent / "_build_mcp2518_citrec"

MCP2518_CITREC_REC_MASK = 0xFF
MCP2518_CITREC_TEC_SHIFT = 8
MCP2518_CITREC_TEC_MASK = 0xFF00
# Independent MCP2518FD datasheet fixtures: RXBP=19, TXBP=20, TXBO=21.
MCP2518_CITREC_RXBP = 1 << 19
MCP2518_CITREC_TXBP = 1 << 20
MCP2518_CITREC_TXBO = 1 << 21
MCP2518_ERROR_PASSIVE_THRESHOLD = 128


def decode_citrec(citrec: int) -> tuple[int, int, bool, bool]:
    rx_errors = citrec & MCP2518_CITREC_REC_MASK
    tx_errors = (citrec & MCP2518_CITREC_TEC_MASK) >> MCP2518_CITREC_TEC_SHIFT
    error_passive = (
        tx_errors >= MCP2518_ERROR_PASSIVE_THRESHOLD
        or rx_errors >= MCP2518_ERROR_PASSIVE_THRESHOLD
        or (citrec & (MCP2518_CITREC_TXBP | MCP2518_CITREC_RXBP)) != 0
    )
    bus_off = (citrec & MCP2518_CITREC_TXBO) != 0
    return tx_errors, rx_errors, error_passive, bus_off


def test_tec_rec_decode():
    rec, tec = 42, 200
    citrec = (tec << 8) | rec
    tx_errors, rx_errors, error_passive, bus_off = decode_citrec(citrec)
    assert rx_errors == rec
    assert tx_errors == tec
    assert error_passive is True
    assert bus_off is False


def test_error_passive_from_rec():
    tx_errors, rx_errors, error_passive, bus_off = decode_citrec(128)
    assert rx_errors == 128
    assert tx_errors == 0
    assert error_passive is True
    assert bus_off is False


def test_txbp_sets_error_passive_with_zero_counters():
    tx_errors, rx_errors, error_passive, _ = decode_citrec(MCP2518_CITREC_TXBP)
    assert tx_errors == 0
    assert rx_errors == 0
    assert error_passive is True


def test_rxbp_datasheet_bit_sets_error_passive():
    _, _, error_passive, _ = decode_citrec(1 << 19)
    assert error_passive is True


def test_bus_off_from_txbo_bit():
    _, _, _, bus_off = decode_citrec(MCP2518_CITREC_TXBO)
    assert bus_off is True
    _, _, _, reserved_bit_bus_off = decode_citrec(1 << 23)
    assert reserved_bit_bus_off is False


def _compile_host_test() -> Path | None:
    gcc = shutil.which("gcc")
    if gcc is None:
        return None
    BUILD.mkdir(parents=True, exist_ok=True)
    exe = BUILD / ("test_mcp2518_citrec_host.exe" if sys.platform == "win32"
                   else "test_mcp2518_citrec_host")
    subprocess.run(
        [gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
         f"-I{INC}", str(HOST), str(SRC), "-o", str(exe)],
        check=True,
        cwd=ROOT,
    )
    return exe


def test_mcp2518_citrec_host_binary_or_syntax():
    exe = _compile_host_test()
    if exe is not None:
        result = subprocess.run([str(exe)], check=True, capture_output=True, text=True)
        assert "mcp2518_citrec_host: ok" in result.stdout
        return

    arm_gcc = shutil.which("arm-none-eabi-gcc")
    if arm_gcc is None:
        arm_gcc = r"C:\Program Files (x86)\Arm GNU Toolchain arm-none-eabi\14.2 rel1\bin\arm-none-eabi-gcc.exe"
    subprocess.run(
        [arm_gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
         f"-I{INC}", "-c", str(HOST), "-o", str(BUILD / "host.o")],
        check=True,
        cwd=ROOT,
    )
    subprocess.run(
        [arm_gcc, "-std=c11", "-Wall", "-Wextra", "-Werror",
         f"-I{INC}", "-c", str(SRC), "-o", str(BUILD / "drv.o")],
        check=True,
        cwd=ROOT,
    )
