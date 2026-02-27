<#
  One-shot setup for the Fridge Data Uploader on the Windows data machine.

  What this script does (in order):
    1. Checks that .env exists -- fails fast if not
    2. Checks that Python is available
    3. Installs pip dependencies from requirements.txt
    4. Does a test run of push_metrics.py using regular python (errors visible)
    5. Removes any existing PushFridgeMetrics scheduled task
    6. Locates pythonw.exe (windowless Python -- ships with Microsoft Store Python)
    7. Registers a new scheduled task that runs silently every minute
    8. Updates from git repository

  Usage:
    EASIEST:
      Double-click setup.bat (it will request admin privileges automatically)
    
    Alternatives:
      Right-click setup.ps1 -> "Run with PowerShell"
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


# ---- 2. Check Python is available and version >=3.9 -----------------
Write-Host "" 
Write-Host "--- Checking Python ---" -ForegroundColor Cyan
$PythonExe = $null
$MinVersion = [Version]"3.9"
$PythonOverride = $null

# Check for manual override in .env
$envLines = Get-Content $EnvFile | Where-Object { $_ -match "^PYTHON_EXE_OVERRIDE=" }
## Read .env file lines robustly
$envLines = Get-Content -Path ".env" -ErrorAction SilentlyContinue
# Always treat as array for count check
if ($null -ne $envLines -and @($envLines).Count -gt 0) {
    $PythonOverride = $envLines[0] -replace "^PYTHON_EXE_OVERRIDE=", ""
    if ($PythonOverride -and (Test-Path $PythonOverride)) {
        $PythonExe = $PythonOverride
        Write-Host "  Manual override: using $PythonExe" -ForegroundColor Yellow
    }
}

if (-not $PythonExe) {
    # Use regex to find python3.X executables with X >= 9 (including 3.10, 3.13, .exe, etc.)
    $candidates = Get-Command -Name "python3.*" -ErrorAction SilentlyContinue | Where-Object {
        $match = [regex]::Match($_.Name, "^python3\.(\d+)(?:\.exe)?$")
        $match.Success -and [int]$match.Groups[1].Value -ge 9
    }
    foreach ($cmd in $candidates) {
        try {
            $verOut = & $cmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            $verMatch = [regex]::Match($verOut, "^3\.(\d+)$")
            if ($verMatch.Success -and [int]$verMatch.Groups[1].Value -ge 9) {
                $PythonExe = $cmd.Source
                Write-Host "  Found: $PythonExe (version $verOut)" -ForegroundColor Green
                break
            } else {
                Write-Host "  Skipping $($cmd.Name) (version $verOut < 3.9)" -ForegroundColor DarkGray
            }
        } catch {}
    }
    # Fallback to 'python' if no python3.X >= 9 found
    if (-not $PythonExe) {
        try {
            $cmd = Get-Command python -ErrorAction Stop
            $verOut = & $cmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            $verMatch = [regex]::Match($verOut, "^3\.(\d+)$")
            if ($verMatch.Success -and [int]$verMatch.Groups[1].Value -ge 9) {
                $PythonExe = $cmd.Source
                Write-Host "  Found: $PythonExe (version $verOut)" -ForegroundColor Green
            } else {
                Write-Host "  Skipping python (version $verOut < 3.9)" -ForegroundColor DarkGray
            }
        } catch {}
    }
}

if (-not $PythonExe) {
    throw "No suitable Python >=3.9 found. Install Python >=3.9 and/or set PYTHON_EXE_OVERRIDE in .env."
}

# ---- 3. Install pip dependencies -----------------------------------
Write-Host ""
Write-Host "--- Installing Python dependencies ---" -ForegroundColor Cyan
$ReqFile = Join-Path $ScriptDir "requirements.txt"
 & $PythonExe -m pip install -r $ReqFile
if ($LASTEXITCODE -ne 0) { throw "pip install failed -- check the output above." }
Write-Host "  Dependencies installed." -ForegroundColor Green

