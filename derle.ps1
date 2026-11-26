$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
py -3 -m PyInstaller --noconfirm --clean LimitNotch.spec
if (-not (Test-Path "dist\LimitNotch.exe")) {
    throw "dist\LimitNotch.exe oluşturulamadı"
}
$boyutMb = [math]::Round((Get-Item "dist\LimitNotch.exe").Length / 1MB, 1)
Write-Host "Hazır: dist\LimitNotch.exe ($boyutMb MB)"
