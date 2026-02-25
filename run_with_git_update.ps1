# Wrapper script for scheduled task execution
# Runs git pull to keep the repository up-to-date, then executes push_metrics.py

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
    git pull 2>$null
    
} catch {
    # Git update failed, but continue with metrics push
    # Errors are suppressed to avoid task failures from git issues
}

# Run the metrics push script
& $PythonExe $MetricsScript
