$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Get-Command node.exe -ErrorAction SilentlyContinue) -or -not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'Instala Node.js LTS desde https://nodejs.org y vuelve a abrir este configurador.' }
if (Test-Path -LiteralPath 'CONFIGURADO.json') { throw 'Esta carpeta ya tiene una página creada. Para actualizar usa Actualizar-pagina.cmd; para otro negocio extrae una carpeta nueva del kit.' }
$env:XDG_CONFIG_HOME = Join-Path $PSScriptRoot '.config-cloudflare'
$env:WRANGLER_SEND_METRICS = 'false'
function Invoke-Cloud([string[]]$Arguments) {
  & npx.cmd --no-install wrangler @Arguments
  if ($LASTEXITCODE -ne 0) { throw 'La operación de Cloudflare no terminó. Revisa el mensaje anterior. No borres recursos de otra instalación.' }
}
$businessCode = Read-Host 'Nombre corto para este negocio (letras minúsculas y guiones, ejemplo luna-farmacia)'
if ($businessCode -notmatch '^[a-z][a-z0-9-]{2,30}$') { throw 'Usa de 3 a 31 letras minúsculas, números o guiones; comienza con una letra.' }
$ownerEmail = (Read-Host 'Correo del dueño para entrar a su página').Trim().ToLowerInvariant()
if ($ownerEmail -notmatch '^[^\s@]+@[^\s@]+\.[^\s@]+$') { throw 'Correo no válido.' }
$suffix = [Guid]::NewGuid().ToString('N').Substring(0,8)
$serviceName = $businessCode + '-' + $suffix
$databaseName = $serviceName + '-datos'
$config = @{name=$serviceName;main='worker.js';compatibility_date='2026-10-11';workers_dev=$true;triggers=@{crons=@('0 * * * *')};assets=@{directory='./public';binding='ASSETS';run_worker_first=$true}}
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath 'wrangler.json' -Encoding utf8
& npm.cmd ci
if ($LASTEXITCODE -ne 0) { throw 'No se pudieron preparar las herramientas. Comprueba internet.' }
Write-Host 'Se abrirá Cloudflare. Inicia sesión en la cuenta correcta y autoriza la conexión.'
Invoke-Cloud @('login')
$identityText = & npx.cmd --no-install wrangler whoami --json
if ($LASTEXITCODE -ne 0) { throw 'No se pudo verificar la cuenta de Cloudflare.' }
$identity = ($identityText -join "`n") | ConvertFrom-Json
$accounts = @($identity.accounts)
if ($accounts.Count -eq 0) { throw 'Esta cuenta no tiene una organización de Cloudflare disponible.' }
Write-Host ('Sesión de Cloudflare: ' + $identity.email)
for ($index=0; $index -lt $accounts.Count; $index++) { Write-Host (($index+1).ToString() + '. ' + $accounts[$index].name + ' — ' + $accounts[$index].id) }
$selection = Read-Host 'Número de la cuenta de este negocio'
if ($selection -notmatch '^\d+$' -or [int]$selection -lt 1 -or [int]$selection -gt $accounts.Count) { throw 'Selecciona un número válido.' }
$selectedAccount = $accounts[[int]$selection-1]
if ($selectedAccount.id -notmatch '^[a-fA-F0-9]{32}$') { throw 'Identificador de cuenta inválido.' }
$config.account_id = $selectedAccount.id
$config | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath 'wrangler.json' -Encoding utf8
Write-Host ('Se publicará en: ' + $selectedAccount.name)
if ((Read-Host 'Escribe CONTINUAR si es la cuenta correcta') -cne 'CONTINUAR') { throw 'Configuración cancelada sin crear la base.' }
Invoke-Cloud @('d1','create',$databaseName,'--binding','DB','--update-config','--use-remote')
Invoke-Cloud @('d1','execute',$databaseName,'--remote','--file','schema.sql','--yes')
Invoke-Cloud @('d1','execute',$databaseName,'--remote','--file','migrations/0002_full_direction.sql','--yes')
# Publicar primero sin credenciales no abre el acceso: el Worker falla cerrado.
Invoke-Cloud @('deploy')
$randomBytes = New-Object byte[] 32
$rng = [Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($randomBytes);$rng.Dispose()
$ownerKey = -join ($randomBytes | ForEach-Object { $_.ToString('x2') })
$hasher = [Security.Cryptography.SHA256]::Create()
$ownerHash = -join ($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($ownerKey)) | ForEach-Object { $_.ToString('x2') });$hasher.Dispose()
$ownerEmail | & npx.cmd --no-install wrangler secret put OWNER_EMAIL
if ($LASTEXITCODE -ne 0) { throw 'No se pudo guardar el correo en Cloudflare.' }
$ownerHash | & npx.cmd --no-install wrangler secret put OWNER_PASSWORD_SHA256
if ($LASTEXITCODE -ne 0) { throw 'No se pudo guardar la clave. La página no está lista.' }
@{service=$serviceName;database=$databaseName;email=$ownerEmail} | ConvertTo-Json | Set-Content -LiteralPath 'CONFIGURADO.json' -Encoding utf8
@"
DATOS PRIVADOS DE LA PAGINA CENTRAL
Correo: $ownerEmail
Clave central: $ownerKey
Servicio de Cloudflare: $serviceName

Abre Cloudflare > Workers y Pages > $serviceName. Copia el enlace workers.dev que aparece en Domains and Routes.
Entra con el correo y la clave central de este archivo. Crea cada sucursal en Configuración.
La clave central NO es la contraseña de Cloudflare ni la del usuario del mostrador.
Conserva este archivo en privado. No lo incluyas en un instalador ni compartas toda esta carpeta con otro cliente.
"@ | Set-Content -LiteralPath 'DATOS-PRIVADOS-DEL-DUENO.txt' -Encoding utf8
Write-Host 'Página creada. Los datos de acceso están en DATOS-PRIVADOS-DEL-DUENO.txt. Copia el enlace desde Cloudflare.'
