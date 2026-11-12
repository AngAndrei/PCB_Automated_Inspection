$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& ./.venv/Scripts/python.exe -m pytest -q
if ($LASTEXITCODE -ne 0) { throw 'Python tests failed.' }
& ./.venv/Scripts/python.exe -m ruff check src tests
if ($LASTEXITCODE -ne 0) { throw 'Python lint failed.' }
npm.cmd --prefix frontend test
if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
npm.cmd --prefix frontend run build
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
Write-Host 'All verification checks passed.' -ForegroundColor Green
