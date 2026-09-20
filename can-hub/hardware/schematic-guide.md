# 八口动力 CAN Hub — 原理图绘制资料包

**用途：** 你在嘉立创 EDA / Altium 里画原理图时对照本文件即可，不必等我画板。  
**对应规格：** `docs/superpowers/specs/2026-09-20-dronecan-star-hub-design.md`  
**MCU 暂定：** STM32G474VET6（LQFP100）  
**日期：** 2026-09-20

---

## 0. 建议分页结构（原理图页）

| 页号 | 名称 | 内容 |
|------|------|------|
| P1 | Block / Title | 框图、版本、丝印约定 |
| P2 | Power | VIN 9–36V、DCDC、5V、3V3、保护 |
| P3 | MCU | G474、晶振、复位、BOOT、SWD、配置锁 |
| P4 | USB | USB-C/Micro、ESD、DM/DP |
| P5 | FDCAN×3 | FDCAN1/2/3 ↔ ADM3055 #0/#1/#2 |
| P6 | SPI + MCP×5 | SPI2、5×MCP2518FD、时钟 |
| P7 | ADM3055 #3–#7 | MCP 口对应隔离收发 |
| P8 | Connectors | 8×CAN 接插件、终端跳线、丝印 |

可把 P5–P7 合并为「CAN Port Sheet」用层次块 ×8。

---

## 1. 系统框图（抄到 Title 页）

```
VIN 9–36V
  │
  ├─ 反接 / 输入 TVS / EMI
  └─ Buck → 5V_SYS ──┬──→ 3V3_LDO → MCU + MCP2518
                      └──→ 8× ADM3055E.VCC / .VIO（逻辑侧共地 GND_SYS）

STM32G474
  FDCAN1 TX/RX ── ADM3055#0 ── CAN_FC   （飞控）
  FDCAN2 TX/RX ── ADM3055#1 ── CAN_M1
  FDCAN3 TX/RX ── ADM3055#2 ── CAN_M2
  SPI2 + CS0..4 + INT0..4
       MCP2518#0..4 TX/RX ── ADM3055#3..#7 ── CAN_M3..M6, CAN_X

每个 ADM3055：CAN 侧独立 GND_ISO_n（彼此不相连）
```

---

## 2. 网络命名约定

| 网络 | 说明 |
|------|------|
| `VIN` | 输入 9–36 V |
| `5V_SYS` | 板级 5 V |
| `3V3` | MCU / MCP 电源 |
| `GND_SYS` | 逻辑侧公共地 |
| `CAN_n_H` / `CAN_n_L` | 第 n 口总线（n=FC,M1…M6,X） |
| `GND_ISO_n` | 第 n 口隔离地 |
| `FDCANx_TX` / `FDCANx_RX` | MCU↔ADM（n=1..3） |
| `MCP_k_TX` / `MCP_k_RX` | MCP2518↔ADM（k=0..4） |
| `MCP_CS_k` / `MCP_INT_k` | SPI 片选 / 中断 |
| `ADM_SILENT_n` / `ADM_STBY_n` | 口使能控制（高=静默/待机） |
| `CFG_ALLOW` | 配置锁输入（高=允许改配置，接拨码） |
| `USB_DP` / `USB_DM` | PA12 / PA11 |

口索引建议与固件一致：

| n | 丝印 | 控制器 | ADM 编号 |
|---|------|--------|----------|
| 0 | CAN_FC | FDCAN1 | U_ISO0 |
| 1 | CAN_M1 | FDCAN2 | U_ISO1 |
| 2 | CAN_M2 | FDCAN3 | U_ISO2 |
| 3 | CAN_M3 | MCP#0 | U_ISO3 |
| 4 | CAN_M4 | MCP#1 | U_ISO4 |
| 5 | CAN_M5 | MCP#2 | U_ISO5 |
| 6 | CAN_M6 | MCP#3 | U_ISO6 |
| 7 | CAN_X  | MCP#4 | U_ISO7 |

---

## 3. MCU 引脚分配（画 MCU 页直接照抄）

与 `firmware/README.md` 一致，画之前在 CubeMX 再核一次 AF：

| 功能 | 引脚 | 备注 |
|------|------|------|
| FDCAN1_RX / TX | PD0 / PD1 | 飞控口 |
| FDCAN2_RX / TX | PB5 / PB6 | M1 |
| FDCAN3_RX / TX | PB3 / PB4 | M2 |
| SPI2_SCK / MISO / MOSI | PB13 / PB14 / PB15 | 五片 MCP 共用 |
| MCP_CS0..CS4 | PC0..PC4 | 默认上拉/软件拉高 |
| MCP_INT0..INT4 | PC5..PC9 | 下降沿 EXTI |
| ADM_SILENT0..7 | PD2..PD9 | 高=Silent |
| ADM_STBY0..7 | PE0..PE7 | 高=Standby；可省部分脚则 STBY 接地（常开） |
| USB_DM / DP | PA11 / PA12 | |
| SWDIO / SWCLK | PA13 / PA14 | |
| NRST | NRST | 复位键 + 电容 |
| BOOT0 | BOOT0 | 下拉 |
| HSE | PF0/PF1 或按封装 | 建议 8 MHz 或 16 MHz 晶振 |
| CFG_ALLOW | 任选空闲 GPIO，如 PE8 | 拨码：开=3V3，关=GND |

