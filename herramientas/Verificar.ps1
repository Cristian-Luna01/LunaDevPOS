$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $PSScriptRoot 'Preparar-conector.ps1')
Push-Location (Join-Path $taskRoot 'punto-de-venta')
try {
    python -m pip install -r requirements-test.txt
    if ($LASTEXITCODE -ne 0) { throw 'No se instalaron dependencias de pruebas.' }
    python -m unittest discover -s . -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas Python.' }
    node --test test_direction_responses.js test_financial_ui.js
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas de interfaz.' }
} finally { Pop-Location }
Push-Location (Join-Path $taskRoot 'pagina-administrador')
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'No se instalaron dependencias del panel.' }
    npm test
    if ($LASTEXITCODE -ne 0) { throw 'Fallaron las pruebas del panel.' }
} finally { Pop-Location }
Write-Output 'Todas las verificaciones terminaron correctamente.'
