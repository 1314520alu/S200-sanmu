# DroneCAN 八口动力隔离 Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付一台 8 口 Classic CAN 星型隔离动力 Hub（接飞控 CAN1），含固件透明路由、Flash 口使能、Python 上位机勾选配置。

**Architecture:** STM32G474 提供 3 路 FDCAN + 5×MCP2518FD；每口 ADM3055E 隔离；固件按「仅 FC↔支路」转发；USB-CDC JSON Lines 配置；上位机 Python 读写使能位图。

**Tech Stack:** STM32G474 / CubeHAL、MCP2518FD SPI、ADM3055E、Python3 + CustomTkinter + pyserial、JSON Lines 配置协议。

**Spec:** `docs/superpowers/specs/2026-09-20-dronecan-star-hub-design.md`

## Global Constraints

- Classic CAN only，默认 **1 Mbps**，全口同速
- 路由：**CAN_FC → 已使能支路**；**支路 → 仅 CAN_FC**；支路互不转发
- 口序固定：`[FC, M1, M2, M3, M4, M5, M6, X]`（长度 8）
- **CAN_FC 不可在配置中关闭**（固件拒绝 `enable[0]=0`）
- 隔离收发：**ADM3055E ×8**；供电输入 **9–36 V**
- 外扩 CAN：**MCP2518FD ×5**（禁止 MCP2515）
- 上位机一期：**Python + CustomTkinter + pyserial**
- 配置协议：**JSON Lines**，USB-CDC（115200）
- 飞行锁：锁开启时 `set_config` 返回 `{"ok":false,"err":"locked"}`
- 本期不做：外设 Hub（飞控 CAN2）、CAN FD 业务、DroneCAN 应用层解析、网页上位机

## File Structure

```
firmware/
  CMakeLists.txt                 # 或 CubeIDE 工程说明 README
  Core/Src/main.c
  Core/Src/app_router.c          # 转发核心
  Core/Inc/app_router.h
  Core/Src/app_ports.c           # 8 口抽象（FDCAN + MCP2518）
  Core/Inc/app_ports.h
  Core/Src/app_config.c          # Flash 参数 + 飞行锁
  Core/Inc/app_config.h
  Core/Src/app_host.c            # USB-CDC JSON 解析
  Core/Inc/app_host.h
  Core/Src/drv_mcp2518.c
  Core/Inc/drv_mcp2518.h
  Core/Src/drv_adm3055.c         # Silent/Standby GPIO
  Core/Inc/drv_adm3055.h
tools/
  hub_config_gui/
    main.py
    protocol.py
    requirements.txt
    README.md
  tests/
    test_protocol.py             # PC 侧协议编解码单测（无硬件）
hardware/
  README.md                      # 原理图模块清单与设计检查表
  bom_draft.md                   # 设计级 BOM
docs/superpowers/specs/2026-09-20-dronecan-star-hub-design.md
```

---

### Task 1: 仓库骨架 + 协议模块（可单测）

**Files:**
- Create: `tools/hub_config_gui/protocol.py`
- Create: `tools/hub_config_gui/requirements.txt`
- Create: `tools/tests/test_protocol.py`
- Create: `tools/hub_config_gui/README.md`
- Create: `hardware/README.md`
- Create: `firmware/README.md`

**Interfaces:**
- Produces: `PORT_NAMES: list[str]`；`encode_set_config(enable: list[int]) -> str`；`parse_line(line: str) -> dict`；`validate_enable(enable: list[int]) -> list[int]`（强制 `enable[0]==1`）

- [ ] **Step 1: 写失败单测**

创建 `tools/tests/test_protocol.py`:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "hub_config_gui"))
from protocol import encode_set_config, parse_line, validate_enable, PORT_NAMES


def test_port_names_order():
    assert PORT_NAMES == ["FC", "M1", "M2", "M3", "M4", "M5", "M6", "X"]


def test_encode_set_config():
    line = encode_set_config([1, 1, 1, 1, 1, 1, 1, 0])
    assert line.endswith("\n")
    obj = json.loads(line.strip())
    assert obj == {"cmd": "set_config", "enable": [1, 1, 1, 1, 1, 1, 1, 0]}


