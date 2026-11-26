# Build dist\MicrobitHub.exe with PyInstaller, then smoke-test it.
# Used locally and by the GitHub Actions release workflow.
#
#   .\packaging\build.ps1                                  # uses .venv if present
#   .\packaging\build.ps1 -Python python -SkipSmokeTest
param(
    [string]$Python = "",
    [switch]$SkipSmokeTest
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    if (-not $Python) {
        $venvPy = Join-Path $root ".venv\Scripts\python.exe"
        $Python = if (Test-Path $venvPy) { $venvPy } else { "python" }
    }

    & $Python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name MicrobitHub `
        --specpath build --workpath build/pyinstaller --distpath dist `
        --exclude-module pytest --exclude-module tkinter `
        packaging/run_microbithub.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }

    $exe = Join-Path $root "dist\MicrobitHub.exe"
    $sizeMb = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "Built $exe ($sizeMb MB)"

    if (-not $SkipSmokeTest) {
        # Start the app headless, let it run an asyncio task, and expect exit code 0.
        $env:QT_QPA_PLATFORM = "offscreen"
        $p = Start-Process -FilePath $exe -ArgumentList "--quit-after", "2" -Wait -PassThru
        Remove-Item Env:QT_QPA_PLATFORM
        if ($p.ExitCode -ne 0) { throw "Smoke test failed: exit code $($p.ExitCode)" }
        Write-Host "Smoke test passed"
    }
}
finally {
    Pop-Location
}
