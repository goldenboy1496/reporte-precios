Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = strDir
objShell.Run "pythonw actualizar_precios.py", 0, True
