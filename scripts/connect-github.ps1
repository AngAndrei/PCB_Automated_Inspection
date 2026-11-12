param([Parameter(Mandatory=$true)][string]$RepositoryUrl, [switch]$Push)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
if ($RepositoryUrl -notmatch '^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:\.git)?/?$') {
    throw 'Use the HTTPS URL of your GitHub repository.'
}
$existingOrigin = git remote get-url origin 2>$null
if ($existingOrigin -and $existingOrigin -ne $RepositoryUrl) {
    throw "Origin already points to $existingOrigin. Inspect it before changing the destination."
}
if (-not $existingOrigin) { git remote add origin $RepositoryUrl }
if ($LASTEXITCODE -ne 0) { throw 'Could not configure origin.' }
if ($Push) {
    if (git status --porcelain) { throw 'Commit the implementation files before pushing: git add . ; git commit -m "feat: implement local PCB inspection workbench"' }
    $projectBranch = git branch --show-current
    git push --set-upstream origin $projectBranch
    if ($LASTEXITCODE -ne 0) { throw 'Feature branch push failed.' }
}
Write-Host "GitHub remote configured: $RepositoryUrl" -ForegroundColor Green
