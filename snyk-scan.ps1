$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "Ambiente .venv nao encontrado. Execute ./run.ps1 primeiro." -ForegroundColor Red
    exit 1
}

$snyk = Join-Path $PSScriptRoot "node_modules\.bin\snyk.cmd"
if (-not (Test-Path $snyk)) {
    Write-Host "Snyk nao instalado. Execute: npm install" -ForegroundColor Red
    exit 1
}

Write-Host "=== Snyk Open Source (dependencias) ===" -ForegroundColor Cyan
& $snyk test --file=requirements.txt --command=$python
$scaExit = $LASTEXITCODE

Write-Host ""
Write-Host "=== Snyk Code (SAST) ===" -ForegroundColor Cyan
& $snyk code test --exclude=node_modules --exclude=.venv --exclude=venv
$codeExit = $LASTEXITCODE

if ($scaExit -ne 0 -or $codeExit -ne 0) {
    exit 1
}
