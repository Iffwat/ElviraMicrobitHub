# Phase 3 — Firmware v2 (MakeCode extension)

**Status:** 🟡 Code complete. Not yet compiled with MakeCode or flashed to a micro:bit.

The micro:bit side is a MakeCode extension in `firmware/makecode/`. It speaks
protocol v2 exactly like `SimTransport`. This is checked by a shared set of
conformance scenarios that both the simulator and the firmware logic must pass.

## Files

| File | Purpose |
|------|---------|
| `firmware/makecode/pxt.json` | Extension manifest: depends on `core`, `bluetooth`, `pxt-motionbit`; asks for "No Pairing Required" |
| `firmware/makecode/protocol.ts` | Pure string helpers: checksum (UTF-8 XOR), escaping, line parsing, integer and decimal parsing |
| `firmware/makecode/hub.ts` | Device logic **without hardware calls**: cards, HELLO / SYNC / HB / SET / ESTOP / RESUME, NAK reasons, watchdog, streaming with deadband |
| `firmware/makecode/main.ts` | Blocks plus hardware binding: Motion:bit motors and servos, pins, built-in sensors, USB serial and Bluetooth UART |
| `firmware/makecode/test.ts` | Example program (the simulator's demo robot), compiled by `pxt build` |
| `firmware/makecode/README.md` | Extension help shown in MakeCode |
| `firmware/conformance/scenarios.txt` | **Golden scenarios**: input lines and the exact expected replies |
| `firmware/host/` | Node harness that runs `protocol.ts` + `hub.ts` against the scenarios with a fake clock |
| `tests/test_firmware_conformance.py` | Runs the same scenarios against `SimTransport` |

```
scenarios.txt ──► tests/test_firmware_conformance.py ──► SimTransport (Python)   ✔ 13/13
             └──► firmware/host (Node)                ──► hub.ts + protocol.ts    CI job
```

Keeping `hub.ts` free of hardware calls is what makes it testable on a PC.
`main.ts` only attaches `apply` callbacks (motor, servo target, pin write) and
the `send` function.

## Behaviour (same as the simulator)

| Feature | Details |
|---------|---------|
| Handshake | `HELLO:2` → `HELLO:2,MicrobitHub-<device name>,0.1.0` (the device name tells robots apart in a classroom) |
| Sync | `CARD:` for every card in declaration order, current value as start, then `SYNCED:<n>` |
| Set | Checksum optional. `ACK`, plus `VAL` with the stored value if it was clamped. `NAK` reasons: `UNKNOWN`, `READ_ONLY`, `ESTOP` (plus a `VAL` to correct the slider), `BAD_VALUE` |
| Text | Unescaped on arrival; `TEXT_OUT` also logs `<id> received text: …` |
| E-stop | `ESTOP`: running motors to 0 (`VAL` each), `EVT:ESTOP`; motor `SET`s refused until `RESUME`. Servos and outputs still work. |
| Watchdog | Armed by the first `HB`. 1000 ms without `HB` → motors to 0, `EVT:WATCHDOG` (once until the next `HB`) |
| Streaming | 20 Hz, changes only, after `SYNC`. Analog input and gauge use a deadband of 5. |
| Bad lines | `LOG:Rejected line: …`; device-to-PC messages sent to it: `LOG:Ignored <TAG>` |

**Firmware-only extras** (not in the simulator; they don't change any reply):
- Bluetooth disconnect → motors stop immediately, without waiting for the watchdog.
- Replies go back on the link the last line came from (USB or Bluetooth).
- Serial buffers are raised to 128 bytes (the micro:bit default of 20 truncates long lines).
- Servo smoothing: optional delay in ms per degree; limits are checked before smoothing.
- Program blocks (`run motor`, `set card value` …) update the dashboard. During
  E-stop, `run motor` keeps the motor at 0.

## Blocks

See [`firmware/makecode/README.md`](../../firmware/makecode/README.md). In short:
add motor / servo / input / output / text / sensor / gauge / sound / joystick
cards, `start MicrobitHub`, actions (run motor, set servo, set value, play
sound, log), values (card value / text, joystick x/y, E-stop active,
dashboard connected) and events (card changed, text received, emergency stop).

Compared with MakerLink:
- **Free card IDs:** card IDs are text, so any ID works, not only M1–M4, S1–S8, A1–A8, D1–D8 and T1–T4.
- **Pin linking:** a pin is linked once when the card is added, instead of calling read/write blocks in a `forever` loop.
- **Events instead of polling:** "on card changed" and "on text received" replace the read-and-clear text reporter.
- **Safety:** adds the watchdog, E-stop, ACK/NAK and checksums.

## Running the checks

```powershell
pytest tests/test_firmware_conformance.py     # simulator side (runs in normal pytest)

cd firmware/host                              # firmware side (needs Node 18+)
npm install
npm test                                      # PASS/FAIL per scenario
```

CI runs both, plus a real MakeCode compile (`firmware-makecode` job:
`pxt target microbit`, `pxt install`, `pxt build`).

## Still to do (needs Node and hardware)

1. **Compile with MakeCode:** push the branch so the `firmware-logic` and
   `firmware-makecode` CI jobs run, or install Node and run them locally. The
   code uses only the TypeScript subset MakeCode supports (no regular
   expressions, Map or exceptions), but it has not been compiled by `pxt` yet.
2. **Flash and test** in a serial monitor (115200 baud): the replies should
   match `scenarios.txt`. Then check that unplugging the dashboard stops the
   motors within about 1 second.
3. Phase 4 then connects to it from the GUI over USB.

## Known differences
- `SET:M1:4.5` rounds to 5 on the micro:bit; Python rounds halves to even (4).
  The PC always sends whole numbers, so this never happens in practice.
- Rejected-line `LOG` texts differ in wording; the scenarios only compare the
  `Rejected line:` / `Ignored` prefix.