# ---- 4. Test run (visible errors) ----------------------------------
Write-Host ""
Write-Host "--- Test run of push_metrics.py ---" -ForegroundColor Cyan
$ScriptPath = Join-Path $ScriptDir "push_metrics.py"
& $PythonExe $ScriptPath
if ($LASTEXITCODE -eq 2) {
    Write-Host "  WARNING: Test run failed due to Pushgateway server being down or unreachable." -ForegroundColor Yellow
    Write-Host "  The scheduled task will still be set up. When the server is available, data will be pushed automatically." -ForegroundColor Yellow
} elseif ($LASTEXITCODE -ne 0) {
    throw "Test run failed -- fix .env / network / logs path and try again."
} else {
    Write-Host "  Test run succeeded." -ForegroundColor Green
}

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
    Write-Host "  pythonw.exe not found next to python.exe -- searching WindowsApps..." `
        -ForegroundColor Yellow
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
Write-Host "--- Registering scheduled task (silent, every 1 min with git updates) ---" `
    -ForegroundColor Cyan

$Action = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument (
        ('"' + (Join-Path $ScriptDir "run_silent.vbs") + '"') +
        " " + ('"' + (Join-Path $ScriptDir "run_with_git_update.ps1") + '"') +
        " " + ('"' + $ScriptDir + '"') +
        " " + ('"' + $PythonwExe + '"') +
        " " + ('"' + $ScriptPath + '"')
    ) `
    -WorkingDirectory $ScriptDir

$Trigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).Date `
    -RepetitionInterval (New-TimeSpan -Minutes 1) `
    -RepetitionDuration (New-TimeSpan -Days 3650)   # ~10 years (~indefinitely)

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 2) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger $Trigger `
        -Settings $Settings `
        -Description "Pull latest code from git, then push fridge sensor metrics to Prometheus Pushgateway every minute" `
        -RunLevel Highest `
        -Force -ErrorAction Stop
    
    Write-Host "  Task registered." -ForegroundColor Green
} catch {
    if ($_ -match "Access is denied" -or $_ -match "unauthorized") {
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Red
        Write-Host "  ADMINISTRATOR PRIVILEGES REQUIRED" -ForegroundColor Red
        Write-Host "========================================" -ForegroundColor Red
        Write-Host ""
        Write-Host "Error: Unable to register scheduled task." -ForegroundColor Red
        Write-Host ""
        Write-Host "This script must be run with Administrator privileges." -ForegroundColor Yellow
        Write-Host ""
        Write-Host "Please re-run this script using one of these methods:" -ForegroundColor Yellow
        Write-Host "  1. Right-click this script -> 'Run with PowerShell' -> click 'Run anyway' -> select 'Run as administrator'" -ForegroundColor White
        Write-Host "  2. Open PowerShell as administrator, then run:" -ForegroundColor White
        Write-Host "     powershell -ExecutionPolicy Bypass -File setup.ps1" -ForegroundColor DarkGray
        Write-Host "  3. Open Command Prompt as administrator, then run:" -ForegroundColor White
        Write-Host "     powershell -ExecutionPolicy Bypass -File setup.ps1" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "Press any key to exit..." -ForegroundColor Yellow
        $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        exit 1
    } else {
        throw $_
    }
}

# ---- 8. Update from git repository --------------------------------
Write-Host ""
Write-Host "--- Updating from git repository ---" -ForegroundColor Cyan

try {
    $CurrentLocation = Get-Location
    Set-Location $ScriptDir
    
    git pull
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Repository updated." -ForegroundColor Green
    } else {
        Write-Host "  Warning: git pull exited with code $LASTEXITCODE" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  Warning: Unable to update from git repository: $_" -ForegroundColor Yellow
} finally {
    Set-Location $CurrentLocation
}

# ---- Done ----------------------------------------------------------
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Task name  : $TaskName"
Write-Host "  Runner     : VBScript wrapper (100% silent execution)"
Write-Host "  Frequency  : every 1 minute (with git pull before each run)"
Write-Host "  Log file   : $ScriptDir\push_metrics.log"
Write-Host "  Verify at  : http://<PUSHGATEWAY_URL>/metrics"
Write-Host ""
Write-Host "  To remove later (run from an elevated PowerShell):"
Write-Host "    Unregister-ScheduledTask -TaskName $TaskName" -ForegroundColor DarkGray
Write-Host ""