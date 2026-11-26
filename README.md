# MicrobitHub

[![CI](https://github.com/Iffwat/ElviraMicrobitHub/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Iffwat/ElviraMicrobitHub/actions/workflows/ci.yml)

Python dashboard for controlling and monitoring a micro:bit + Cytron Motion:bit robot
over Bluetooth or USB. Inspired by MakerLink.

**Status:** Phase 0 (setup) and phase 1 (core + simulator) complete. The GUI window is an empty shell until phase 2.

## Quick start

```powershell
cd C:\Users\USER\Microbithub
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

python -m microbithub          # open the GUI
python -m microbithub --demo   # console demo against the simulated robot
pytest                         # run the test suite
```

## Documentation

See [`docs/`](docs/README.md): the project plan, one page per phase, and [CI/CD](docs/devops.md).
