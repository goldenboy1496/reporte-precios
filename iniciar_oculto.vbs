Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = strDir
objShell.Run "pythonw app.py", 0, False
WScript.Sleep 2000
objShell.Run "http://localhost:5000", 1, False
