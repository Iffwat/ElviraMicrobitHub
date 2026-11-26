# Continuous Delivery (CD)

CD produces something people can actually **run**: a Windows `MicrobitHub.exe` that needs no Python installed.

MicrobitHub uses **continuous delivery**, not continuous deployment. Every change produces
a ready-to-use build automatically, but a **public release** happens only when a person
pushes a version tag. A desktop app has no server to deploy to, so the "deployment" is
a GitHub Release that users download.

| Kind of build | Produced by | When | Where to get it | Kept |
|---------------|-------------|------|-----------------|------|
| **Dev build** | `ci.yml` → `build` job | Every PR and every push to `main` | Actions → run → *Artifacts* → `MicrobitHub-dev-<sha>` | 14 days |
| **Release** | `release.yml` | Push of a tag `vX.Y.Z` | Repository → *Releases* | Permanent |
| **Pre-release** | `release.yml` | Push of a tag `vX.Y.Z-<suffix>` (e.g. `v0.3.0-beta.1`) | *Releases* (marked *Pre-release*) | Permanent |

---

## 1. Dev builds (every PR and `main`)

Useful for trying a change on real hardware before merging, or giving the latest
version to a tester.

1. Open the PR (or the Actions run for `main`).
2. *Checks* → **CI** → *Summary* → **Artifacts** → `MicrobitHub-dev-<sha>`.
3. GitHub downloads it as a `.zip`. Unzip it and run `MicrobitHub.exe`.

You must be signed in to GitHub to download artifacts.

---

## 2. Releases

### 2.1 Versioning
The project uses [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`.

| Change | Example | Bump |
|--------|---------|------|
| Bug fix only | Fix BLE reconnect | `0.2.0` → `0.2.1` |
| New feature, backwards compatible | Phase 2 GUI, CSV logging | `0.2.1` → `0.3.0` |
| Breaking change (e.g. protocol v3, old firmware stops working) | | `0.x` → `1.0.0` / `1.x` → `2.0.0` |

While the version is `0.x`, the project is in development. `1.0.0` = first classroom-ready release.

The version is set in **one place only**: `src/microbithub/__init__.py`
```python
__version__ = "0.2.0"
```
`pyproject.toml` reads it from there (`dynamic = ["version"]`), and so do the app's
About box, the status bar and the release check.

### 2.2 How to release — step by step

```powershell
# 1. On a branch: bump the version
#    edit src/microbithub/__init__.py  ->  __version__ = "0.2.0"
git switch -c release-0.2.0
git commit -am "Release 0.2.0"
git push -u origin release-0.2.0

# 2. Open a PR into main, wait for green CI, merge it.

# 3. Tag the merged commit on main and push the tag
git switch main
git pull
git tag -a v0.2.0 -m "MicrobitHub 0.2.0"
git push origin v0.2.0
```

4. Watch **Actions → Release**. When it finishes, the release appears under **Releases**.

### 2.3 What the Release workflow does

`.github/workflows/release.yml`, triggered by tags matching `v*.*.*`:

```
tag v0.2.0
   │
   ▼
┌──────────────────────────┐   the full CI (lint + 4 test runs);
│ ci  (calls ci.yml)       │   if anything fails, nothing is published
└────────────┬─────────────┘
             ▼
┌──────────────────────────────────────────────────────────────┐
│ release (windows-latest, contents: write)                    │
│  1. install .[build]                                         │
│  2. check tag v0.2.0 matches microbithub.__version__ (0.2.0) │
│  3. packaging/build.ps1  → build exe + headless smoke test   │
│  4. rename → MicrobitHub-v0.2.0-windows-x64.exe              │
│     write   → MicrobitHub-v0.2.0-windows-x64.exe.sha256      │
│  5. softprops/action-gh-release: create the GitHub Release   │
│     - attach exe + checksum                                  │
│     - release notes generated from merged PRs / commits      │
│     - pre-release if the tag contains "-"                    │
└──────────────────────────────────────────────────────────────┘
```

Safety checks that stop a bad release:
- **CI must pass**: the same lint and tests as for a PR.
- **Version check**: a tag that doesn't match `__version__` fails at step 2.
  This stops releasing `v0.2.0` when the code still says `0.1.0`.
- **Smoke test**: the exe must start and exit cleanly before it is published.

Only the `release` job gets write permission, and only to create the release.

### 2.4 What users get

On the Releases page:
- `MicrobitHub-v0.2.0-windows-x64.exe`: download and double-click; no install needed
- `MicrobitHub-v0.2.0-windows-x64.exe.sha256`: checksum to confirm the download is intact
- Release notes listing the changes

Verifying the download (optional, PowerShell):
```powershell
Get-FileHash .\MicrobitHub-v0.2.0-windows-x64.exe -Algorithm SHA256
# compare with the value in the .sha256 file
```

**Windows SmartScreen:** the exe isn't code-signed yet, so the first run shows
*"Windows protected your PC"*. Click **More info → Run anyway**. See §5.

---

## 3. Pre-releases

For testing with students or on hardware before an official release:

```powershell
git tag -a v0.3.0-beta.1 -m "Beta for classroom test"
git push origin v0.3.0-beta.1
```

- `__version__` must start with the same numbers. The check accepts tag `v0.3.0-beta.1` with `__version__ = "0.3.0"`.
- The release is marked **Pre-release**, so it isn't shown as "Latest".

---

## 4. When something goes wrong

### Release workflow failed (nothing was published)
1. Read the failed step in **Actions → Release**.
2. Fix the problem on a branch, open a PR and merge it.
3. Delete the tag and push it again on the fixed commit:
   ```powershell
   git tag -d v0.2.0
   git push origin :refs/tags/v0.2.0
   git pull
   git tag -a v0.2.0 -m "MicrobitHub 0.2.0"
   git push origin v0.2.0
   ```

### A published release is broken
Don't reuse the version number; people may already have downloaded it.
1. On GitHub, edit the broken release and mark it **Pre-release** (or delete it) so it is no longer "Latest".
2. Fix the bug, bump to the next patch version (`0.2.1`) and release that.

Users can always download any earlier version from the Releases page; that is the rollback.

---

## 5. Dependency updates (Dependabot)

`.github/dependabot.yml` checks every week for:
- **pip** packages (PySide6, pyqtgraph, qasync, ruff, pytest …), with minor and patch updates grouped into one PR
- **GitHub Actions** versions (`actions/checkout`, `setup-python` …)

Each Dependabot PR runs through CI and gets a dev build. Merge it when everything is green and
the dev exe still works. Updates reach users with the next release.

---

## 6. Planned improvements

| Improvement | Phase | Notes |
|-------------|-------|-------|
| App icon and version info in the exe | 7 | `--icon` and `--version-file` in `build.ps1` |
| Code signing | 7 | Removes the SmartScreen warning; needs a code-signing certificate stored as a GitHub secret |
| Installer (Inno Setup / MSIX) | 7 | Start-menu shortcut, uninstall entry |
| Attach the MakeCode extension and `.hex` to releases | 3 | So the firmware version always matches the app version |
| macOS / Linux builds | later | Add matrix entries to `release.yml`; BLE behaves differently on each OS |
| `CHANGELOG.md` | any | Release notes are generated automatically for now |
