@echo off
title Conectar con GitHub Pages
cd /d "C:\Users\Bryan Roblero\Documents\reporte_web"
echo ========================================================
echo   SUBIENDO REPORTE A GITHUB PAGES...
echo ========================================================
echo.
echo Se abrira una ventana en tu navegador para autorizar tu cuenta de GitHub.
echo.
git push -u origin main
echo.
echo ========================================================
echo   LISTO! Presiona cualquier tecla para salir.
echo ========================================================
pause
