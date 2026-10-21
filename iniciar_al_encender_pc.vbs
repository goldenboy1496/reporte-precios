Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = strDir

' Esperar 45 segundos para que Windows conecte el Wi-Fi / Red
WScript.Sleep 45000

' Ejecutar en segundo plano invisible (solo si no ha corrido hoy)
objShell.Run "pythonw.exe actualizar_precios.py --solo-primera-del-dia", 0, True
