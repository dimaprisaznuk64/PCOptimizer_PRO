# Create portable zip
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root "dist\PCOptimizer_PRO"
$stageDir = Join-Path $root "dist\portable_stage"
$version = (Select-String -Path (Join-Path $root "app\__init__.py") -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
$zipPath = Join-Path $root "dist\PCOptimizer_PRO_${version}_portable.zip"

$exe = Join-Path $appDir "PCOptimizer_PRO.exe"
if (-not (Test-Path $exe)) {
    throw "Built app not found at $exe. Run scripts\build_exe.ps1 first."
}

if (Test-Path $stageDir) { Remove-Item $stageDir -Recurse -Force }
New-Item -ItemType Directory -Path $stageDir -Force | Out-Null

& robocopy $appDir $stageDir /E /XD data __pycache__ /R:0 /W:0 | Out-Host
$robocopyExit = $LASTEXITCODE
if ($robocopyExit -ge 8) {
    throw "robocopy failed with exit code $robocopyExit."
}

if (-not (Test-Path (Join-Path $stageDir "PCOptimizer_PRO.exe"))) {
    throw "Portable staging is missing PCOptimizer_PRO.exe."
}

if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force
if (-not (Test-Path $zipPath)) {
    throw "Portable zip was not created: $zipPath"
}

try {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [System.IO.Compression.ZipFile]::OpenRead($zipPath)
    try {
        if ($zip.Entries.Count -eq 0) { throw "Portable zip is empty: $zipPath" }
        $hasExe = $zip.Entries | Where-Object { $_.FullName -ieq "PCOptimizer_PRO.exe" } | Select-Object -First 1
        if (-not $hasExe) { throw "Portable zip missing PCOptimizer_PRO.exe: $zipPath" }
    } finally {
        $zip.Dispose()
    }
} catch {
    throw "Portable zip integrity check failed: $($_.Exception.Message)"
}

Remove-Item $stageDir -Recurse -Force
Write-Host "Portable zip created at $zipPath"