# MicrobitHub — Project Plan

A Python desktop dashboard for controlling and monitoring a micro:bit robot
(Cytron Motion:bit), inspired by **MakerLink** but rebuilt with a Python GUI and a
stronger architecture.

---

## 1. Goals

| # | Goal |
|---|------|
| G1 | Control motors, servos, pins and text from a Python GUI. Show sensor data live. |
| G2 | Work over **Bluetooth (BLE)** *and* **USB serial**, so a cable can be used when Bluetooth isn't reliable. |
| G3 | Make it **safe**: the robot stops by itself if the link drops. |
| G4 | Let the GUI build itself from what the micro:bit declares, as MakerLink does with `INIT` cards. |
| G5 | Be easy to extend and test, including a **simulator**, so the GUI can be developed without hardware. |
| G6 | Optionally allow secure remote viewing and control (a later phase). |

**Not goals for v1:** mobile app, multi-robot fleets, cloud accounts.

---

## 2. What we keep from MakerLink, and what we improve

| Area | MakerLink | MicrobitHub |
|------|-----------|-------------|
| GUI | One large HTML file. Needs Chrome or Edge. | Python desktop app (PySide6), split into modules |
| Link | BLE only | BLE (`bleak`) **+ USB serial** (`pyserial`), behind one shared interface |
| Protocol | Text lines, no version, no checks | Text lines **+ version handshake, heartbeat, acks for important commands, checksum** |
| Safety | None. Motors keep running after a disconnect. | **Watchdog on the micro:bit**: stop motors after about 1 s with no heartbeat. Emergency-stop button in the GUI. |
| Card count | Fixed (M1–4, S1–8, A1–8 …) | Same Motion:bit limits, but the protocol allows any ID |
| Data | Live chart only | Live charts **+ CSV logging, record and replay, chart export** |
| Layout | Browser localStorage | JSON "profiles" saved to disk, so layouts can be shared between students |
| Input | Mouse only | Mouse **+ keyboard shortcuts + gamepad** (for driving the robot) |
| Remote | Firebase, 4-digit room code, no login, permissions only checked in the viewer | Optional local web or MQTT bridge with a **token**, permissions **checked on the host** |
| Sounds | Played from Google URLs | Sound files bundled with the app, work offline |
| Testing | None | Unit tests for the protocol, plus a simulator device |

---

## 3. Architecture

```
┌──────────────────────── Python app (PC) ────────────────────────┐
│                                                                 │
│   GUI layer (PySide6 + pyqtgraph)                               │
│     MainWindow ─ CardGrid ─ Cards (Motor, Servo, Analog, …)     │
│     Terminal panel ─ Connection bar ─ E-Stop                     │
│            ▲  Qt signals                                        │
│            │                                                    │
│   Core layer (no GUI code; can be tested on its own)            │
│     DeviceSession ── state model (cards, values)                │
│        │  Protocol (encode / decode / checksum / acks)          │
│        │  Heartbeat + reconnect logic                           │
│        │  Logger (CSV) / Recorder                               │
│            ▲                                                    │
│   Transport layer (asyncio)                                     │
│     Transport (abstract)                                        │
│       ├─ BleTransport     (bleak, Nordic UART)                  │
│       ├─ SerialTransport  (pyserial-asyncio, USB)               │
│       └─ SimTransport     (fake robot for development)          │
└─────────────────────────────────────────────────────────────────┘
                    │ BLE UART / USB serial
┌───────────────────▼──────────── micro:bit ──────────────────────┐
│  MakeCode extension "MicrobitHub" (TypeScript, like MakerLink)  │
│    blocks: init cards, link pins↔streams, send/receive values   │
│    watchdog, heartbeat replies, servo smoothing, limits         │
│  └── Motion:bit driver (cytrontechnologies/pxt-motionbit)       │
└─────────────────────────────────────────────────────────────────┘
```

**Why the micro:bit side stays MakeCode (TypeScript):** MicroPython on the
micro:bit **does not support Bluetooth**. MakeCode does, and the Motion:bit
driver is also written for MakeCode. The micro:bit side therefore remains a
MakeCode extension. Only the PC side is Python.
(A MicroPython version that works only over USB is possible later.)

---

## 4. Technology choices

| Purpose | Library | Reason |
|---------|---------|--------|
| GUI | **PySide6** (Qt 6) | Mature, looks native on Windows, LGPL license |
| Real-time charts | **pyqtgraph** | Much faster than matplotlib for live data |
| Async with Qt | **qasync** | Runs `bleak`'s asyncio loop inside the Qt event loop |
| Bluetooth | **bleak** | Python BLE library for Windows, macOS and Linux |
| USB serial | **pyserial** + **pyserial-asyncio** | micro:bit appears as a COM port |
| Gamepad | **pygame** (joystick module only) | Simple, works across platforms |
| Config / profiles | `json` + **pydantic** | Checks layout files when they load |
| Packaging | **PyInstaller** | Builds a single `.exe` for students |
| Tests | **pytest**, **pytest-asyncio** | Protocol and session tests |

