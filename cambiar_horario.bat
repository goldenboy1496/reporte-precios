@echo off
chcp 65001 >nul
cls
set SCRIPT_DIR=%~dp0
echo ================================================================
echo       CONFIGURAR HORARIO DE ACTUALIZACION AUTOMATICA
echo ================================================================
echo.
echo Carpeta actual: %SCRIPT_DIR%
echo.
echo Selecciona como deseas que se ejecute la actualizacion automatica:
echo.
echo   [1] Todos los dias a una hora fija (ej. 08:00 AM, 07:30 AM, etc.)
echo   [2] Dos veces al dia (08:00 AM y 02:00 PM)
echo   [3] Cada 4 horas continuamente
echo   [4] Cada vez que enciendas o inicies sesion en la computadora
echo   [5] Ver la programacion actual
echo   [6] Eliminar la tarea automatica
echo.
set /p OPCION="Elige una opcion (1-6): "

if "%OPCION%"=="1" goto HORA_FIJA
if "%OPCION%"=="2" goto DOS_VECES
if "%OPCION%"=="3" goto CADA_4_HORAS
if "%OPCION%"=="4" goto AL_INICIAR
if "%OPCION%"=="5" goto VER_ACTUAL
if "%OPCION%"=="6" goto ELIMINAR
goto FIN

:HORA_FIJA
echo.
echo Ingresa la hora en formato de 24 horas (ej. 07:30, 08:00, 14:00, 18:30):
set /p HORA="Hora: "
if "%HORA%"=="" set HORA=08:00
schtasks /create /sc DAILY /tn "ReportePrecios_AutoScraping" /tr "wscript.exe \"%SCRIPT_DIR%ejecutar_scraping_oculto.vbs\"" /st %HORA% /f >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Horario configurado exitosamente: Todos los dias a las %HORA%.
) else (
    echo [ERROR] No se pudo configurar el horario. Intenta ejecutando como Administrador.
)
goto FIN

:DOS_VECES
schtasks /create /sc DAILY /tn "ReportePrecios_AutoScraping" /tr "wscript.exe \"%SCRIPT_DIR%ejecutar_scraping_oculto.vbs\"" /st 08:00 /ri 360 /du 08:00 /f >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea configurada para ejecutarse a las 08:00 AM y a las 02:00 PM.
) else (
    echo [ERROR] No se pudo configurar la tarea.
)
goto FIN

:CADA_4_HORAS
schtasks /create /sc DAILY /tn "ReportePrecios_AutoScraping" /tr "wscript.exe \"%SCRIPT_DIR%ejecutar_scraping_oculto.vbs\"" /st 08:00 /ri 240 /du 12:00 /f >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea configurada para ejecutarse cada 4 horas a partir de las 08:00 AM.
) else (
    echo [ERROR] No se pudo configurar la tarea.
)
goto FIN

:AL_INICIAR
schtasks /create /sc ONLOGON /tn "ReportePrecios_AutoScraping" /tr "wscript.exe \"%SCRIPT_DIR%ejecutar_scraping_oculto.vbs\"" /f >nul
if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea configurada para ejecutarse en segundo plano cada vez que inicies sesion.
) else (
    echo [ERROR] No se pudo configurar la tarea.
)
goto FIN

:VER_ACTUAL
echo.
echo Consultando tarea en Windows:
schtasks /query /tn "ReportePrecios_AutoScraping" /fo LIST
goto FIN

:ELIMINAR
schtasks /delete /tn "ReportePrecios_AutoScraping" /f >nul
echo.
echo [OK] Tarea automatica eliminada de Windows.
goto FIN

:FIN
echo.
echo ================================================================
pause
