<#
  One-shot setup for the Fridge Data Uploader on the Windows data machine.

  What this script does (in order):
    1. Checks that .env exists -- fails fast if not
    2. Checks that Python is available
    3. Installs pip dependencies from requirements.txt
    4. Does a test run of push_metrics.py using regular python (errors visible)
    5. Removes any existing PushFridgeMetrics scheduled task
    6. Locates pythonw.exe (windowless Python -- ships with Microsoft Store Python)
    7. Registers a new scheduled task that runs silently as SYSTEM every minute

  Usage:
    Right-click -> "Run with PowerShell"
    -- or --
    powershell -ExecutionPolicy Bypass -File setup.ps1

  NOTE: All strings are pure ASCII (no characters above code point 127).
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

trap {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  SETUP FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Press any key to exit..." -ForegroundColor Yellow
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    exit 1
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---- 1. Check .env exists ------------------------------------------
Write-Host "--- Checking .env ---" -ForegroundColor Cyan
$EnvFile = Join-Path $ScriptDir ".env"
if (-not (Test-Path $EnvFile)) {
    throw ".env file not found at: $EnvFile`n  -> Copy .env.example to .env and fill in your values."
}
Write-Host "  Found: $EnvFile" -ForegroundColor Green

# ---- 2. Check Python is available ----------------------------------
Write-Host ""
Write-Host "--- Checking Python ---" -ForegroundColor Cyan
$PythonExe = $null
try {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
} catch {
    throw "Python not found. Install Python from the Microsoft Store, then re-run this script."
}
Write-Host "  Found: $PythonExe" -ForegroundColor Green

# ---- 3. Install pip dependencies -----------------------------------
Write-Host ""
Write-Host "--- Installing Python dependencies ---" -ForegroundColor Cyan
$ReqFile = Join-Path $ScriptDir "requirements.txt"
pip install -r $ReqFile
if ($LASTEXITCODE -ne 0) { throw "pip install failed -- check the output above." }
Write-Host "  Dependencies installed." -ForegroundColor Green

# ---- 4. Test run (visible errors) ----------------------------------
Write-Host ""
Write-Host "--- Test run of push_metrics.py ---" -ForegroundColor Cyan
$ScriptPath = Join-Path $ScriptDir "push_metrics.py"
python $ScriptPath
if ($LASTEXITCODE -ne 0) {
    throw "Test run failed -- fix .env / network / logs path and try again."
}
Write-Host "  Test run succeeded." -ForegroundColor Green

# ---- 5. Remove existing task if present ----------------------------
Write-Host ""
Write-Host "--- Checking for existing scheduled task ---" -ForegroundColor Cyan
$TaskName = "PushFridgeMetrics"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Removed previous task." -ForegroundColor Yellow
} else {
    Write-Host "  No existing task found." -ForegroundColor Green
}

# ---- 6. Locate pythonw.exe (windowless -- no CMD popup) ------------
Write-Host ""
Write-Host "--- Locating pythonw.exe ---" -ForegroundColor Cyan
$PythonwExe = $null

# Search alongside the python.exe that is already on PATH
$PythonDir = Split-Path -Parent $PythonExe
$Candidate = Join-Path $PythonDir "pythonw.exe"
if (Test-Path $Candidate) {
    $PythonwExe = $Candidate
}

# Fallback: scan common Microsoft Store Python locations
if (-not $PythonwExe) {
    $LocalAppData = [System.Environment]::GetFolderPath("LocalApplicationData")
    $SearchRoot = Join-Path $LocalAppData "Microsoft\WindowsApps"
    if (Test-Path $SearchRoot) {
        $Found = Get-ChildItem -Path $SearchRoot -Filter "pythonw.exe" -Recurse `
                     -ErrorAction SilentlyContinue |
                 Select-Object -First 1
        if ($Found) { $PythonwExe = $Found.FullName }
    }
}

if (-not $PythonwExe) {
    throw (
        "pythonw.exe not found next to $PythonExe and not found in" +
        " %LOCALAPPDATA%\Microsoft\WindowsApps." +
        " Install Python from the Microsoft Store (it ships pythonw.exe)."
    )
}
Write-Host "  Found: $PythonwExe" -ForegroundColor Green

# ---- 7. Register new scheduled task --------------------------------
Write-Host ""
Write-Host "--- Registering scheduled task (silent, SYSTEM, every 1 min) ---" `
    -ForegroundColor Cyan

$Action = New-ScheduledTaskAction `
    -Execute $PythonwExe `
    -Argument ('"' + $ScriptPath + '"') `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "Push fridge sensor metrics to Prometheus Pushgateway every minute" `
    -RunLevel Highest `
    -User "SYSTEM" `
    -Force

Write-Host "  Task registered." -ForegroundColor Green

# ---- Done ----------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Task name  : $TaskName"
Write-Host "  Runner     : $PythonwExe (no CMD popup)"
Write-Host "  Runs as    : SYSTEM"
Write-Host "  Frequency  : every 1 minute"
Write-Host "  Log file   : $ScriptDir\push_metrics.log"
Write-Host "  Verify at  : http://<PUSHGATEWAY_URL>/metrics"
Write-Host ""
Write-Host "  To remove later:"
Write-Host "    Unregister-ScheduledTask -TaskName $TaskName" -ForegroundColor DarkGray
Write-Host ""
Write-Host "Press any key to exit..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")