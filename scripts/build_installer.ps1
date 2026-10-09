# Compile the Inno Setup installer from the PyInstaller output.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    )
    $iscc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) {
    throw "ISCC.exe (Inno Setup 6) not found. Install Inno Setup 6 first."
}

$iss = Join-Path $root "installer\PCOptimizer_PRO.iss"
& $iscc $iss
Write-Host "Done. Installer in $root\dist\installer"
