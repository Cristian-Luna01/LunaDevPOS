@echo off
setlocal
cd /d "%~dp0..\punto-de-venta"
where py >nul 2>nul
if errorlevel 1 (
  python native_desktop.py --data-dir "%~dp0..\datos"
) else (
  py -3.12 native_desktop.py --data-dir "%~dp0..\datos"
)
if errorlevel 1 (
  echo Se necesita Python 3.12 y las dependencias de requirements-desktop.txt.
  pause
)
