# PyDalyBMS - Python library for Daly BMS

PyDalyBMS is a Python library for Daly BMS.
Read information from Daly BMS via UART/485 protocol.

## Installation

```bash
pip install pydalybms
```

## Usage

Important: For work with UART, you first need push activate button on BMS. The activate button is located on UART port, and it need connect to ground on 1 second.

```python
from pydalybms import DalyBMS

bms = DalyBMS("/dev/ttyUSB0")
soc = bms.get_soc()
print(soc)
```
