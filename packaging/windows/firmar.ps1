# Firma digital de los ejecutables de Windows (Authenticode).
# Solo firma si existen los secretos WINDOWS_CERT_PFX (certificado .pfx en base64) y WINDOWS_CERT_PASSWORD;
# sin ellos no hace nada y el programa se publica sin firmar.
# Uso: pwsh packaging/windows/firmar.ps1 dist\TurbuLENS.exe instalador\TurbuLENS-Instalador.exe
param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Archivos)
if (-not $env:WINDOWS_CERT_PFX) { Write-Host "Sin certificado: se omite la firma."; exit 0 }
$pfx = Join-Path $env:RUNNER_TEMP "cert.pfx"
[IO.File]::WriteAllBytes($pfx, [Convert]::FromBase64String($env:WINDOWS_CERT_PFX))
$signtool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" | Sort-Object FullName -Descending | Select-Object -First 1
if (-not $signtool) { throw "No se encontró signtool.exe" }
foreach ($f in $Archivos) {
  & $signtool.FullName sign /f $pfx /p $env:WINDOWS_CERT_PASSWORD /fd sha256 /tr http://timestamp.digicert.com /td sha256 `
    /d "TurbuLENS" /du "https://github.com/DiegoCagua/TurbuLENS" $f
  if ($LASTEXITCODE -ne 0) { throw "Falló la firma de $f" }
}
Remove-Item $pfx
