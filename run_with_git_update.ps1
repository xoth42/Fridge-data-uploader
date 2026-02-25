# Wrapper script for scheduled task execution (SILENT)
# Runs git pull to keep the repository up-to-date, then executes push_metrics.py
# All output is suppressed to prevent popup windows

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

try {
    Set-Location $ScriptDir
    
    # Try to update from git repository (non-blocking)
    # Suppress both stdout and stderr completely
    git pull *>$null
    
} catch {
    # Git update failed, but continue with metrics push
    # Errors are completely suppressed
}

# Run the metrics push script with all output suppressed
& $PythonExe $MetricsScript *>$null
