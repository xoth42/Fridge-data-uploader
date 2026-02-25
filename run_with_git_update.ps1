# Wrapper script for scheduled task execution (SILENT)
# Runs git pull to keep the repository up-to-date, then executes push_metrics.py
# All output is suppressed to prevent popup windows
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

try {
    Set-Location $ScriptDir
    
    # Try to update from git repository (non-blocking)
    # Suppress both stdout and stderr completely
    git pull *>$null
    
} catch {
    # Git update failed, but continue with metrics push
    # Errors are completely suppressed
}

# Periodically check if task needs updating (once per hour)
Update-TaskIfNeeded *>$null

# Run the metrics push script with all output suppressed
& $PythonExe $MetricsScript *>$null
