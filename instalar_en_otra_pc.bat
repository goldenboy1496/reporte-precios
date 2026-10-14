@echo off
chcp 65001 >nul
echo ================================================================
echo       INSTALADOR RAPIDO PARA OTRA COMPUTADORA
echo ================================================================
echo.
echo 1. Verificando Python...
python --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Python no esta detectado en el PATH.
    echo     Por favor descarga e instala Python desde https://www.python.org/
    echo     IMPORTANTE: Marca la casilla "Add python.exe to PATH" durante la instalacion.
    echo.
    pause
    exit /b 1
)
python --version

echo.
echo 2. Instalando librerias necesarias (Flask, Selenium, Pandas, Openpyxl)...
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [!] Hubo un error instalando las librerias. Revisa tu conexion a Internet.
    pause
    exit /b 1
)

echo.
echo 3. Verificando Google Chrome...
reg query "HKEY_CURRENT_USER\Software\Google\Chrome\BLBeacon" /v version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    reg query "HKEY_LOCAL_MACHINE\Software\Google\Chrome\BLBeacon" /v version >nul 2>&1
    if %ERRORLEVEL% NEQ 0 (
        echo [!] Google Chrome no se encontro en el registro estandar.
        echo     Asegurate de tener Google Chrome instalado para que Selenium funcione.
    ) else (
        echo [OK] Google Chrome detectado.
    )
) else (
    echo [OK] Google Chrome detectado.
)

echo.
echo ================================================================
echo   INSTALACION COMPLETADA CON EXITO!
echo ================================================================
echo.
echo Para usar el sistema en esta nueva computadora:
echo   - Doble clic en 'iniciar_oculto.vbs' para abrir el panel de control.
echo   - Doble clic en 'cambiar_horario.bat' si deseas programar la actualizacion diaria automatica.
echo.
pause
