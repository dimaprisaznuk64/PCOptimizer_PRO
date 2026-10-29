# Create portable zip
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$appDir = Join-Path $root "dist\PCOptimizer_PRO"
$stageDir = Join-Path $root "dist\portable_stage"
$version = (Select-String -Path (Join-Path $root "app\__init__.py") -Pattern '__version__ = "([^"]+)"').Matches[0].Groups[1].Value
$zipPath = Join-Path $root "dist\PCOptimizer_PRO_${version}_portable.zip"

if (Test-Path $stageDir) { Remove-Item $stageDir -Recurse -Force }
robocopy $appDir $stageDir /E /XD data __pycache__ /R:0 /W:0
Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $zipPath -Force
Remove-Item $stageDir -Recurse -Force
Write-Host "Portable zip created at $zipPath"