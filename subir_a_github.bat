@echo off
chcp 65001 >nul
title Actualizar y Subir Reporte a GitHub Pages
cd /d C:\Users\Bryan Roblero\Documents\reporte
echo ========================================================
echo   COMPILANDO DATOS Y SUBIENDO A GITHUB PAGES...
echo ========================================================
echo.
python exportar_reporte_estatico.py
echo.
git add -A
git commit -m "Actualizacion automatica del reporte" >nul 2>&1
git push origin main
echo.
echo ========================================================
echo   LISTO! Reporte en vivo actualizado en la web:
echo   https://goldenboy1496.github.io/reporte-precios/
echo ========================================================
echo.
pause
