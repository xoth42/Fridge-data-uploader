<#
  One-time setup on the Windows data machine.
  Run from the directory that contains push_metrics.py and .env
  Right-click → "Run with PowerShell"  (or:  powershell -ExecutionPolicy Bypass -File setup.ps1)
#>
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition

# ---- 1. Install Python dependencies -----------------------------------
Write-Host "--- Installing Python dependencies ---" -ForegroundColor Cyan
pip install -r "$ScriptDir\requirements.txt"
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }

# ---- 2. Verify a manual run works -------------------------------------
Write-Host ""
Write-Host "--- Test run ---" -ForegroundColor Cyan
python "$ScriptDir\push_metrics.py"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Test run returned errors — fix .env and try again." -ForegroundColor Red
    exit 1
}

# ---- 3. Register a Windows Task Scheduler job (replaces cron) ---------
Write-Host ""
Write-Host "--- Creating scheduled task (every 1 minute) ---" -ForegroundColor Cyan

$TaskName   = "PushFridgeMetrics"
$PythonExe  = (Get-Command python).Source
$ScriptPath = Join-Path $ScriptDir "push_metrics.py"

# Remove old version of the task if it exists (idempotent re-runs)
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "  Removed previous task." -ForegroundColor Yellow
}

$Action  = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "`"$ScriptPath`"" `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)     # ~10 years ≈ indefinitely

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
    -Force

Write-Host ""
Write-Host "--- Done ---" -ForegroundColor Green
Write-Host "  Task '$TaskName' will run every 1 minute."
Write-Host "  Logs:  $ScriptDir\push_metrics.log"
Write-Host "  Verify at:  http://<PUSHGATEWAY_URL>/metrics"
Write-Host ""
Write-Host "  To remove later:  Unregister-ScheduledTask -TaskName $TaskName" -ForegroundColor DarkGray