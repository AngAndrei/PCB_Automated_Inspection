param([int]$Port = 8000, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $python)) { throw 'Run ./scripts/setup.ps1 first.' }
if (-not (Test-Path -LiteralPath 'frontend/dist/index.html')) { throw 'Build the frontend with npm.cmd --prefix frontend run build.' }
$env:YOLO_CONFIG_DIR = Join-Path $projectRoot 'data/ultralytics'
$env:PYTHONUNBUFFERED = '1'
$env:YOLO_OFFLINE = 'true'
$env:YOLO_AUTOINSTALL = 'false'
New-Item -ItemType Directory -Force -Path 'data/logs', $env:YOLO_CONFIG_DIR | Out-Null
$worker = Start-Process -FilePath $python -ArgumentList @('-m', 'pcb_inspection.worker') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data/logs/worker.out.log' -RedirectStandardError 'data/logs/worker.err.log'
try {
    Write-Host "Circuit Inspect: http://127.0.0.1:$Port (Ctrl+C stops this session)" -ForegroundColor Green
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$Port" }
    & $python -m uvicorn pcb_inspection.api:app --host 127.0.0.1 --port $Port
} finally {
    if (-not $worker.HasExited) { Stop-Process -Id $worker.Id -ErrorAction SilentlyContinue }
}
