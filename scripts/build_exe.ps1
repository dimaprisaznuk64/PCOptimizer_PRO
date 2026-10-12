# Build the portable onedir executable with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3.13" } else { "python" }
if (-not (Test-Path (Join-Path $root "assets\app.ico"))) {
    Invoke-Expression "$pyCmd scripts/make_icon.py"
}
Invoke-Expression "$pyCmd -m PyInstaller --clean --noconfirm PCOptimizer_PRO.spec"

$exe = Join-Path $root "dist\PCOptimizer_PRO\PCOptimizer_PRO.exe"
Write-Host "Done: $exe"
