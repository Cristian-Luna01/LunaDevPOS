@echo off
setlocal
cd /d "%~dp0"
title Botica - Recuperar acceso
set "POS_PYTHON="
set "POS_ARGS="
set "POS_BUNDLED=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%POS_BUNDLED%" (
    "%POS_BUNDLED%" -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if not errorlevel 1 set "POS_PYTHON=%POS_BUNDLED%"
)
if defined POS_PYTHON goto run
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "POS_PYTHON=py"
    set "POS_ARGS=-3"
    goto run
)
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
    set "POS_PYTHON=python"
    goto run
)
echo.
echo No se encontro Python 3.11 o superior en este equipo.
echo Copia este mensaje para solicitar ayuda con la instalacion.
goto finish
:run
"%POS_PYTHON%" %POS_ARGS% "%~dp0recuperar_acceso.py"
:finish
echo.
echo La ventana permanecera abierta para que puedas leer el resultado.
pause
endlocal