def test_validate_force_fc_on():
    out = validate_enable([0, 1, 0, 0, 0, 0, 0, 0])
    assert out[0] == 1


def test_parse_get_config_response():
    msg = parse_line('{"ok":true,"cmd":"get_config","enable":[1,1,1,1,1,1,1,0],"lock":false}\n')
    assert msg["ok"] is True
    assert msg["enable"][7] == 0
```

- [ ] **Step 2: 运行单测确认失败**

Run: `cd tools && python -m pytest tests/test_protocol.py -v`  
Expected: FAIL（`protocol` 未实现或 import 失败）

- [ ] **Step 3: 实现 `protocol.py`**

```python
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
```

`requirements.txt`:

```
pyserial>=3.5
customtkinter>=5.2.0
pytest>=8.0.0
```

- [ ] **Step 4: 再跑单测**

Run: `cd tools && python -m pytest tests/test_protocol.py -v`  
Expected: PASS

- [ ] **Step 5: 写 README 骨架**

`tools/hub_config_gui/README.md`：说明依赖安装、`pytest`、日后 GUI 启动命令。  
`firmware/README.md`：注明将用 STM32CubeIDE / G474。  
`hardware/README.md`：注明 8×ADM3055E、9–36V、检查表见后续任务。

- [ ] **Step 6: Commit**

```bash
git add tools hardware firmware
git commit -m "feat: add hub config protocol module and repo skeleton"
```

---

### Task 2: Python 上位机 GUI（无硬件可手测协议编码）

**Files:**
- Create: `tools/hub_config_gui/main.py`
- Modify: `tools/hub_config_gui/README.md`

**Interfaces:**
- Consumes: `protocol.encode_*` / `parse_line` / `PORT_NAMES` / `validate_enable`
- Produces: 可运行窗口；串口收发一行 JSON

- [ ] **Step 1: 实现 GUI 主程序**

`tools/hub_config_gui/main.py` 须包含：

- COM 下拉（`serial.tools.list_ports`）+ 打开/关闭，波特率 **115200**，超时 0.2s  
- 8 个勾选框，标签为 `PORT_NAMES`；**FC 勾选且 `state=disabled`**  
- 按钮：`读取配置` → 发 `get_config`；`写入保存` → 发 `set_config`；`读取状态` → 发 `get_status`；`恢复默认` → enable=`[1,1,1,1,1,1,1,0]`  
- 后台线程或 `after()` 轮询串口，按行 `parse_line`；`ok:false` 弹窗显示 `err`  
- 日志文本框追加收发行  
- 状态区：若响应含 `ports` 数组，显示每口 `tx/rx/err/fault`

最小结构示例（实现时可扩展，但命令必须走 `protocol.py`）：

```python
import customtkinter as ctk
import serial
import serial.tools.list_ports
import protocol

class HubConfigApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("DroneCAN Hub Config")
        self.ser: serial.Serial | None = None
        # build: port combo, connect btn, 8 checkboxes, action buttons, log, status

    def send_line(self, line: str) -> None:
        if not self.ser or not self.ser.is_open:
            return
        self.ser.write(line.encode("utf-8"))
        self.append_log("TX " + line.strip())

    def on_write(self) -> None:
        enable = [1] + [1 if self.vars[i].get() else 0 for i in range(1, 8)]
        self.send_line(protocol.encode_set_config(enable))