**上电默认：** 所有 `ADM_SILENT`、`ADM_STBY` 经 MCU 复位前用下拉/上拉策略保证收发器默认静默（推荐：外部弱上拉到 3V3，固件初始化后再按配置拉低打开）。

---

## 4. 电源页（P2）要点

### 4.1 输入

```
VIN+ ──► 保险丝 F1 (建议 2–3A) ──► 反接保护（理想二极管或 P-MOS）
      ──► TVS（如 SMBJ36A 或按 VIN 选）
      ──► 共模电感 + 差模电容（EMI）
      ──► Buck 模块/IC ──► 5V_SYS
```

候选宽压 Buck（任选一，以你库为准）：

- 模块：金升阳 / XP Power 一类 9–36Vin → 5Vout，≥2 A（8×isoPower 峰值要留裕量）  
- 或同步 Buck IC + 电感（需单独设计）

### 4.2 5V → 3V3

- LDO：AMS1117-3.3 偏弱；推荐 AP2112 / TLV75533 等 ≥500 mA  
- 或小 Buck 3V3

### 4.3 去耦

- 每个 IC：0.1 µF 紧贴 VCC；MCU 每组电源脚按数据手册放置 100 nF + 若干 µF  
- `5V_SYS` 总电容：≥100 µF 电解/固态 + 陶瓷

**注意：** 8 片 ADM3055 isoPower 开关噪声大，`5V_SYS` 走线加粗，靠近每片再放 10 µF。

---

## 5. ADM3055E 单口典型接法（×8 复制）