Alternative considered: **NiceGUI** gives a browser UI written in Python and makes
remote access easy, but real-time charts are weaker and it doesn't feel like a
desktop app. It is a fallback if remote access becomes the main need.

---

## 5. Protocol v2 (text lines, `\n`-terminated)

Kept human-readable, like MakerLink, so it is easy to debug in a serial monitor.

```
<TYPE>:<payload>[*<checksum>]\n
```
- `checksum` = XOR of all bytes before `*`, written as 2 hex digits. It is optional,
  but always sent by the PC for actuator commands.
- Free-text fields are escaped (`%`→`%25`, `*`→`%2A`, `,`→`%2C`, newline→`%0A`) so
  text can never be confused with a checksum or a field separator (*added in phase 1*).
  Full details: [phase-1-core-simulator.md](phases/phase-1-core-simulator.md).

### PC → micro:bit
| Message | Meaning |
|---------|---------|
| `HELLO:2` | Start of a session; protocol version 2 |
| `SYNC` | Ask for all card definitions and current values |
| `HB:<n>` | Heartbeat every 250 ms (n = sequence number) |
| `SET:M1:-200*4F` | Set a value (motor, servo, stream, text) |
| `ESTOP` | Stop all motors immediately and hold servos |
| `RESUME` | Clear the E-stop |

### micro:bit → PC
| Message | Meaning |
|---------|---------|
| `HELLO:2,MicrobitHub,<fw version>` | Reply to the handshake |
| `CARD:M1,MOTOR,0,-255,255,"Left wheel"` | Card definition (ID, type, start, min, max, label) |
| `SYNCED:<count>` | All cards sent (*added in phase 1*, so the PC knows when sync is complete) |
| `VAL:A1:512` | Value update |
| `ACK:<id>` / `NAK:<id>,<reason>` | Confirms or rejects a `SET` |
| `HB:<n>` | Heartbeat echo, used to measure latency |
| `LOG:<text>` | Line for the terminal |
| `EVT:<name>` | Events (button A pressed, E-stop triggered by the watchdog …) |

### Card types
`MOTOR`, `SERVO`, `ANALOG_IN`, `ANALOG_OUT`, `DIGITAL_IN`, `DIGITAL_OUT`,
`BUTTON` (momentary), `TEXT_IN`, `TEXT_OUT`, `SOUND`, plus new ones:
`GAUGE`, `JOYSTICK` (2-axis drive → mixes into two motors), `SENSOR_BUILTIN`
(accelerometer, compass, temperature, light level).

### Safety rules (on the micro:bit)
1. No `HB` for **1000 ms** → all motors set to 0 and `EVT:WATCHDOG` sent.
2. `ESTOP` overrides everything until `RESUME`.
3. Servo limits are enforced on the micro:bit, not just in the GUI.

---

## 6. GUI design

```
┌───────────────────────────────────────────────────────────────────┐
│ [Transport ▼ BLE|USB|Sim] [Device ▼] [Connect]  ● 23 ms   [■ STOP] │
├───────────────────────────────────────────────────────────────────┤
│ ┌─Motor M1─────┐ ┌─Servo S1─────┐ ┌─Analog A1 (chart)──────────┐  │
│ │ ◀  ■  ▶      │ │  ◜ 90° ◝     │ │  ╱╲  ╱╲╱╲                  │  │
│ │ ───●─── 120  │ │ ────●────    │ │ ╱  ╲╱      value: 512      │  │
│ └──────────────┘ └──────────────┘ └────────────────────────────┘  │
│ ┌─Digital D1───┐ ┌─Text T1──────┐ ┌─Joystick─────┐                 │
│ │  ◉ HIGH      │ │ [hello ][Send]│ │     (●)      │                 │
│ └──────────────┘ └──────────────┘ └──────────────┘                 │
├───────────────────────────────────────────────────────────────────┤
│ Terminal  > Hardware connected. 6 cards.        [Log CSV ●] [Rec] │
└───────────────────────────────────────────────────────────────────┘
```

- **Card grid:** drag to rearrange, resize, rename; switch between edit and run mode.
- **Connection bar:** transport picker, device scan list, latency shown, link quality.
- **E-Stop:** large, always visible, bound to the **Space** key.
- **Themes:** dark and light.
- **Profiles:** File → Save/Load layout (`.mhub.json`).
- **Keyboard drive:** WASD keys mapped to a joystick card. Gamepad sticks mapped the same way.

