$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'CONFIGURADO.json')) { throw 'Usa primero Crear-pagina.cmd para una página nueva.' }
$env:XDG_CONFIG_HOME=Join-Path $PSScriptRoot '.config-cloudflare'
$env:WRANGLER_SEND_METRICS='false'
$config = Get-Content -LiteralPath 'wrangler.json' -Raw | ConvertFrom-Json
$config | Add-Member -NotePropertyName triggers -NotePropertyValue @{crons=@('0 * * * *')} -Force
$config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath 'wrangler.json' -Encoding utf8
& npx.cmd --no-install wrangler deploy
if ($LASTEXITCODE -ne 0) { throw 'La actualización no terminó.' }
