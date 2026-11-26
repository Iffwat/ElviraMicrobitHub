# Phase 7 — Packaging

**Status:** ⏳ Coming soon (basic exe build already done, see below)

## Already done (set up together with CI/CD)
- `packaging/build.ps1` builds a single `dist\MicrobitHub.exe` (about 45 MB) with PyInstaller and smoke-tests it
- GitHub Actions builds it on every PR and push to `main`, and publishes it as a Release for `v*` tags ([devops.md](../devops.md))

## Remaining scope
- App icon and Windows version information on the exe
- README and user guide, including a MakeCode block reference
- Optional installer, and code signing to avoid SmartScreen warnings

## Done when
The app runs on a Windows PC without Python installed, with an icon and a user guide.
