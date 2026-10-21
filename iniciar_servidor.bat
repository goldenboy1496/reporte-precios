@echo off
chcp 65001 >nul
title Servidor de Precios - Comparador Regional
cd /d "%~dp0"

echo ===================================================================
echo   INICIANDO SERVIDOR - COMPARADOR DE PRECIOS REGIONAL
echo ===================================================================
echo.

:: Verificar si el servidor ya esta corriendo en el puerto 5000
netstat -ano | findstr :5000 | findstr LISTENING >nul
if %ERRORLEVEL% equ 0 (
    echo [OK] El servidor ya esta activo en el puerto 5000.
    echo [OK] Abriendo navegador en http://localhost:5000 ...
    start "" http://localhost:5000
    timeout /t 4 >nul
    exit /b 0
)

echo [1/2] Abriendo navegador en http://localhost:5000 ...
start "" http://localhost:5000

echo [2/2] Iniciando servidor Flask en http://localhost:5000 ...
echo.
echo Presiona Ctrl+C en esta ventana para detener el servidor.
echo ===================================================================
echo.

python app.py

if %ERRORLEVEL% neq 0 (
    echo.
    echo ===================================================================
    echo [ERROR] No se pudo iniciar el servidor.
    echo Revisa el mensaje anterior.
    echo ===================================================================
    pause
)
