$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$posPython = $null
$posPythonArgs = @()
$posCandidates = @(
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    'python',
    'py'
)
foreach ($posCandidate in $posCandidates) {
    $posCommand = Get-Command $posCandidate -ErrorAction SilentlyContinue
    if ($posCommand) {
        $posArgs = @()
        if ($posCandidate -eq 'py') { $posArgs = @('-3') }
        & $posCommand.Source @posArgs -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' 2>$null
        if ($LASTEXITCODE -eq 0) {
            $posPython = $posCommand.Source
            $posPythonArgs = $posArgs
            break
        }
    }
}
if (-not $posPython) { throw 'Se necesita Python 3.11 o superior. Instálalo y vuelve a iniciar.' }
if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'data\pos.sqlite3'))) {
    & $posPython @posPythonArgs app.py init
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo inicializar la base.' }
}
Write-Host 'Abre http://127.0.0.1:8765 en tu navegador. Ctrl+C detiene el servidor.'
& $posPython @posPythonArgs app.py serve