---

## 7. Project structure

```
Microbithub/
├─ .venv/                      # already created (Python 3.12)
├─ docs/
│  ├─ README.md                # documentation index
│  ├─ PLAN.md                  # this file
│  └─ phases/                  # one page per phase
├─ pyproject.toml
├─ README.md
├─ src/microbithub/
│  ├─ __main__.py              # python -m microbithub
│  ├─ app.py                   # QApplication + qasync loop
│  ├─ core/
│  │  ├─ protocol.py           # encode/decode, checksum, message types
│  │  ├─ session.py            # DeviceSession: handshake, sync, heartbeat, acks
│  │  ├─ model.py              # Card / CardType / state (pydantic)
│  │  ├─ logger.py             # CSV logging, record/replay
│  │  └─ events.py             # pure-Python Signal (Qt bridge added in phase 2)
│  ├─ transport/
│  │  ├─ base.py               # abstract Transport (connect/send/receive)
│  │  ├─ ble.py                # bleak + Nordic UART
│  │  ├─ serial.py             # pyserial-asyncio
│  │  └─ sim.py                # simulated robot
│  ├─ gui/
│  │  ├─ main_window.py
│  │  ├─ connection_bar.py
│  │  ├─ card_grid.py
│  │  ├─ terminal.py
│  │  └─ cards/                # motor.py, servo.py, analog.py, digital.py, …
│  ├─ input/gamepad.py
│  └─ assets/                  # icons, sounds (siren/chime/beep .wav)
├─ firmware/makecode/          # MakeCode extension (main.ts, pxt.json)
└─ tests/                      # test_protocol.py, test_session.py
```

---

## 8. Phases / milestones

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| **0. Setup** | venv, `pyproject.toml`, dependencies, project skeleton, pytest running | `python -m microbithub` opens an empty window |
| **1. Core + simulator** | `protocol.py`, `session.py`, `SimTransport` with tests | Tests pass; the simulator declares cards and streams fake sensor data |
| **2. Basic GUI** | Main window, card grid, Motor/Servo/Analog/Digital/Text cards, terminal | All card types work against the simulator |
| **3. Firmware v2** | MakeCode extension: protocol v2, watchdog, ESTOP, heartbeat | Flashed micro:bit responds correctly in a serial monitor |
| **4. USB serial** | `SerialTransport` | Real robot controlled over a USB cable |
| **5. Bluetooth** | `BleTransport` (bleak), device scan, auto-reconnect | Real robot controlled over BLE; unplugging stops the motors within 1 s |
| **6. Polish** | Profiles, CSV logging, record/replay, sounds, themes, keyboard and gamepad drive | Usable in a classroom demo |
| **7. Packaging** | PyInstaller `.exe`, README, block guide | Runs on a PC without Python installed |
| **8. (Optional) Remote** | Local web viewer or MQTT bridge with token auth; permissions checked on the host | A remote viewer can watch and control only the cards allowed |

Suggested order: **1 → 2 → 3 → 4 → 5**. USB comes before BLE because it is
much easier to debug. BLE is the hardest part on Windows.

---

## 9. Risks and mitigations

| Risk | Mitigation |
|------|-----------|
| Windows BLE is unreliable and pairing is confusing | Set MakeCode project to **"No Pairing Required"**; offer USB as a fallback; auto-reconnect |
| Qt and asyncio event loops conflict | Use `qasync` from the start (phase 0) |
| BLE throughput (~20-byte packets) floods with many streams | Change-only sending, a deadband for analog values, a set rate per stream (e.g. 20 Hz max) |
| micro:bit memory limits with many cards | Keep the protocol text-based but short; test with the maximum card count |
| Motion:bit motor direction differs per channel (seen in MakerLink) | Per-card "invert direction" option in the GUI profile |

---

## 10. Open questions (to decide before phase 2)

1. **Desktop only, or remote access too?** This affects PySide6 vs NiceGUI.
2. Is the hardware always **Motion:bit**, or should other boards be supported (e.g. a generic pins-only mode)?
3. Should the new firmware stay **compatible with existing MakerLink blocks** so current student projects keep working?
4. Target users: students (simple, fixed layout) or makers (fully customizable)?

---

## 11. Progress

| Phase | Status | Page |
|-------|--------|------|
| 0. Setup | **Done** | [phase-0-setup.md](phases/phase-0-setup.md) |
| 1. Core + simulator | **Done** | [phase-1-core-simulator.md](phases/phase-1-core-simulator.md) |
| 2–8 | Coming soon | see [docs/README.md](README.md) |
