@echo off
chcp 65001 >nul
echo ========================================================
echo   Configuracion de Scraping Automatico de Precios
echo ========================================================
echo.
echo Registrando tarea en el Programador de Tareas de Windows...
echo Horario configurado: Todos los dias a las 08:00 AM.
echo.

set SCRIPT_DIR=%~dp0
schtasks /create /sc DAILY /tn "ReportePrecios_AutoScraping" /tr "wscript.exe \"%SCRIPT_DIR%ejecutar_scraping_oculto.vbs\"" /st 08:00 /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea programada registrada exitosamente.
    echo El scraping se ejecutara de forma invisible en segundo plano todos los dias a las 8:00 AM.
) else (
    echo.
    echo [ERROR] Hubo un problema al registrar la tarea. Prueba abriendo esta ventana como Administrador.
)
echo.
pause
