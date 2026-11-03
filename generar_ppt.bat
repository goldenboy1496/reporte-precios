@echo off
chcp 65001 > nul
title Generador de PowerPoint - Reporte de Desfases Samsung
echo ===================================================================
echo     GENERADOR AUTOMÁTICO DE PRESENTACIÓN POWERPOINT (SAMSUNG)
echo ===================================================================
echo.
echo [1/3] Generando presentación para Guatemala (GT)...
python exportar_ppt_desfases.py gt

echo.
echo [2/3] Generando presentación para El Salvador (SV)...
python exportar_ppt_desfases.py sv

echo.
echo [3/3] Generando presentación para Honduras (HN)...
python exportar_ppt_desfases.py hn

echo.
echo ===================================================================
echo  ¡Presentaciones generadas exitosamente en formato 16:9 widescreen!
echo ===================================================================
echo.
echo Abriendo presentación de Guatemala en PowerPoint...
for %%f in (Reporte_Desfases_GT_*.pptx) do (
    start "" "%%f"
    goto :fin
)
:fin
echo Listo. Presiona cualquier tecla para salir.
pause > nul
