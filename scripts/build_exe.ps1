# Build the portable onedir executable with PyInstaller.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$pyCmd = if (Get-Command py -ErrorAction SilentlyContinue) { "py -3.13" } else { "python" }
if (-not (Test-Path (Join-Path $root "assets\app.ico"))) {
    Invoke-Expression "$pyCmd scripts/make_icon.py"
}

# Preserve user data (settings/logs live next to the exe in `<exe_dir>\data`),
# because PyInstaller wipes dist\PCOptimizer_PRO during COLLECT.
$dataDir = Join-Path $root "dist\PCOptimizer_PRO\data"
$backup = Join-Path $env:TEMP "pcopt_data_backup_$(Get-Date -Format yyyyMMdd_HHmmss)"
$hadData = $false
if (Test-Path $dataDir) {
    $hadData = $true
    Copy-Item $dataDir $backup -Recurse -Force
    Write-Host "Backed up data to $backup"
}

try {
    Invoke-Expression "$pyCmd -m PyInstaller --clean --noconfirm PCOptimizer_PRO.spec"
}
finally {
    # Restore even if the build failed, so the user's data is never lost.
    if ($hadData -and (Test-Path $backup)) {
        if (-not (Test-Path (Join-Path $root "dist\PCOptimizer_PRO"))) {
            New-Item -ItemType Directory -Path (Join-Path $root "dist\PCOptimizer_PRO") -Force | Out-Null
        }
        New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
        Copy-Item (Join-Path $backup "*") $dataDir -Recurse -Force -ErrorAction SilentlyContinue
        Write-Host "Restored data to $dataDir"
    }
    if (Test-Path $backup) {
        Remove-Item $backup -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$exe = Join-Path $root "dist\PCOptimizer_PRO\PCOptimizer_PRO.exe"
Write-Host "Done: $exe"
