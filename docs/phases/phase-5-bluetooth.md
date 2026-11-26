# Phase 5 — Bluetooth (BLE) Transport

**Status:** ⏳ Coming soon

## Planned scope
- `transport/ble.py` using `bleak` and the Nordic UART service (`6e400001-b5a3-f393-e0a9-e50e24dcca9e`)
- Device scan list in the connection bar (names starting with `BBC micro:bit`)
- Split outgoing data into 20-byte BLE writes, with a send queue
- Automatic reconnect
- MakeCode project setting: **No Pairing Required**

## Done when
The real robot can be controlled over BLE, and unplugging its power stops the motors within 1 s.
