"""S200 / X25 fixed identifiers and geometry."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(r"G:\soft\S200工程")
BACKUP_EPRU = ROOT / "lceda_project" / "S200飞机_backup" / "S200飞机.epru"
FIXED_DIR = ROOT / "lceda_project" / "S200飞机_fixed"
FIXED_EPRU = FIXED_DIR / "S200飞机.epru"
ANALYSIS_DIR = ROOT / "lceda_project" / "analysis"
ONLINE_BACKUP = Path(r"C:\Users\alu\Documents\LCEDA-Pro\online-projects-backup\S200飞机")

MM = 39.37008
HX = round(25.5 * MM, 4)
HY = round(26.75 * MM, 4)
HOLE = round(3.2 * MM, 4)
PAD_OD = round(6.0 * MM, 4)

EXPECTED_PAD_XY_MM = (
    (-25.5, 26.75),
    (25.5, 26.75),
    (-25.5, -26.75),
    (25.5, -26.75),
)

FP_UUIDS = ("64c5a8ceeba634d8", "4e5392818c02f692")
PRIMARY_FP_UUID = "64c5a8ceeba634d8"
DEVICE_UUID = "537727934d365244"
SCH_COMP_PARENT = "99a200c10781d133"
PROJECT_UUID = "6798d283322f489e966f8c310276b491"
FP_LIB = "f0c0c271af94472d905c395236a4c10a"
DEV_LIB = "c448d4e8f4bd4dac9bda22e039fc5058"
SYM_LIB = "8344162c58f54de596ddaf533c85ed31"
LCEDA_API_BASE = "https://pro.lceda.cn"
LCEDA_LIB_PATH = "f4d2341cf4484ec7a4e1b0e1ff4fbab1"

HUB_STATUS = Path(
    r"C:\Users\alu\AppData\Roaming\Cursor\User\globalStorage"
    r"\chengbin.jlceda-mcp-hub"
    r"\jlceda-mcp-hub-runtime-status-cursor-mcp-json-127.0.0.1-8765.json"
)
HUB_RAW_API_FLAG = Path(
    r"C:\Users\alu\AppData\Roaming\Cursor\User\globalStorage"
    r"\chengbin.jlceda-mcp-hub\cursor-mcp-json_raw_api_tools.flag"
)
HUB_HOST = "127.0.0.1"
HUB_PORT = 8765
HUB_HTTP_PORT = 7900
HUB_WS_URL = f"ws://{HUB_HOST}:{HUB_PORT}/bridge/ws"
HUB_HTTP_MCP = f"http://{HUB_HOST}:{HUB_HTTP_PORT}/mcp"

WEB_DB = Path(r"C:\Users\alu\Documents\LCEDA-Pro\database\web.db")
