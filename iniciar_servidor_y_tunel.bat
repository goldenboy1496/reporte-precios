@echo off
title Comparador de Precios Regional - Samsung
cd /d "%~dp0"
echo ========================================================
echo   INICIANDO COMPARADOR DE PRECIOS REGIONAL
echo ========================================================
echo.
echo 1. Iniciando aplicacion local (Flask)...
start "" /b python app.py

timeout /t 3 >nul

echo 2. Iniciando tunel seguro para acceso de tu jefe...
echo.
echo ========================================================
echo Copia el enlace 'https://....trycloudflare.com' que aparecera abajo
echo y enviaselo a tu jefe para que pueda consultar desde cualquier lugar.
echo ========================================================
echo.
cloudflared.exe tunnel --url http://localhost:5000
pause
