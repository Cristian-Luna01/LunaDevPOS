$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$taskVendor = Join-Path $taskRoot 'punto-de-venta/vendor'
$taskProvenance = Get-Content -LiteralPath (Join-Path $taskVendor 'cloudflared-provenance.json') -Raw | ConvertFrom-Json
$taskBinary = Join-Path $taskVendor 'cloudflared.exe'
if (-not (Test-Path -LiteralPath $taskBinary)) {
    $taskTemporary = Join-Path $taskVendor 'cloudflared.download'
    Invoke-WebRequest -Uri $taskProvenance.url -OutFile $taskTemporary
    if ((Get-FileHash -LiteralPath $taskTemporary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskProvenance.sha256) {
        throw 'El conector descargado no coincide con el SHA256 esperado. No se ejecutará.'
    }
    Move-Item -LiteralPath $taskTemporary -Destination $taskBinary
}
if ((Get-FileHash -LiteralPath $taskBinary -Algorithm SHA256).Hash.ToLowerInvariant() -ne $taskProvenance.sha256) {
    throw 'El conector existente no coincide con el SHA256 esperado.'
}
Write-Output 'Conector oficial verificado; archivo ignorado por Git.'
