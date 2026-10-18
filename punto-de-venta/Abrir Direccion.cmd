@echo off
setlocal
if not exist "%~dp0data\Direccion.url" (
    echo Primero abre Iniciar.cmd y deja Botica funcionando.
    pause
    exit /b 1
)
start "" "%~dp0data\Direccion.url"
endlocal