```

- [ ] **Step 2: 无硬件冒烟**

Run: `cd tools/hub_config_gui && python main.py`  
Expected: 窗口打开；未连串口时点写入不崩溃；FC 无法取消勾选。

- [ ] **Step 3: 更新 README 启动说明**

```bash
pip install -r requirements.txt
python hub_config_gui/main.py
```

- [ ] **Step 4: Commit**

```bash
git add tools/hub_config_gui
git commit -m "feat: add Python hub port-enable config GUI"
```

---

### Task 3: 固件口抽象 + 配置存储 + 路由核心

**Files:**
- Create: `firmware/Core/Inc/app_config.h`
- Create: `firmware/Core/Src/app_config.c`
- Create: `firmware/Core/Inc/app_ports.h`
- Create: `firmware/Core/Src/app_ports.c`
- Create: `firmware/Core/Inc/app_router.h`
- Create: `firmware/Core/Src/app_router.c`
- Create: `tools/tests/test_router_logic.py`

**Interfaces:**
- Produces C API（头文件签名必须一致）：

```c
// app_config.h
#include <stdint.h>
#include <stdbool.h>
#define HUB_PORT_COUNT 8
typedef struct {
    uint8_t enable[HUB_PORT_COUNT];
    uint32_t magic;
} hub_config_t;

void hub_config_init(void);
const hub_config_t *hub_config_get(void);
bool hub_config_set_enable(const uint8_t enable[HUB_PORT_COUNT], bool force_fc_on);
bool hub_config_is_locked(void);
void hub_config_set_locked(bool locked);

// app_router.h
void router_on_frame(uint8_t src_port, const uint8_t *data, uint8_t len,
                     uint32_t id, bool ide);
```

- [ ] **Step 1: Python 路由规则单测**

Create `tools/tests/test_router_logic.py`:

```python
def destinations(src: int, enable: list[int]) -> list[int]:
    assert len(enable) == 8 and enable[0] == 1
    if not enable[src]:
        return []
    if src == 0:
        return [i for i in range(1, 8) if enable[i]]
    return [0]


def test_fc_to_enabled_only():
    en = [1, 1, 0, 1, 0, 0, 0, 0]
    assert destinations(0, en) == [1, 3]


def test_branch_only_to_fc():
    en = [1, 1, 1, 1, 1, 1, 1, 1]
    assert destinations(2, en) == [0]


def test_disabled_src_drops():
    en = [1, 1, 0, 1, 0, 0, 0, 0]
    assert destinations(2, en) == []
```

Run: `cd tools && python -m pytest tests/test_router_logic.py -v`  
Expected: PASS

- [ ] **Step 2: 实现 `app_config.c` / `app_router.c`**

`hub_config_set_enable`：若 `enable[0]==0` 则强制改为 1 再保存；`locked` 时返回 false。  
Flash：一期可用 `#define HUB_CONFIG_USE_FLASH 0`（RAM 配置），接口保持不变。  
`router_on_frame`：按规则调用 `port_send`（`app_ports.c` 可先 stub）。

- [ ] **Step 3: Commit**

```bash
git add firmware tools/tests/test_router_logic.py
git commit -m "feat: add hub config and FC-centric router core"
```

---

### Task 4: MCP2518 + FDCAN 端口驱动与 ADM3055 控制

**Files:**
- Create: `firmware/Core/Inc/drv_mcp2518.h`
- Create: `firmware/Core/Src/drv_mcp2518.c`
- Create: `firmware/Core/Inc/drv_adm3055.h`
- Create: `firmware/Core/Src/drv_adm3055.c`
- Modify: `firmware/Core/Src/app_ports.c`
- Modify: `firmware/README.md`

**Interfaces:**
- `port_init_all(bitrate)`、`port_send(port, id, ide, data, len)`、`port_poll_rx(...)`  
- `adm3055_set_silent(port, silent)`、`adm3055_set_standby(port, sb)`  
- 引脚映射表写在 `firmware/README.md`

- [ ] **Step 1: CubeMX 工程**

- MCU: **STM32G474**（封装与 PCB 同步，优先 GPIO 充足封装）  
- FDCAN1/2/3 @ **1 Mbps**  
- SPI 挂 5×MCP2518：独立 CS、独立 INT  
- USB Device CDC  
- GPIO：每口 ADM3055 Silent（优先）/ Standby  

- [ ] **Step 2: MCP2518 驱动最小集**

复位、1 Mbps Classic、正常模式、发标准/扩展帧、读 RX、读错误计数。

- [ ] **Step 3: `app_ports` 映射**

