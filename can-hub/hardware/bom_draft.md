# Design-Level BOM (Draft)

8-port isolated CAN hub — component counts for schematic capture. Part numbers and vendors TBD at layout.

| Function | Part / block | Qty | Notes |
|----------|--------------|-----|-------|
| MCU | STM32G474 (industrial temp) | 1 | 3× FDCAN; package per PCB (e.g. LQFP100) |
| SPI CAN controller | MCP2518FD | 5 | Shared SPI bus; independent CS + INT each |
| Isolated CAN transceiver | ADM3055E | 8 | −40~105 °C; isoPower per device |
| Input power | 9–36 V → 5 V DCDC | 1 | Wide-input buck; size for 8× isoPower + MCU + 5×2518 |
| Logic rail | 3.3 V LDO or DCDC | 1 | From 5V_SYS for MCU and MCP2518FD |
| Per-port protection | CAN TVS (bus side) | 8 | One per ADM3055E CANH/CANL pair |
| Per-port termination | Switchable 120 Ω | 8 | Jumper or DIP per port; short-stub rules for dual-ESC branches |

## Power tree (reference)

```
VIN 9–36 V ──► reverse-polarity / TVS / EMI ──► DCDC ──► 5V_SYS ──► 3V3
                                                      └──► ADM3055E logic (×8, common 5 V)
```

## Per-port blocks (×8)

Each port: **ADM3055E** → CAN connector; **TVS** on bus; **120 Ω** termination (switchable).

| Silk | Role |
|------|------|
| CAN_FC | Flight controller CAN1 |
| CAN_M1 … CAN_M6 | Motor axes 1–6 (dual ESC per port) |
| CAN_X | Spare / bench debug |
