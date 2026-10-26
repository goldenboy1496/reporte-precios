Set objFSO = CreateObject("Scripting.FileSystemObject")
strDir = objFSO.GetParentFolderName(WScript.ScriptFullName)
Set objShell = CreateObject("WScript.Shell")
objShell.CurrentDirectory = strDir

' Esperar 30 segundos para que Windows conecte el Wi-Fi / Red
WScript.Sleep 30000

' 1. Iniciar servidor local en segundo plano (puerto 5000)
objShell.Run "cmd.exe /c ""pythonw.exe app.py""", 0, False

' 2. Ejecutar actualizacion automatica de tiendas (solo si no ha corrido hoy)
objShell.Run "cmd.exe /c ""python.exe actualizar_precios.py --solo-primera-del-dia""", 0, False
