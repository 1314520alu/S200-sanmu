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
