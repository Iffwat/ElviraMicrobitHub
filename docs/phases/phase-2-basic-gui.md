# Phase 2 — Basic GUI

**Status:** ✅ Done — 115 tests passing (48 new GUI tests)

The window now connects to the simulated robot and builds a card for every
card the device declares. Every card type works against `SimTransport`.

## Run it

```powershell
.\.venv\Scripts\Activate.ps1
python -m microbithub        # pick "Simulator", press Connect
pytest                       # GUI tests run headless (QT_QPA_PLATFORM=offscreen)
```

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│ Transport [Simulator ▼] [Connect]   ● Connected 23 ms  [■ STOP]  │  connection bar
├──────────────────────────────────────────────────────────────────┤
│ cards, wrapping left → right in declaration order (scrolls)      │  card grid
├──────────────────────────────────────────────────────────────────┤
│ 09:49:56 APP Connected to MicrobitHub-Sim …          [Clear]     │  terminal
└──────────────────────────────────────────────────────────────────┘
  status bar: device name · firmware · card count            v0.1.0
```

The grid and terminal are in a splitter, so the terminal can be resized.

## Modules

| File | Purpose |
|------|---------|
| `gui/bridge.py` | `SessionBridge`: re-emits every core `Signal` of a `DeviceSession` as a Qt signal. `attach()` / `detach()` per session. |
| `gui/main_window.py` | Wires bar, grid, terminal and session together. Creates a new transport + `DeviceSession` for each Connect. Runs coroutines with `spawn()` (errors go to the terminal). |
| `gui/connection_bar.py` | Transport picker, Connect/Disconnect, status dot, latency, E-Stop / Resume button |
| `gui/card_grid.py` | `CardGrid`: one widget per card, rebuilt on each sync; a re-declared card ID replaces its widget in place |
| `gui/flow_layout.py` | Wrapping layout (port of Qt's Flow Layout example) |
| `gui/terminal.py` | Timestamped, coloured lines: `APP`, `LOG`, `EVT`, `WARN`, `ERR` (keeps the last 2000) |
| `gui/cards/base.py` | `CardWidget`: title, enable/disable, `commit()` / `stream()` sending, deferred updates while the user interacts |
| `gui/cards/slider.py` | Motor, Servo, Analog output |
| `gui/cards/analog.py` | Analog input (live pyqtgraph chart), Gauge (bar) |
| `gui/cards/digital.py` | Digital input (LED), Digital output (toggle), Button (momentary) |
| `gui/cards/text.py` | Text in, Text out, and `GenericCard` (fallback) |
| `gui/cards/sound.py` | Sound card and the `PLAY:<NAME>[:ONCE|LOOP]` / `STOP` parser |

```
DeviceSession ──core Signal──► SessionBridge ──Qt signal──► MainWindow ──► CardGrid / Terminal / Bar
      ▲                                                          │
      └──────────── spawn(session.set_value(...)) ◄── valueRequested(card_id, value, wait_ack)
```

## Cards

| Card type | Widget | Sends |
|-----------|--------|-------|
| `MOTOR` | Slider (min..max), ◀ Rev / ■ Stop / Fwd ▶ | yes |
| `SERVO` | Slider (limits from the card, e.g. 20..160), Min / Center / Max | yes |
| `ANALOG_OUT` | Slider, Off / Max | yes |
| `ANALOG_IN` | Big value + 10-second scrolling chart (double width) | — |
| `SENSOR_BUILTIN` | Same as analog input; Y axis auto-ranges (no default limits) | — |
| `GAUGE` | Big value + bar | — |
| `DIGITAL_IN` | LED + HIGH / LOW | — |
| `DIGITAL_OUT` | ON / OFF toggle | yes |
| `BUTTON` | Hold button: 1 while pressed, 0 on release | yes |
| `TEXT_IN` | Latest text (plain text, never HTML) | — |
| `TEXT_OUT` | Text box + Send (Enter also sends), max 64 characters | yes |
| `SOUND` | Shows what is playing; Mute and Stop sound | — |
| `JOYSTICK` | `GenericCard`: shows the value, accepts `x,y` typed in | yes |

### Sending values

- **Drag** a slider: values are streamed **without ACK**, at most one line per
  50 ms; the latest value is always sent.
- **Release**, keyboard arrows, mouse wheel and the card buttons send the final
  value **with ACK** (retried by the session).
- While the user drags, values from the device are held back so the slider
  does not jump; the latest one is applied on release.
- If the device refuses a value and sends a correction (`VAL`), the card
  snaps to the device's value. Example: a motor `SET` during E-stop.

### Sound
Bundled sound files arrive in phase 6. Until then every sound is the system
beep: once for `ONCE`, every second for `LOOP` until `STOP`. Every `VAL` is
treated as a command, so the same `PLAY:CHIME:ONCE` twice plays twice.

## Safety in the GUI

| What | Behaviour |
|------|-----------|
| **E-Stop button** | Always visible, red. Sends `ESTOP`; turns into a green **Resume** once the device confirms (`EVT:ESTOP`). |
| **Space key** | E-stop anywhere in the window. It never resumes. A focused text box keeps Space for typing. |
| Disconnect | Sends `SET:<motor>:0` for every running motor before disconnecting, instead of waiting for the watchdog. |
| Closing the window | Disconnects (as above) first, then closes. |
| Link lost | Status dot turns orange, "Link lost — no data", terminal warning. |
| Connection lost | Terminal error, cards stay visible with their last values but are disabled. |
| Watchdog | `EVT:WATCHDOG` is shown as a terminal warning. |

## Transports
The picker lists **Simulator** (20 ms simulated latency). *USB serial (phase 4)*
and *Bluetooth (phase 5)* are listed but greyed out. `MainWindow(transports=…)`
takes a `name → factory` map, so phases 4 and 5 only add entries.

## Tests

| File | Covers |
|------|--------|
| `tests/test_gui_cards.py` | Widget for every card type, slider throttling, deferred updates, digital/button/text/sound cards, sound parser, grid rebuild/replace, connection bar states, bridge attach/detach |
| `tests/test_gui_live.py` | Whole window against `SimTransport` on a real qasync loop: connect, controls reach the robot, sensors reach the cards, Space E-stop + NAK snap-back + resume, disconnect stops motors, lost connection + reconnect, watchdog, failed connect, close while connected |
| `tests/conftest.py` | Sets `QT_QPA_PLATFORM=offscreen` for every test |

The live tests are plain (sync) tests that each run one scenario with
`loop.run_until_complete` on a fresh `qasync.QEventLoop`, so they don't share
pytest-asyncio's loop.

## Changes from the plan
- Desktop only (PySide6), as chosen in phase 0. Open questions 2–4 in PLAN §10
  don't affect this phase.
- `JOYSTICK` uses the generic card for now; the drag pad comes with keyboard and
  gamepad drive in phase 6.
- `GAUGE` is a bar, not a dial.
- Drag-to-rearrange, rename, themes and profiles stay in phase 6.
- Space only stops; resuming always needs a click (safer).

## Tip
Headless screenshots on Windows show boxes instead of text because offscreen
Qt has no fonts. Set `QT_QPA_FONTDIR=C:/Windows/Fonts` to fix that.
