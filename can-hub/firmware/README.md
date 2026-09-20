# Firmware

STM32 firmware for the DroneCAN 8-port isolated CAN hub.

Target MCU: **STM32G474VET6** (LQFP100, final package must follow the PCB).

## Port mapping

| Logical port | Backend | Physical role |
|---|---|---|
| 0 | FDCAN1 | CAN_FC |
| 1 | FDCAN2 | CAN_M1 |
| 2 | FDCAN3 | CAN_M2 |
| 3 | MCP2518FD #0 | CAN_M3 |
| 4 | MCP2518FD #1 | CAN_M4 |
| 5 | MCP2518FD #2 | CAN_M5 |
| 6 | MCP2518FD #3 | CAN_M6 |
| 7 | MCP2518FD #4 | CAN_M7 |

All links operate as Classical CAN at 1 Mbit/s. A disabled port drives its
ADM3055 SILENT and STANDBY controls high; transmit and receive calls return
without touching the CAN controller.

## CubeMX checklist

CubeMX is not available in the current development environment. Create the
`.ioc`/HAL project with these settings before loading firmware on hardware:

- MCU: STM32G474VET6 (or the exact STM32G474 package fitted to the PCB).
- Clock: configure the system clock and enable a timer/DWT-based microsecond
  delay for `app_ports_hw_delay_us()`.
- FDCAN1, FDCAN2, FDCAN3: Classical CAN, normal mode, 1 Mbit/s nominal timing,
  11/29-bit reception into RX FIFO0, TX FIFO/queue enabled, no bit-rate switch.
- SPI2: master, full duplex, mode 0 (CPOL=0, CPHA=0), 8-bit, MSB first,
  software NSS, initially at or below 10 MHz. Each MCP2518FD has an independent
  active-low CS and falling-edge interrupt input.
- MCP2518FD: 40 MHz oscillator as assumed by `app_ports.c`; change
  `MCP_OSC_HZ` if the board uses another frequency.
- USB: USB Device FS, CDC class. PA11/PA12 are reserved for USB DM/DP.
- GPIO: all MCP CS outputs idle high; MCP INT inputs with EXTI; ADM3055 SILENT
  and STANDBY outputs default high so transceivers remain passive during boot.
- Enable the FDCAN, SPI, GPIO, USB Device, and required interrupt HAL modules.
- Implement the `app_ports_hw_*` functions declared in `app_ports.h` in a board
  adapter. The SPI transfer hook must assert/deassert the selected device CS
  around one complete transfer.

Suggested FDCAN nominal timing for an 80 MHz kernel clock is prescaler 4,
20 time quanta/bit, TSEG1 15, TSEG2 4, SJW 4. Recalculate if the kernel clock
differs.

## Provisional pin table

This table is a routing proposal, not a verified PCB netlist. Validate every
alternate function and package pin in CubeMX and against the schematic before
generating code.

| Function | Provisional MCU pin(s) | Notes |
|---|---|---|
| FDCAN1 RX/TX | PD0 / PD1 | Leaves PA11/PA12 for USB |
| FDCAN2 RX/TX | PB5 / PB6 | Verify AF selection in CubeMX |
| FDCAN3 RX/TX | PB3 / PB4 | Verify AF selection in CubeMX |
| SPI2 SCK/MISO/MOSI | PB13 / PB14 / PB15 | Shared by five MCP2518FDs |
| MCP CS0..CS4 | PC0..PC4 | Active low, independent |
| MCP INT0..INT4 | PC5..PC9 | Falling-edge EXTI |
| ADM SILENT0..7 | PD2..PD9 | Active high |
| ADM STANDBY0..7 | PE0..PE7 | Active high; omit unconnected controls |
| USB FS DM/DP | PA11 / PA12 | USB Device CDC |

## Board adapter example

`app_ports.c` intentionally contains weak host-safe hooks rather than HAL type
dependencies. The CubeMX project should override them, for example:

```c
bool app_ports_hw_fdcan_send(uint8_t instance, const port_frame_t *frame)
{
    /* Select hfdcan1/2/3, fill FDCAN_TxHeaderTypeDef, then call
       HAL_FDCAN_AddMessageToTxFifoQ(). */
}

bool app_ports_hw_mcp_spi_transfer(uint8_t device, const uint8_t *tx,
                                   uint8_t *rx, uint32_t len)
{
    /* CS low; HAL_SPI_TransmitReceive(&hspi2, tx, rx, len, timeout); CS high. */
}
```

## Bench status

The required CAN_FC to CAN_M1 1 Mbit/s forwarding and disabled-M1 silence test
has not been run because no target hardware or CAN analyzer is available in
this environment. Host compilation and software tests do not replace this
bench test.
