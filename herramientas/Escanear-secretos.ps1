$ErrorActionPreference='Stop'
$taskRoot=Split-Path -Parent $PSScriptRoot
$taskTool=Join-Path ([IO.Path]::GetTempPath()) 'lunadev-gitleaks-8.30.1'
New-Item -ItemType Directory -Path $taskTool -Force | Out-Null
$taskArchive=Join-Path $taskTool 'gitleaks.zip'
Invoke-WebRequest 'https://github.com/gitleaks/gitleaks/releases/download/v8.30.1/gitleaks_8.30.1_windows_x64.zip' -OutFile $taskArchive
if((Get-FileHash $taskArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne 'd29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e'){throw 'No coincide la huella del escáner oficial'}
Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskTool -Force
Push-Location $taskRoot
try {
    & (Join-Path $taskTool 'gitleaks.exe') git . --log-opts='--all' --redact --report-format json --report-path gitleaks-report.json
    if($LASTEXITCODE -ne 0){throw 'El escáner detectó posibles secretos; revisar el informe con valores ocultos.'}
} finally {Pop-Location}