| port | 后端 |
|------|------|
| 0 | FDCAN1 |
| 1 | FDCAN2 |
| 2 | FDCAN3 |
| 3–7 | MCP2518 #0–#4 |

禁用口：Silent + `port_send` 直接 return。

- [ ] **Step 4: 台架测试（至少 2 路）**

CAN_FC ↔ CAN_M1 @ 1 Mbps；禁用 M1 后不应再有转发。  
Expected: 与规格路由一致。

- [ ] **Step 5: Commit**

```bash
git add firmware
git commit -m "feat: add FDCAN/MCP2518 ports and ADM3055 silent control"
```

---

### Task 5: USB-CDC 宿主协议固件

**Files:**
- Create: `firmware/Core/Inc/app_host.h`
- Create: `firmware/Core/Src/app_host.c`
- Modify: `firmware/Core/Src/main.c`

**Interfaces:**
- 命令与 `protocol.py` 一致：`ping` / `get_config` / `set_config` / `get_status`
- 响应：`ok`, `cmd`, `enable`, `lock`, `ports[].tx|rx|err|fault`

- [ ] **Step 1: 行缓冲 JSON 解析**

单行 ≤ 256 字节；非法 JSON → `{"ok":false,"err":"bad_json"}`。  
锁定时 `set_config` → `{"ok":false,"err":"locked"}`。

- [ ] **Step 2: 与 Python GUI 联调**

Expected: 勾选与配置一致；锁定时写入提示 `locked`。

- [ ] **Step 3: Commit**

```bash
git add firmware
git commit -m "feat: add USB-CDC JSON host config interface"
```

---

### Task 6: 硬件原理图 / PCB 检查表与 BOM

**Files:**
- Create: `hardware/bom_draft.md`
- Modify: `hardware/README.md`

- [ ] **Step 1: 设计级 BOM**

`hardware/bom_draft.md`：G474×1、MCP2518FD×5、ADM3055E×8、9–36V→5V、3V3、每口 TVS/终端。

- [ ] **Step 2: 原理图检查表**

写入 `hardware/README.md`：

- [ ] 8×ADM3055E 逻辑侧共 5V，CAN 侧地不相连  
- [ ] isoPower 按 AN-0971  
- [ ] 每口 TVS + 可切换 120Ω  
- [ ] VIN 9–36V 反接/TVS/EMI  
- [ ] USB-CDC ESD  
- [ ] 丝印 CAN_FC / M1–M6 / X  
- [ ] 配置锁 GPIO  

- [ ] **Step 3: Commit**

```bash
git add hardware
git commit -m "docs: add hub hardware BOM draft and schematic checklist"
```

---

### Task 7: 集成验证清单

**Files:**
- Create: `docs/superpowers/plans/verification-checklist.md`

- [ ] **Step 1: 创建并执行可测项**

```markdown
# Hub 验证清单
- [ ] GUI ping / get_config / set_config / get_status
- [ ] FC 强制使能
- [ ] 锁开启拒绝 set_config
- [ ] FC 帧到达所有已使能口；不到未使能口
- [ ] 支路帧只到 FC
- [ ] 两支路互不串话
- [ ] 单口 fault silent 后其余口仍通
- [ ] 1 Mbps 双节点 ACK 稳定（每口抽测）
- [ ] 9V / 36V 供电边界（硬件就绪后）
- [ ] ArduPilot + 12 ESC 联调（硬件就绪后）
```

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/verification-checklist.md
git commit -m "docs: add hub integration verification checklist"
```

---

## Spec coverage（自检）

| 规格项 | 任务 |
|--------|------|
| 8 口动力 Hub / 12 ESC | Task 4、6 |
| 仅 FC↔支路 | Task 3 |
| G474+5×2518+8×ADM3055E | Task 4、6 |
| 9–36V / ADI | Task 6 |
| 上位机勾选 / 锁定 | Task 1–2、5 |
| Python 一期 | Task 2 |

## Placeholder scan

无 TBD/TODO 步骤；协议字段与规格 §6.1 一致。
