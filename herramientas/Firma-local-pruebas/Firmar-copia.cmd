@echo off
setlocal
rem Let Windows PowerShell resolve its own modules if started from PowerShell 7.
set "PSModulePath="
set "LUNADEV_FIRMA_ARCHIVO=%~1"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0Firmar-copia.ps1"
set "RESULTADO=%ERRORLEVEL%"
echo.
pause
exit /b %RESULTADO%
