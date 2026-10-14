@echo off
chcp 65001 >nul
title Verificador en Vivo de El Gallo más Gallo
cd /d "C:\Users\Bryan Roblero\Documents\reporte"
echo ======================================================================
echo    AUDITORIA Y VERIFICACION EN VIVO: EL GALLO MAS GALLO
echo ======================================================================
echo.
echo Se abrira Google Chrome VISIBLE en tu pantalla para que puedas ver
echo con tus propios ojos la tienda oficial de El Gallo mas Gallo.
echo.
echo Extrayendo modelos y precios en vivo:
echo ----------------------------------------------------------------------
python scripts\gallo.py --visible
echo ----------------------------------------------------------------------
echo.
echo ¿Deseas publicar estos precios actualizados a la web de GitHub Pages?
echo [S] Si, publicar ahora
echo [N] No, solo queria revisar
echo.
set /p OPCION="Elige una opcion (S/N): "
if /i "%OPCION%"=="S" (
    echo.
    echo Compilando y subiendo a GitHub Pages...
    python exportar_reporte_estatico.py
    cd /d "C:\Users\Bryan Roblero\Documents\reporte_web"
    git add index.html
    git commit -m "Precios de Gallo mas Gallo auditados en vivo"
    git push origin main
    echo.
    echo ======================================================================
    echo   [OK] Precios auditados y subidos exitosamente a la web!
    echo   Enlace: https://goldenboy1496.github.io/reporte-precios/
    echo ======================================================================
)
echo.
pause
