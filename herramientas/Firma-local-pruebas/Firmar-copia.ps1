[CmdletBinding()]
param([string]$Archivo = $env:LUNADEV_FIRMA_ARCHIVO)

$ErrorActionPreference = 'Stop'
$cert = $null
function Resolve-FirmaArchivo([string]$Ruta) {
    try { $file = Get-Item -LiteralPath $Ruta.Trim().Trim('"') }
    catch { throw 'No se encontro el archivo. Pega solo la ruta, sin texto antes de C:\.' }
    if ($file.PSIsContainer -or $file.Name -notin @('LunaDevPOS.exe','Instalar-LunaDevPOS.exe','Desinstalar-LunaDevPOS.exe')) {
        throw 'Selecciona un EXE reconocido de LunaDev POS.'
    }
    return $file
}

try {
    if ([string]::IsNullOrWhiteSpace($Archivo)) {
        $default = Join-Path (Split-Path -Parent $PSScriptRoot) 'Ejecutable-compilado\LunaDevPOS.exe'
        $hasDefault = Test-Path -LiteralPath $default -PathType Leaf
        Write-Host 'LunaDev POS - firma local, solo para desarrollo'
        if ($hasDefault) { $prompt = 'Pulsa Enter para firmar LunaDevPOS.exe, o pega otra ruta' }
        else { $prompt = 'Pega la ruta del EXE de compilacion o del instalador (Enter para salir)' }
        do {
            $answer = Read-Host $prompt
            if ($null -eq $answer) { return }
            if ([string]::IsNullOrWhiteSpace($answer)) {
                if (-not $hasDefault) { return }
                $answer = $default
            }
            try { $item = Resolve-FirmaArchivo $answer }
            catch { Write-Host $_.Exception.Message -ForegroundColor Yellow }
        } until ($item)
    } else {
        $item = Resolve-FirmaArchivo $Archivo
    }
    if ((Get-AuthenticodeSignature -LiteralPath $item.FullName).Status -ne 'NotSigned') {
        throw 'El original ya contiene una firma o no se puede verificar. No se modificara.'
    }
    $engine = $null
    if ($item.Name -ieq 'LunaDevPOS.exe') {
        $engine = Join-Path $item.DirectoryName '_internal'
        $python = Get-ChildItem -LiteralPath $engine -Filter 'python3*.dll' -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -match '^python3\d+\.dll$' } | Select-Object -First 1
        if (-not $python) {
            throw 'Falta el motor _internal junto al EXE. Elige LunaDevPOS.exe dentro de Ejecutable-compilado.'
        }
    }

    $base = Join-Path $PSScriptRoot 'salidas'
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $suffix = [guid]::NewGuid().ToString('N').Substring(0,8)
    $output = Join-Path $base "prueba-$stamp-$suffix"
    [void][IO.Directory]::CreateDirectory($output)
    $copy = Join-Path $output $item.Name
    if ($engine) {
        Write-Host 'Copiando el motor del programa; puede tardar un momento...'
        $engineCopy = Join-Path $output '_internal'
        Copy-Item -LiteralPath $engine -Destination $engineCopy -Recurse
        if (-not (Test-Path -LiteralPath (Join-Path $engineCopy $python.Name) -PathType Leaf)) {
            throw 'No se pudo copiar la DLL de Python. No se firmara una copia incompleta.'
        }
    }
    Copy-Item -LiteralPath $item.FullName -Destination $copy

    # Only the current user's personal store. Never add a trusted root or publisher.
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject 'CN=LunaDev POS - Solo pruebas locales' `
        -CertStoreLocation 'Cert:\CurrentUser\My' -KeyAlgorithm RSA -KeyLength 3072 `
        -HashAlgorithm SHA256 -KeyExportPolicy NonExportable -NotAfter (Get-Date).AddDays(30)
    $null = Set-AuthenticodeSignature -LiteralPath $copy -Certificate $cert -HashAlgorithm SHA256
    $check = Get-AuthenticodeSignature -LiteralPath $copy
    if ($check.SignerCertificate.Thumbprint -ne $cert.Thumbprint -or $check.Status -in @('HashMismatch','NotSigned','NotSupportedFileFormat','Incompatible')) {
        throw "No se pudo comprobar la firma de la copia: $($check.Status)."
    }

    $report = @(
        'SOLO PRUEBAS. No distribuir como version comercial.',
        "Archivo: $($item.Name)",
        "Huella del firmante: $($cert.Thumbprint)",
        "Estado en Windows: $($check.Status)",
        "Detalle: $($check.StatusMessage)",
        "SHA256 de la copia: $((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash)",
        "Motor _internal incluido: $([bool]$engine)",
        'No se agrego el certificado a almacenes de confianza. La copia no es un paquete de instalacion nuevo.'
    )
    Set-Content -LiteralPath (Join-Path $output 'SOLO-PRUEBAS.txt') -Value $report -Encoding UTF8
    Write-Host "Firma incorporada en la copia: $copy"
    Write-Host "Estado en Windows: $($check.Status) - esta firma no otorga confianza publica."
} catch {
    Write-Host "No se pudo completar la firma: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    if ($cert) {
        Remove-Item -LiteralPath "Cert:\CurrentUser\My\$($cert.Thumbprint)" -DeleteKey
    }
}
