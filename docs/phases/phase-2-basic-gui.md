# Phase 2 — Basic GUI

**Status:** ⏳ Coming soon

## Planned scope
- Build on the phase 0 shell (`app.py` with qasync, `gui/main_window.py`)
- Connection bar: transport picker (Sim for now), Connect button, latency display, **E-Stop** (Space key)
- Card grid built automatically from the cards the device declares
- Card widgets: Motor, Servo, Analog (live pyqtgraph chart), Digital, Button, Text in/out, Sound
- Terminal panel for `LOG` lines, events and errors
- A bridge from the core `Signal` class to Qt signals

## Done when
All card types work against `SimTransport`.

See [PLAN.md](../PLAN.md) §6 for the GUI layout.
