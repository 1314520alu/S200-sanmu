# Hardware

8-port isolated CAN hub for large UAVs.

- **MCU:** STM32G474 (3× FDCAN + SPI for 5× MCP2518FD)
- **Transceivers:** 8× ADM3055E (isolated CAN)
- **Input power:** 9–36 V DC → 5 V → 3.3 V
- **BOM:** see [bom_draft.md](bom_draft.md)
- **原理图绘制资料（对照画板）：** [schematic-guide.md](schematic-guide.md)

## Schematic checklist

Review before layout sign-off:

- [ ] 8×ADM3055E 逻辑侧共 5V，CAN 侧地不相连
- [ ] isoPower 按 AN-0971
- [ ] 每口 TVS + 可切换 120Ω
- [ ] VIN 9–36V 反接/TVS/EMI
- [ ] USB-CDC ESD
- [ ] 丝印 CAN_FC / M1–M6 / X
- [ ] 配置锁 GPIO