**必读官方：** [ADM3055E 产品页](https://www.analog.com/en/products/adm3055e.html) + **AN-0971**（isoPower 辐射布板）  
**评估板参考：** EVAL-ADM3055E / CN0401

### 5.1 引脚简表（20-SOIC_IC）

| 脚 | 名 | 接法 |
|----|----|------|
| 1,2,10 | GND1 | `GND_SYS` |
| 3 | VCC | `5V_SYS`；旁路 **10 µF + 0.1 µF** |
| 4 | VIO | 本设计接 **`5V_SYS`**（也可 3V3；与 TX/RX 电平一致即可；MCU 3V3 时 **VIO 建议 3V3**） |
| 5 | RXD | → MCU FDCAN_RX 或 MCP RX |
| 6 | SILENT | → `ADM_SILENT_n`（高=静默） |
| 7 | TXD | ← MCU FDCAN_TX 或 MCP TX |
| 8 | STBY | → `ADM_STBY_n`（高=待机）或接地常工作 |
| 9 | AUXIN | 可选：接 MCU 作电子终端；一期可 GND |
| 11,15 | GND2 | `GND_ISO_n` |
| 12 | RS | **短接到 GND2**（全速，1 Mbps） |
| 13 | CANL | 总线 |
| 14 | CANH | 总线 |
| 16 | VISOIN | 经磁珠 ← VISOOUT |
| 17 | AUXOUT | 可选接电子终端开关；一期 NC |
| 18,20 | GNDISO | 经磁珠 → `GND_ISO_n` |
| 19 | VISOOUT | **0.22 µF + 10 µF** 到 GNDISO；磁珠到 VISOIN |

### 5.2 电平重要决定

| 方案 | VIO | TX/RX 对接 |
|------|-----|------------|
| **A（推荐简化）** | **3V3** | 直接接 G474 / MCP2518（均为 3V3 IO） |
| B | 5V | 需要电平转换，不推荐 |

**本资料默认：VCC=5V_SYS，VIO=3V3。**

### 5.3 总线侧（每口）

```
CANH ──┬── TVS (如 PESD1CAN / ESDCAN04) ──┬── 接插件 CAN_H
       │                                  │
CANL ──┴── TVS                            └── 接插件 CAN_L
       │
       └── 跳线/拨码 JPx ── 120Ω ── 跨 CANH-CANL
GND_ISO_n ── 接插件可选引出（屏蔽地/机壳策略按整机规范）
```

**禁止：** 把 `GND_ISO_0`…`GND_ISO_7` 在 PCB 上连在一起。

### 5.4 逻辑侧到控制器

**FDCAN 口（n=0,1,2）：**

```
FDCANx_TX (MCU) ──► ADM.TXD
FDCANx_RX (MCU) ◄── ADM.RXD
```

**MCP 口（n=3..7）：**

```
MCP.TXCAN ──► ADM.TXD
MCP.RXCAN ◄── ADM.RXD
```

---

## 6. MCP2518FD ×5（P6）

**数据手册：** Microchip MCP2518FD  
**时钟：** 推荐 **40 MHz** 晶振（与现固件 `MCP_OSC_HZ` 一致）

### 6.1 每片最小连接

| MCP 脚 | 网络 |
|--------|------|
| VDD | 3V3 |
| VSS | GND_SYS |
| OSC1/OSC2 | 40 MHz 晶振 + 负载电容（按晶振手册） |
| SCK/SI/SO | SPI2 共用 |
| CS | `MCP_CS_k`（独立） |
| INT | `MCP_INT_k`（独立，可加上拉） |
| TXCAN / RXCAN | 对应 ADM3055 TXD / RXD |
| STBY | 可接 GND（常工作）或 MCU |

五片共用一组 SPI，**CS 各自独立**，不要硬件 NSS。

### 6.2 SPI 注意

- 走线尽量短、等长优先 CLK  
- 上拉 CS  
- SPI 时钟 ≤10 MHz 起步（固件可读）

---

## 7. USB 页

```
USB Connector D+/D- ── ESD (如 USBLC6-2) ── PA12/PA11
VBUS ── 可选检测分压到 GPIO；本机自供电为主，可不取电
GND ── GND_SYS
```

CDC 虚拟串口供上位机配置。

---

## 8. 接插件与丝印

每口建议 4 pin（或 JST-GH 4P，按机型统一）：

| Pin | 信号 |
|-----|------|
| 1 | CAN_H |
| 2 | CAN_L |
| 3 | GND_ISO（可选） |
| 4 | 屏蔽/NC |

丝印必须清晰：`CAN_FC`、`CAN_M1`…`CAN_M6`、`CAN_X`。

终端：每口旁标注 `TERM` + 跳线位。

---

## 9. 配置锁

```
3V3 ── 拨码 SW_CFG ── CFG_ALLOW ── MCU GPIO
                 └── 下拉 10k 到 GND（默认关=飞行锁）
```

固件：`CFG_ALLOW=1` 才允许 `set_config`。

---

## 10. 设计级 BOM（画图选料）

| 位号类 | 型号建议 | 数量 |
|--------|----------|------|
| U_MCU | STM32G474VET6 | 1 |
| U_MCP | MCP2518FD-E/SL 或同封装 | 5 |
| U_ISO | **ADM3055EBRIZ**（SOIC_IC 宽体） | 8 |
| U_PWR | 9–36V→5V ≥2A 模块/IC | 1 |
| U_3V3 | 3.3V LDO ≥0.5A | 1 |
| Y_MCP | 40 MHz | 5（或时钟缓冲共用，不推荐一期） |
| Y_MCU | 8/16 MHz HSE | 1 |
| TVS_CAN | PESD1CAN 等 | 8 |
| FB | isoPower 推荐磁珠（见 ADM 数据手册典型值） | 每片 2～3 |
| R_TERM | 120 Ω 1% | 8 |
| JP_TERM | 2.54 跳线或拨码 | 8 |
| ESD_USB | USBLC6-2SC6 | 1 |
| CON_CAN | 按机型 | 8 |
| CON_PWR | XT30 / 端子 | 1 |
| CON_USB | Type-C 或 Micro-B | 1 |

具体封装以你 EDA 库为准；隔离器件优先选 **ADM3055E** 宽体以满足爬电距离。

---

## 11. PCB / 布局硬性提醒（原理图阶段就写进备注）

1. 每个 ADM3055 **逻辑地与总线地分区**，隔离槽在芯片下方。  
2. 按 **AN-0971** 放磁珠与电容，否则辐射难过。  
3. 8 路 CAN 连接器分区放置，避免总线交叉。  
4. SPI 五从设备星型或短总线，CS 短。  
5. 动力口线束长时，终端只放在「该支路两端」（Hub 跳线 + ESC 远端）。

---

## 12. 官方参考链接（下载后对着抄）

| 文档 | 链接 |
|------|------|
| ADM3055E | https://www.analog.com/en/products/adm3055e.html |
| isoPower 布板 AN-0971 | ADI 网站搜 AN-0971 |
| EVAL-ADM3055E | ADI Evaluation boards |
| MCP2518FD | https://www.microchip.com/en-us/product/mcp2518fd |
| STM32G474 数据手册 | ST.com STM32G474 |
| 本仓库引脚表 | `firmware/README.md` |
| 本仓库 BOM 草案 | `hardware/bom_draft.md` |

---

## 13. 画图检查清单（画完自检）

- [ ] 8 个 `GND_ISO_n` 互不相连  
- [ ] VIO=3V3，VCC=5V，TX/RX 无 5V 灌入 MCU  
- [ ] RS 接地（全速）  
- [ ] 每口 TVS + 可断 120Ω  
- [ ] FDCAN×3 + MCP×5 与丝印一一对应  
- [ ] USB 占 PA11/PA12，与 FDCAN1 不冲突  
- [ ] CFG_ALLOW 拨码存在  
- [ ] 上电默认 Silent/Standby 安全  

---

你按本资料在嘉立创新建工程即可。若某页（例如只把「单口 ADM3055 层次图」画成可复制符号）需要我按网表级再拆一版文字网表，指定页号即可。
