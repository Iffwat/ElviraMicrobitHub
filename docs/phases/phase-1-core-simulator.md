# Phase 1 — Core + Simulator

**Status:** ✅ Done — 67 tests passing

The core is pure Python with no external dependencies. It has no GUI code and
can be tested on its own. The GUI (phase 2) and the real transports (phases
4 and 5) are built on top of it.

## Run it

```powershell
.\.venv\Scripts\Activate.ps1
python -m microbithub              # console demo against the simulated robot
python -m microbithub --seconds 10
pytest                             # run the tests
```

## Modules

| File | Purpose |
|------|---------|
| `core/model.py` | `CardType`, `Card` (value, limits, label), coercion and clamping |
| `core/protocol.py` | Message dataclasses, `encode()` / `decode()`, checksum, text escaping |
| `core/events.py` | Small `Signal` class (connect / emit). The core does not depend on Qt. |
| `core/session.py` | `DeviceSession`: handshake, sync, heartbeat, ACK + retry, E-stop, link monitoring |
| `transport/base.py` | Abstract `Transport` and `LineBuffer` (joins chunks into lines, UTF-8 safe) |
| `transport/sim.py` | `SimTransport`: a fake robot that behaves like the planned firmware |
| `__main__.py` | Console demo |

```
DeviceSession ──send_line()──► Transport ──► (micro:bit / simulator)
      ▲                            │
      └──────── on_line() ◄────────┘
```

## Protocol v2 (as implemented)

Line format: `<TYPE>[:<payload>][*<checksum>]`, ending with `\n`.

- **Checksum:** XOR of the UTF-8 bytes before `*`, as 2 hex digits. Optional when
  receiving. The PC always adds it to `SET`, `ESTOP` and `RESUME`. A wrong checksum
  rejects the line.
- **Escaping:** text fields (text values, labels, log text, NAK reasons, event
  names) encode `%`→`%25`, `*`→`%2A`, `,`→`%2C`, LF→`%0A`, CR→`%0D`.
  Decoding only replaces those five sequences, so a plain `50%` sent by firmware
  still arrives as `50%`.
- **Card IDs:** a letter followed by up to 15 letters, digits or `_` (e.g. `M1`, `S8`, `LIGHT_1`).
- **Values:** whole numbers become `int`; everything else is text.

### PC → micro:bit
| Message | Example | Meaning |
|---------|---------|---------|
| HELLO | `HELLO:2` | Start of a session, protocol version |
| SYNC | `SYNC` | Ask for all card definitions |
| HB | `HB:17` | Heartbeat (every 250 ms by default) |
| SET | `SET:M1:-200*21` | Set a card value |
| ESTOP | `ESTOP*5D` | Stop all motors until RESUME |
| RESUME | `RESUME*19` | Clear the E-stop |

### micro:bit → PC
| Message | Example | Meaning |
|---------|---------|---------|
| HELLO | `HELLO:2,MicrobitHub,1.0.0` | Handshake reply |
| CARD | `CARD:S1,SERVO,90,20,160,Gripper` | Card: id, type, start, min, max, label (fields may be empty; label may be in `"quotes"`) |
| SYNCED | `SYNCED:9` | All cards sent (**new**, not in the original plan) |
| VAL | `VAL:A1:512` | Value update |
| ACK / NAK | `ACK:M1` / `NAK:M1,ESTOP` | Confirms or rejects a SET |
| HB | `HB:17` | Heartbeat echo, used to measure latency |
| LOG | `LOG:Robot ready` | Line for the terminal |
| EVT | `EVT:WATCHDOG` | `ESTOP`, `RESUME`, `WATCHDOG`, ... |

NAK reasons used by the simulator: `UNKNOWN`, `READ_ONLY`, `ESTOP`, `BAD_VALUE`.

### Card types
`MOTOR` (-255..255), `SERVO` (0..180), `ANALOG_IN` / `ANALOG_OUT` / `GAUGE` (0..1023),
`DIGITAL_IN` / `DIGITAL_OUT` / `BUTTON` (0..1), `TEXT_IN`, `TEXT_OUT`,
`SOUND` (value such as `PLAY:SIREN:LOOP` or `STOP`), `JOYSTICK` (text `"x,y"`),
`SENSOR_BUILTIN`.

Writable from the PC: MOTOR, SERVO, ANALOG_OUT, DIGITAL_OUT, BUTTON, TEXT_OUT, JOYSTICK.

## DeviceSession behaviour

| Feature | Details |
|---------|---------|
| Connect | `connect()` moves through CONNECTING → HANDSHAKE → SYNCING → READY. It times out if there is no HELLO reply (3 s) or no SYNCED (5 s), and checks the protocol version. |
| Set value | `await set_value(id, v)` clamps the value to the card limits, updates the local value immediately and waits for ACK (0.3 s, 2 retries). It returns `False` on NAK, on timeout, or if a newer value for the same card replaced it. It raises an error for unknown or read-only cards. |
| Fire-and-forget | `set_value(..., wait_ack=False)` for fast slider streams |
| Heartbeat | `HB:n` every 250 ms; the round-trip time goes to `latency_ms` |
| Link monitor | `link_lost` fires after 1.5 s of silence; `link_restored` fires when data arrives again |
| E-stop | `estop()` / `resume()`; `session.estopped` follows the device's `EVT` messages |
| Disconnect | Deliberate: `disconnect()`. If the link drops unexpectedly, the session emits `error("Connection lost")` and moves to DISCONNECTED. |

Signals: `state_changed`, `cards_cleared`, `card_added`, `value_changed`,
`log_received`, `event_received`, `latency_updated`, `link_lost`,
`link_restored`, `error`.

## Simulator

`SimTransport` acts as the reference for the phase 3 firmware:

- 9 demo cards (`demo_cards()`): 2 motors, a gripper servo (limited to 20..160), a
  light sensor, a bumper, a headlight, text in/out and an alarm sound
- **Watchdog:** after the first heartbeat, 1 s without `HB` sets the motors to 0 and sends `EVT:WATCHDOG`
- **E-stop:** motors go to 0; a motor `SET` gets `NAK:..,ESTOP` plus a `VAL` to correct the PC's value
- **Limits:** values are clamped; if the stored value differs from the request, a `VAL` is sent back
- **Streaming:** 20 Hz, changes only, with a deadband of 5 for analog values
- **Animation:** sine-wave light sensor, bumper toggling every 1.5 s, uptime text,
  and a chime on each bumper press
- **Test hooks:** `latency`, `drop_incoming`, `received`, `set_sensor()`,
  `simulate_disconnect()`, `animate=False`

## Tests

| File | Covers |
|------|--------|
| `tests/test_protocol.py` | Round-trip for every message, checksum, escaping, invalid input |
| `tests/test_model.py` | Default ranges, clamping, coercion |
| `tests/test_transport_base.py` | Line framing across chunks, CRLF, split UTF-8 characters |
| `tests/test_session.py` | Handshake, ACK, clamping, E-stop, watchdog, retries, streaming, disconnect, reconnect |

## Changes from the plan
- Added the `SYNCED:<count>` message, so the PC knows when sync is complete.
- Added escaping for text fields.
- `events.py` is a pure-Python `Signal` class; the Qt bridge comes in phase 2.
- Runtime dependencies are empty for now; `pydantic` will be added with profiles (phase 6).
