
REM VBScript that silently runs PowerShell without any visible windows
REM This is called by the scheduled task to ensure 100% silent execution

Set args = WScript.Arguments
If args.Count = 0 Then
    WScript.Echo "Error: No script path provided"
    WScript.Quit(1)
End If

scriptPath = args(0)
scriptDir = args(1)
pythonExe = args(2)
metricsScript = args(3)

' Create the PowerShell command
psCommand = "powershell.exe -NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File """ & scriptPath & """ -ScriptDir """ & scriptDir & """ -PythonExe """ & pythonExe & """ -MetricsScript """ & metricsScript & """"

' Execute silently (0 = hidden window, False = don't wait)
Set objShell = CreateObject("WScript.Shell")
objShell.Run psCommand, 0, False

' Exit without displaying anything
WScript.Quit(0)
