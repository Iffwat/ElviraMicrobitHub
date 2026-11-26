# Phase 0 — Setup

**Status:** ✅ Done

## What was set up

| Item | Details |
|------|---------|
| Python | 3.12.10, with a virtual environment at `.venv/` |
| Packaging | `pyproject.toml` with a `src/` layout, installed in editable mode: `pip install -e ".[dev]"` |
| Runtime dependencies | `PySide6` (6.12), `pyqtgraph` (0.14), `qasync` (0.28) |
| Dev dependencies | `pytest`, `pytest-asyncio` (`asyncio_mode = "auto"`) |
| Package skeleton | `src/microbithub/{core,transport,gui}` |
| Event loop | `app.py`: asyncio runs on top of Qt's event loop through `qasync`, so `await` works in GUI code |
| Main window | `gui/main_window.py`: title, placeholder, status bar (connection and version), File → Quit (Ctrl+Q), Help → About |
| Version control | Git 2.56, repository `origin` → GitHub, `.gitignore` |

## Commands

```powershell
.\.venv\Scripts\Activate.ps1
python -m microbithub          # open the GUI (empty window until phase 2)
python -m microbithub --demo   # console demo with the simulated robot (phase 1)
pytest                         # run all tests
```

## Tests
`tests/test_gui_smoke.py` runs headless (`QT_QPA_PLATFORM=offscreen`) and checks two things:
- the main window can be created
- the full app starts, runs an asyncio task inside the Qt loop and exits with code 0
  (it runs in a subprocess so it cannot interfere with the async tests)

## Done when ✔
`python -m microbithub` opens an empty window, and `pytest` passes (69 tests).
