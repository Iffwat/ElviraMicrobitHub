# MicrobitHub

[![CI](https://github.com/Iffwat/ElviraMicrobitHub/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Iffwat/ElviraMicrobitHub/actions/workflows/ci.yml)

Python dashboard for controlling and monitoring a micro:bit + Cytron Motion:bit robot
over Bluetooth or USB. Inspired by MakerLink.

**Status:** Phases 0–2 complete: core, simulator and the dashboard GUI. Run the app, pick
**Simulator** and press **Connect** to drive the simulated robot. USB and Bluetooth come in phases 4 and 5.

## Quick start

```powershell
cd C:\Users\USER\Microbithub
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

python -m microbithub          # open the GUI (Simulator → Connect)
python -m microbithub --demo   # console demo against the simulated robot
pytest                         # run the test suite
```

## Documentation

See [`docs/`](docs/README.md): the project plan, one page per phase, and [CI/CD](docs/devops.md).
