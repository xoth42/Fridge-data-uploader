# collectall.ps1 -- Collect first and last line of ALL files in today's
# Bluefors date folder and post a report for review.
#
# Usage: powershell -ExecutionPolicy Bypass -File collectall.ps1
#
# No admin required. Strictly read-only against all data directories.
# All output files are written to the script's own folder only.

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

trap {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  COLLECTION FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---- 1. Check .env exists ----
$EnvFile = Join-Path $ScriptDir ".env"
if (-not (Test-Path $EnvFile)) {
    throw ".env file not found at: $EnvFile"
}
Write-Host "Found .env at: $EnvFile" -ForegroundColor Green

# ---- 2. Check python is available ----
$PythonExe = $null
try {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
} catch {
    throw "Python not found. Install Python from the Microsoft Store first."
}
Write-Host "Python found at: $PythonExe" -ForegroundColor Green

# ---- 3. Check python-dotenv is installed ----
Write-Host ""
Write-Host "--- Checking dependencies ---" -ForegroundColor Cyan
pip show python-dotenv >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing python-dotenv..." -ForegroundColor Yellow
    pip install python-dotenv
    if ($LASTEXITCODE -ne 0) { throw "pip install python-dotenv failed" }
}
Write-Host "Dependencies OK" -ForegroundColor Green

# ---- 4. Run collection (read-only) ----
Write-Host ""
Write-Host "--- Collecting all file data (read-only) ---" -ForegroundColor Cyan
Write-Host ""

$CollectScript = Join-Path $ScriptDir "collectall.py"
if (-not (Test-Path $CollectScript)) {
    throw "collectall.py not found at: $CollectScript"
}

python $CollectScript

if ($LASTEXITCODE -ne 0) {
    throw "collectall.py exited with errors -- see output above"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  COLLECTION COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")