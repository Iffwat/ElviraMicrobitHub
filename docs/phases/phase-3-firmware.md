# Phase 3 — Firmware v2 (MakeCode extension)

**Status:** ⏳ Coming soon

## Planned scope
- MakeCode extension in `firmware/makecode/` (TypeScript), depending on `pxt-motionbit`
- Blocks: initialize, declare cards, link pins to streams, send and read values
- Protocol v2 as implemented in phase 1 (HELLO, SYNC/SYNCED, HB, SET/ACK/NAK, ESTOP/RESUME)
- **Watchdog:** stop the motors after 1 s without a heartbeat
- Servo smoothing and limits enforced on the micro:bit
- The same messages over both USB serial and Bluetooth UART
- `SimTransport` (`src/microbithub/transport/sim.py`) is the reference for its behaviour

## Done when
A flashed micro:bit gives the same replies as the simulator in a serial monitor.
