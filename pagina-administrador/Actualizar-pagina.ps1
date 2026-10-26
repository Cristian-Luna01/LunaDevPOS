$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'CONFIGURADO.json')) { throw 'Usa primero Crear-pagina.cmd para una página nueva.' }
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Instala Node.js LTS desde https://nodejs.org y vuelve a abrir el actualizador.' }
# Usa el lock nuevo aunque la carpeta conserve node_modules de una versión anterior.
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las dependencias corregidas. No se publicó la actualización.' }
$env:XDG_CONFIG_HOME=Join-Path $PSScriptRoot '.config-cloudflare'
$env:WRANGLER_SEND_METRICS='false'
$config = Get-Content -LiteralPath 'wrangler.json' -Raw | ConvertFrom-Json
$config | Add-Member -NotePropertyName triggers -NotePropertyValue @{crons=@('0 * * * *')} -Force
$config | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath 'wrangler.json' -Encoding utf8
$saved = Get-Content -LiteralPath 'CONFIGURADO.json' -Raw | ConvertFrom-Json
& npx.cmd --no-install wrangler d1 execute $saved.database --remote --file migrations/0003_reliable_transfers.sql --yes
if ($LASTEXITCODE -ne 0) { throw 'No se pudo preparar la migración. No se publicó la actualización.' }
& npx.cmd --no-install wrangler deploy
if ($LASTEXITCODE -ne 0) { throw 'La actualización no terminó.' }
