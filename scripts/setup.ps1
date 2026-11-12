param([switch]$SkipML)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
if (-not (Test-Path -LiteralPath '.venv/Scripts/python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11 or later is required.' }
}
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
$package = if ($SkipML) { '.[dev]' } else { '.[dev,ml]' }
& $python -m pip install -e $package
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
npm.cmd --prefix frontend ci --no-audit --no-fund
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'Setup complete. Start the app with ./scripts/start.ps1' -ForegroundColor Green
