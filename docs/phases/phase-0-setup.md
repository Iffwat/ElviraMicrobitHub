# Phase 0 — Setup

**Status:** 🟡 Partly done

## Done
- Python 3.12 virtual environment at `.venv/`
- `pyproject.toml` with a `src/` layout, installed in editable mode (`pip install -e ".[dev]"`)
- Package skeleton: `src/microbithub/{core,transport}`
- pytest + pytest-asyncio configured (`asyncio_mode = "auto"`)
- `.gitignore`
- Entry point: `python -m microbithub` (currently runs the console demo from phase 1)

## Deferred to phase 2
- Install the GUI dependencies (`PySide6`, `pyqtgraph`, `qasync`)
- `app.py` with the Qt + asyncio event loop (qasync)
- `python -m microbithub` opens an empty window

## Not started
- Git repository (`git` is not installed yet: `winget install Git.Git`, then `git init`)
