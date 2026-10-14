@echo off
chcp 65001 >nul
echo ========================================================
echo   Eliminar Tarea Programada de Scraping
echo ========================================================
echo.
schtasks /delete /tn "ReportePrecios_AutoScraping" /f

if %ERRORLEVEL% EQU 0 (
    echo.
    echo [OK] Tarea programada eliminada con exito.
) else (
    echo.
    echo [AVISO] La tarea no existia o requirio permisos de administrador.
)
echo.
pause
