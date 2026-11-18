@echo off
cd /d "%~dp0"
python cargar_forecast_tesser.py
if errorlevel 1 pause
