# Task 4 Report

## Status

**DONE_WITH_CONCERNS**

The MCP2518FD register-level driver, ADM3055 GPIO driver, and eight-port
FDCAN/MCP mapping are implemented. The firmware is host-compilable without HAL;
CubeMX-generated board code must override the documented `app_ports_hw_*`
hooks.

## Implemented

- Added MCP2518FD RESET/READ/WRITE SPI operations, 1 Mbit/s Classical CAN
  timing, RX/TX FIFO setup, accept-all filter, standard/extended TX/RX, and
  TEC/REC/error-state reads.
- Added active-high ADM3055 SILENT/STANDBY control with board GPIO callbacks.
- Mapped ports 0..2 to FDCAN1..3 and ports 3..7 to MCP2518FD devices 0..4.
- Disabled ports are switched to SILENT/STANDBY and return before controller
  transmit/receive access; configuration changes apply GPIO state immediately.
- Added CubeMX setup guidance, HAL integration hooks, FDCAN timing guidance,
  and a provisional pin table to `firmware/README.md`.

## Verification

- ARM GNU C 14.2 syntax build with `-std=c11 -Wall -Wextra -Werror`: PASS.
- `python -m pytest tools/tests -q`: PASS (7 tests).
- `git diff --check`: PASS.

## Concerns / skipped work

- CubeMX generation was unavailable; no `.ioc` or generated HAL project was
  produced. The provisional pins require schematic/package/alternate-function
  validation.
- The CAN_FC ↔ CAN_M1 1 Mbit/s bench test and disabled-M1 silence check were
  skipped because target hardware and a CAN analyzer were unavailable. No
  hardware result is claimed.

## Review fix (CiTREC decode)

**Status:** FIXED

- Corrected CiTREC field decode: `[7:0]` → REC (`rx_errors`), `[15:8]` → TEC
  (`tx_errors`); TEC/REC were previously swapped.
- `error_passive` now derives from TEC/REC ≥ 128 and/or CiTREC status bits
  TXBP (bit 20) and RXBP (bit 21); no longer uses TXBP alone as the sole flag.
- `bus_off` uses CiTREC TXBO (bit 22) and RXBO (bit 23) instead of mis-mapped
  bit 21.
- Added `mcp2518_decode_citrec()` plus host tests in
  `tools/tests/test_mcp2518_citrec.py` and `test_mcp2518_citrec_host.c`.

### Verification (review fix)

- `python -m pytest tools/tests/test_mcp2518_citrec.py -v`: **5 passed**
  (Python decode assertions + ARM GNU C 14.2 syntax compile of host test).
- `python -m pytest tools/tests -q`: **12 passed** (full suite).
