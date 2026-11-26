# DevOps Overview

MicrobitHub uses **GitHub Actions** for CI/CD. This page is the overview; details are in:

| Document | Covers |
|----------|--------|
| [ci.md](ci.md) | **Continuous Integration**: lint, tests, dev builds, troubleshooting, branch protection |
| [cd.md](cd.md) | **Continuous Delivery**: dev builds, versioning, how to release, pre-releases, fixing a bad release, Dependabot |

## The pipeline

```
 feature branch ──push──► CI: lint + tests (Windows & Linux, Py 3.12 & 3.13)
        │
        └─ Pull Request ─► CI + Windows exe dev build (artifact, 14 days)
                │  merge when green
                ▼
              main ──push──► CI + exe dev build
                │
                └─ tag vX.Y.Z ──► Release: CI → version check → build exe
                                   → smoke test → GitHub Release (.exe + .sha256)
```

## Files

| File | Purpose |
|------|---------|
| `.github/workflows/ci.yml` | CI: lint, test matrix, exe dev build |
| `.github/workflows/release.yml` | CD: GitHub Release when a version tag is pushed |
| `.github/dependabot.yml` | Weekly dependency update PRs |
| `.github/pull_request_template.md` | PR checklist |
| `packaging/build.ps1` | Builds and smoke-tests `dist\MicrobitHub.exe` (local + CI) |
| `packaging/run_microbithub.py` | PyInstaller entry script |
| `pyproject.toml` | Dependencies, ruff rules, pytest and coverage settings |
| `src/microbithub/__init__.py` | `__version__`, the only place the version is set |

## Cheat sheet

```powershell
# before pushing (same checks as CI)
ruff check . ; ruff format . ; pytest --cov

# build the exe locally
.\packaging\build.ps1

# release (after bumping __version__ and merging to main)
git tag -a v0.2.0 -m "MicrobitHub 0.2.0"
git push origin v0.2.0
```
