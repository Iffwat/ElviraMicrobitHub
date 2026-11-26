# DevOps: CI / CD

MicrobitHub uses **GitHub Actions**. Workflows live in `.github/workflows/`.

```
 feature branch ──push──► CI: lint + tests (Windows & Linux, Py 3.12 & 3.13)
        │
        └─ Pull Request ─► CI + Windows exe build (downloadable artifact)
                │  merge (CI must be green)
                ▼
              main ──push──► CI + exe build artifact ("dev build")
                │
                └─ tag v1.2.3 ──► Release: CI → build exe → smoke test → GitHub Release
```

## Workflows

| File | Trigger | What it does |
|------|---------|--------------|
| `ci.yml` | Push to any branch, pull requests, manual run | **lint**: `ruff check` + `ruff format --check`<br>**test**: pytest + coverage on Windows/Ubuntu × Python 3.12/3.13 (Qt runs headless)<br>**build** (PRs and `main` only): PyInstaller `MicrobitHub.exe` + smoke test, uploaded as an artifact (kept 14 days) |
| `release.yml` | Push of a tag `v*.*.*` | Runs all of CI, checks the tag matches `__version__`, builds and smoke-tests the exe, and publishes a **GitHub Release** with the `.exe`, a `.sha256` file and release notes generated from the commits. A tag with a suffix (`v0.2.0-beta.1`) becomes a pre-release. |
| `dependabot.yml` | Weekly | Opens PRs to update pip packages and GitHub Actions, with minor and patch updates grouped |

## Run the same checks locally

```powershell
.\.venv\Scripts\Activate.ps1
ruff check .              # lint   (ruff check --fix . to auto-fix)
ruff format .             # format
pytest --cov              # tests + coverage
.\packaging\build.ps1     # build dist\MicrobitHub.exe and smoke-test it
```

## How to make a release

1. Update the version in `src/microbithub/__init__.py` (the only place it is set), e.g. `__version__ = "0.2.0"`.
2. Commit and merge to `main`.
3. Tag and push:
   ```powershell
   git tag v0.2.0
   git push origin v0.2.0
   ```
4. The **Release** workflow publishes `MicrobitHub-v0.2.0-windows-x64.exe` under *Releases* on GitHub.

If the tag doesn't match `__version__`, the release fails before anything is published.

## Suggested branch workflow

- One branch per phase or feature (`phase2-gui`, `fix-ble-reconnect`, ...).
- Open a **Pull Request** into `main`. CI runs and the PR gets a test build of the `.exe`.
- Merge when CI is green.

### Recommended GitHub settings (done once, in the browser)

1. **Settings → Branches → Add branch ruleset** for `main`:
   - Require a pull request before merging
   - Require status checks to pass: `Lint (ruff)` and the `Test (...)` jobs
2. **Settings → Actions → General → Workflow permissions:** "Read repository contents" is enough. The release job asks for write access itself.
3. **Settings → Code security:** enable Dependabot alerts.

## Notes
- The status badge in the root `README.md` shows the CI result for `main`.
- The exe is not code-signed, so Windows SmartScreen may warn on first run ("More info → Run anyway"). Code signing needs a paid certificate and can be added to `release.yml` later.
- `ruff` is pinned in `pyproject.toml` so lint results stay stable; Dependabot proposes updates.
