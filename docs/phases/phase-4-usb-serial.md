# Phase 4 — USB Serial Transport

**Status:** ⏳ Coming soon

## Planned scope
- `transport/serial.py` using `pyserial-asyncio`, at 115200 baud
- Auto-detect the micro:bit COM port (USB VID `0x0D28`)
- Reuse `LineBuffer` for framing
- Report an unexpected unplug through `_emit_disconnect()`

## Done when
The real robot can be controlled from the GUI over a USB cable.
