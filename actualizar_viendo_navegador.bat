@echo off
chcp 65001 >nul
cls
echo ================================================================
echo       ACTUALIZACION MANUAL DE PRECIOS (MODO VISIBLE)
echo ================================================================
echo.
echo Se abrira una ventana de Google Chrome para cada tienda
echo para que puedas ver la navegacion y la extraccion en vivo.
echo.
echo Presiona cualquier tecla para comenzar...
pause >nul
echo.

python actualizar_precios.py --visible

echo.
echo ================================================================
echo   Extraccion finalizada. Ya puedes revisar http://localhost:5000
echo ================================================================
pause
