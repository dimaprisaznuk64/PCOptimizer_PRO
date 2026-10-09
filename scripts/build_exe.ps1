# Build the portable onedir executable with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

python scripts/make_icon.py
python -m PyInstaller --clean --noconfirm PCOptimizer_PRO.spec

$exe = Join-Path $root "dist\PCOptimizer_PRO\PCOptimizer_PRO.exe"
Write-Host "Done: $exe"
