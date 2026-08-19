# Wrapper script for scheduled task execution (SILENT)
# Runs git pull to keep the repository up-to-date, then executes push_metrics.py
# All child-process output is suppressed to prevent popup windows; each external
# step runs under a hard timeout, and a short breadcrumb trail is written to
# wrapper.log so a stall before the push is never silent again.
# Also periodically checks if the task registration needs updating

param(
    [Parameter(Mandatory=$true)]
    [string]$ScriptDir,
    
    [Parameter(Mandatory=$true)]
    [string]$PythonExe,
    
    [Parameter(Mandatory=$true)]
    [string]$MetricsScript
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Continue"  # Don't stop on git errors, still run metrics

$VBScriptPath = Join-Path $ScriptDir "run_silent.vbs"
$TaskName = "PushFridgeMetrics"
$LastUpdateCheckFile = Join-Path $ScriptDir ".last_task_update_check"

# ---------------------------------------------------------------------------
# Breadcrumb log + bounded external-process runner
#
# The scheduled task launches this wrapper detached and silent, so a network
# stall in `git pull` or `pip install` would hang the run *before* Python ever
# starts -- invisibly, because all output was suppressed with *>$null. That
# leaves no trace in push_metrics.log and silently stops the once-a-minute push
# (the source of the "data stale" alerts).
#
# Wlog writes a tiny, un-suppressed breadcrumb so a stall is visible, and
# Invoke-Bounded runs each external step under a hard timeout so nothing can
# block the metrics push indefinitely. Both are best-effort and never throw.
# ---------------------------------------------------------------------------
$WrapperLog = Join-Path $ScriptDir "wrapper.log"

function Wlog([string]$Message) {
    try {
        # Keep the file bounded (~0.5 MB): retain only the most recent lines.
        if ((Test-Path $WrapperLog) -and ((Get-Item $WrapperLog -ErrorAction SilentlyContinue).Length -gt 524288)) {
            $tail = Get-Content $WrapperLog -Tail 400 -ErrorAction SilentlyContinue
            Set-Content -Path $WrapperLog -Value $tail -Encoding UTF8 -ErrorAction SilentlyContinue
        }
        $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        Add-Content -Path $WrapperLog -Value ("$ts [wrapper] $Message") -Encoding UTF8 -ErrorAction SilentlyContinue
    } catch {
        # Never let logging break the run.
    }
}

function Invoke-Bounded {
    # Run an external command with a hard timeout. Returns $true if it exited on
    # its own within $TimeoutSec, $false if it timed out (and was killed) or
    # could not be started. Never throws.
    param(
        [string]   $Label,
        [string]   $FilePath,
        [string[]] $Arguments,
        [int]      $TimeoutSec
    )
    # PID-tagged temp files avoid contention if two runs ever overlap.
    $outFile = Join-Path $ScriptDir (".wrap_{0}_{1}.out.tmp" -f $Label, $PID)
    $errFile = Join-Path $ScriptDir (".wrap_{0}_{1}.err.tmp" -f $Label, $PID)
    $proc = $null
    try {
        $proc = Start-Process -FilePath $FilePath -ArgumentList $Arguments `
            -WorkingDirectory $ScriptDir -NoNewWindow -PassThru -ErrorAction Stop `
            -RedirectStandardOutput $outFile -RedirectStandardError $errFile
    } catch {
        Wlog ("{0}: could not start ({1})" -f $Label, $_.Exception.Message)
        return $false
    }

    if ($proc.WaitForExit($TimeoutSec * 1000)) {
        Wlog ("{0}: done (exit {1})" -f $Label, $proc.ExitCode)
        $result = $true
    } else {
        # Timed out -- kill the whole process tree so nothing lingers/piles up.
        & taskkill /T /F /PID $proc.Id *>$null
        try { $proc.WaitForExit(5000) | Out-Null } catch {}
        Wlog ("{0}: TIMEOUT after {1}s -- killed" -f $Label, $TimeoutSec)
        $result = $false
    }

    Remove-Item $outFile, $errFile -Force -ErrorAction SilentlyContinue
    return $result
}

# Function to update task registration if needed (uses VBScript for silent execution)
function Update-TaskIfNeeded {
    try {
        $LastCheck = Get-Date
        if (Test-Path $LastUpdateCheckFile) {
            $LastCheckTime = Get-Item $LastUpdateCheckFile | Select-Object -ExpandProperty LastWriteTime
            # Only check once per hour to avoid overhead
            if ((New-TimeSpan -Start $LastCheckTime -End $LastCheck).TotalMinutes -lt 60) {
                return
            }
        }
        
        # Check if the VBScript exists (new setup requirement)
        if (Test-Path $VBScriptPath) {
            $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
            if ($task) {
                $currentAction = $task.Actions[0].Execute
                # If task is still using powershell.exe, update it to use VBScript
                if ($currentAction -ne "wscript.exe") {
                    # Re-register the task with VBScript wrapper
                    $Action = New-ScheduledTaskAction `
                        -Execute "wscript.exe" `
                        -Argument (
                            ('"' + $VBScriptPath + '"') +
                            " " + ('"' + (Join-Path $ScriptDir "run_with_git_update.ps1") + '"') +
                            " " + ('"' + $ScriptDir + '"') +
                            " " + ('"' + $PythonExe + '"') +
                            " " + ('"' + $MetricsScript + '"')
                        ) `
                        -WorkingDirectory $ScriptDir
                    
                    Set-ScheduledTask -TaskName $TaskName -Action $Action -ErrorAction SilentlyContinue *>$null
                }
            }
        }
        
        # Update the check timestamp
        "" | Out-File -FilePath $LastUpdateCheckFile -Force -ErrorAction SilentlyContinue
    } catch {
        # Silently fail - don't break the metrics push
    }
}

Wlog "run start"

try { Set-Location $ScriptDir } catch {}

# Try to update from git repository (non-fatal, hard time-limited so a network
# stall or credential prompt can never block the metrics push below).
Invoke-Bounded -Label "gitpull" -FilePath "git" -Arguments @("pull") -TimeoutSec 30 | Out-Null

# Sync dependencies after any git update (no-op if already up to date).
Invoke-Bounded -Label "pip" -FilePath $PythonExe `
    -Arguments @("-m", "pip", "install", "-r", (Join-Path $ScriptDir "requirements.txt"), "--quiet") `
    -TimeoutSec 60 | Out-Null

# Periodically check if task needs updating (once per hour)
Update-TaskIfNeeded *>$null

# Run one-shot diagnostic if present.
# Python (diagnose.py) owns the "already done" check via DIAGNOSE_VERSION in
# .diagnose_done — always invoke it so a version bump is actually honoured.
$DiagnoseScript = Join-Path $ScriptDir "diagnose.py"
if (Test-Path $DiagnoseScript) {
    Invoke-Bounded -Label "diagnose" -FilePath $PythonExe -Arguments @($DiagnoseScript) -TimeoutSec 45 | Out-Null
}

# Run the metrics push script -- the whole point of the task. It always runs
# regardless of what happened above, and is itself time-limited so a hung push
# cannot wedge future scheduled runs. push_metrics.py writes its own detailed
# log (push_metrics.log) via Python logging; output here stays suppressed.
Wlog "push start"
$pushOk = Invoke-Bounded -Label "push" -FilePath $PythonExe -Arguments @($MetricsScript) -TimeoutSec 60
$pushState = if ($pushOk) { "completed" } else { "TIMEOUT or failed to start" }
Wlog "run end (push $pushState)"
