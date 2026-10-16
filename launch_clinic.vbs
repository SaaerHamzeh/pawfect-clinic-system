' Pawfect Clinic Desktop Launcher
' Runs the server invisibly in the background and opens the clinic in desktop app mode.

Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strPath = fso.GetParentFolderName(WScript.ScriptFullName)

' 1. Check if server is already responding on localhost:8000
On Error Resume Next
Set xmlHttp = CreateObject("MSXML2.ServerXMLHTTP.6.0")
xmlHttp.setTimeouts 1000, 1000, 1000, 1000
xmlHttp.open "GET", "http://localhost:8000/accounts/login/", False
xmlHttp.send

If Err.Number <> 0 Then
    ' Server is not running, start it silently (0 = hidden window)
    WshShell.CurrentDirectory = strPath
    WshShell.Run "run_clinic_silent.bat", 0, False
    WScript.Sleep 2000
End If
On Error GoTo 0

' 2. Launch Microsoft Edge in App Mode (Dedicated window without address bar)
On Error Resume Next
WshShell.Run "msedge.exe --app=http://localhost:8000", 1, False

If Err.Number <> 0 Then
    ' Fallback to default browser
    WshShell.Run "http://localhost:8000", 1, False
End If
