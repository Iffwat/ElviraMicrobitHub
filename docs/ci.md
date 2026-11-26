# Continuous Integration (CI)

CI checks every change automatically, so problems are found before they reach `main`.

- **Workflow file:** `.github/workflows/ci.yml`
- **Runs on:** GitHub Actions (GitHub-hosted Windows and Ubuntu machines)
- **Results:** the repository's **Actions** tab, and the checks section of each Pull Request

---

## 1. When CI runs

| Trigger | When | Jobs that run |
|---------|------|---------------|
| `push` | Any push to **any branch** | lint, test |
| `pull_request` | A PR is opened or updated | lint, test, **build** |
| `push` to `main` | A merge or direct push to `main` | lint, test, **build** |
| `workflow_dispatch` | Manual: Actions → CI → *Run workflow* | lint, test (and build if run on `main`) |
| `workflow_call` | Called by `release.yml` when a version tag is pushed | lint, test |

Tag pushes do **not** trigger CI directly. The release workflow calls it instead (see [cd.md](cd.md)).

**Concurrency:** if you push again to the same branch while CI is still running,
the older run is cancelled (`cancel-in-progress: true`), so only the newest commit is checked.

**Permissions:** CI only has read access to the repository (`contents: read`).

---

## 2. Jobs

```
          ┌──────────┐
push/PR ─►│  lint    │──┐
          └──────────┘  │   (PR or main only)
          ┌──────────┐  ├──► ┌──────────────┐
          │ test ×4  │──┘    │ build (exe)  │
          └──────────┘       └──────────────┘
```

`lint` and `test` run in parallel. `build` starts only if both succeed.

### 2.1 `lint` — Lint (ruff)
| Step | Command | Fails when |
|------|---------|-----------|
| Install | `pip install -e ".[dev]"` | dependency problem |
| Lint | `ruff check --output-format=github .` | a rule is broken; errors appear as annotations on the PR's changed lines |
| Format | `ruff format --check .` | a file isn't formatted |

Rules are set in `pyproject.toml` under `[tool.ruff]`:

| Setting | Value |
|---------|-------|
| Line length | 100 |
| Target | Python 3.12 |
| Rule sets | `E`/`W` pycodestyle, `F` pyflakes, `I` import sorting, `B` bugbear, `UP` pyupgrade |

ruff is **pinned** (`ruff==…` in the `dev` extras), so a new ruff release can't suddenly fail CI.
Dependabot proposes upgrades as PRs.

### 2.2 `test` — Test (OS, Python)
A **matrix** of 4 parallel runs; `fail-fast: false` means each one finishes even if another fails:

| | Python 3.12 | Python 3.13 |
|---|---|---|
| **windows-latest** | ✔ | ✔ |
| **ubuntu-latest** | ✔ | ✔ |

| Step | Details |
|------|---------|
| Qt system libraries (Linux only) | `libegl1 libgl1 libxkbcommon0 libfontconfig1 libdbus-1-3` |
| Install | `pip install -e ".[dev]"` (pip cache keyed on `pyproject.toml`) |
| Run tests | `pytest -q --cov --cov-report=term --cov-report=xml --junitxml=test-results.xml` |
| Upload | `test-results.xml` + `coverage.xml` as artifact `test-results-<os>-py<ver>` (kept 14 days, uploaded even if tests fail) |

`QT_QPA_PLATFORM=offscreen` is set for the whole job, so Qt runs without a screen.
That lets `tests/test_gui_smoke.py` create the window and start the full app on a headless server.

**Coverage** appears in the log of the *Run tests* step (`TOTAL … %`). Measured on Windows,
it was 82% when CI was set up.

### 2.3 `build` — Build Windows exe
Runs only for **pull requests** and pushes to **`main`**, not on every feature-branch push, to save time.

