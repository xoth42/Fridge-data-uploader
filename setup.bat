@echo off
REM Double-click safe batch wrapper for setup.ps1
REM This file requests admin privileges and runs the PowerShell setup script

REM Check if running with admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    REM Not running as admin - request elevation
    powershell -Command "Start-Process cmd.exe -ArgumentList '/c %~f0' -Verb RunAs"
    exit /b
)

REM Running as admin - execute the PowerShell script
cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -File setup.ps1
pause
