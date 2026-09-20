# Hub Config GUI

Python tools for configuring the DroneCAN 8-port isolated CAN hub over a JSON Lines serial protocol.

## Setup

```bash
pip install -r requirements.txt
```

## Run GUI

```bash
python hub_config_gui/main.py
```

Or from the `tools/hub_config_gui` directory:

```bash
python main.py
```

Serial defaults: **115200** baud, 0.2 s read timeout. FC port is always enabled and cannot be unchecked in the UI.

## Tests

```bash
cd tools
python -m pytest tests/test_protocol.py -v
```