| Step | Details |
|------|---------|
| Install | `pip install -e ".[build]"` (PyInstaller) |
| Build and smoke-test | `./packaging/build.ps1 -Python python` |
| Upload | `dist/MicrobitHub.exe` as artifact `MicrobitHub-dev-<commit sha>` (kept 14 days) |

`packaging/build.ps1`:
1. Runs PyInstaller: one file, no console window, entry script `packaging/run_microbithub.py`, excluding `pytest` and `tkinter`.
2. Starts the exe headless with `--quit-after 2` and requires exit code 0. This proves the
   bundled app starts, runs its Qt + asyncio loop and quits cleanly.

This is the "continuous delivery" half of the pipeline. A tester can download the exe from any PR, see [cd.md](cd.md).

---

## 3. Reading the results

| Where | What you see |
|-------|--------------|
| PR page → *Checks* | ✔ / ✖ for each job; click *Details* for the log |
| PR → *Files changed* | ruff errors shown inline on the offending lines |
| Actions → a run → *Summary* | Job graph and the **Artifacts** section (test results, exe) |
| README badge | Result of the latest CI run on `main` |

---

## 4. Run the same checks locally (before pushing)

```powershell
.\.venv\Scripts\Activate.ps1

ruff check .            # same as the lint job   (ruff check --fix .  auto-fixes)
ruff format .           # fixes formatting       (CI runs it with --check)
pytest --cov            # same as the test job
.\packaging\build.ps1   # same as the build job (about 1-2 min)
```

If all four pass locally, CI will almost always pass. The exception is Linux-specific problems.

---

## 5. Changing CI

| Task | How |
|------|-----|
| Add a test | Put `test_*.py` in `tests/`; it is picked up automatically |
| Add or remove a Python version | Edit `matrix.python` in `ci.yml` |
| Enable more lint rules | Add rule codes to `[tool.ruff.lint] select` in `pyproject.toml`, then run `ruff check --fix .` |
| New runtime dependency | Add it to `dependencies` in `pyproject.toml`. CI installs it automatically, and the pip cache refreshes because the file changed. |
| New system library on Linux | Add it to the *Install Qt system libraries* step |
| Tests needing hardware | Mark them `@pytest.mark.hardware` and skip them in CI. CI machines have no micro:bit or Bluetooth. |

---

## 6. Recommended: protect `main`

So that nothing reaches `main` without green CI:

**GitHub → Settings → Rules → Rulesets → New branch ruleset**
1. Target: `main`
2. ☑ Require a pull request before merging
3. ☑ Require status checks to pass, and add:
   `Lint (ruff)`, `Test (windows-latest, py3.12)`, `Test (windows-latest, py3.13)`,
   `Test (ubuntu-latest, py3.12)`, `Test (ubuntu-latest, py3.13)`
4. ☑ Block force pushes

(Status checks can only be selected after CI has run at least once.)

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| `ruff format --check` fails: *Would reformat: …* | Run `ruff format .` locally and commit |
| `ruff check` fails with an `I001` import order error | `ruff check --fix .` |
| Linux test: *qt.qpa.plugin: Could not load the Qt platform plugin* | A system library is missing. Find it in the log (`libxcb…`, `libEGL…`) and add it to the apt step. |
| Linux test crashes with *Aborted (core dumped)* in the GUI test | Same as above; or check `QT_QPA_PLATFORM=offscreen` is set |
| A session test fails only sometimes | The timing in async tests is too tight for a slow CI machine. Increase the timeout in `wait_until(...)` instead of adding `sleep`. |
| `build` job: *PyInstaller failed* | Run `.\packaging\build.ps1` locally to reproduce. A new import may need `--hidden-import`. |
| `build` job: *Smoke test failed: exit code 1* | The exe crashes at startup. Run `dist\MicrobitHub.exe` locally to see the error. |
| Install step is slow or fails after changing dependencies | Normal for the first run with a new cache key; check the version constraints in `pyproject.toml` |
| CI didn't run at all | Check the Actions tab is enabled (Settings → Actions → General) and the workflow file is on the branch you pushed |
