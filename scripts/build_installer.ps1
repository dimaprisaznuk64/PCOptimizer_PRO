# Compile the Inno Setup installer from the PyInstaller output.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Find-Iscc {
    $cmd = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe"
    ) | Where-Object { Test-Path $_ }
    if ($candidates) { return $candidates | Select-Object -First 1 }

    $uninstallRoots = @(
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    )
    foreach ($rootKey in $uninstallRoots) {
        foreach ($entry in Get-ChildItem $rootKey -ErrorAction SilentlyContinue) {
            $props = Get-ItemProperty $entry.PSPath -ErrorAction SilentlyContinue
            if ($props.DisplayName -like "Inno Setup*" -and $props.InstallLocation) {
                $candidate = Join-Path $props.InstallLocation "ISCC.exe"
                if (Test-Path $candidate) { return $candidate }
            }
        }
    }
    return $null
}

$iscc = Find-Iscc
if (-not $iscc) {
    throw "ISCC.exe (Inno Setup 6) not found. Install Inno Setup 6 first."
}

$appDir = Join-Path $root "dist\PCOptimizer_PRO"
$exe = Join-Path $appDir "PCOptimizer_PRO.exe"
if (-not (Test-Path $exe)) {
    throw "Built app not found at $exe. Run scripts\build_exe.ps1 first, then re-run this script."
}

$iss = Join-Path $root "installer\PCOptimizer_PRO.iss"
$versionFile = Join-Path $root "assets\version_info.txt"
$expectedVersion = $null
if (Test-Path $versionFile) {
    $match = Select-String -Path $versionFile -Pattern "StringStruct\(u'ProductVersion', u'([^']+)'\)" | Select-Object -First 1
    if ($match) { $expectedVersion = $match.Matches[0].Groups[1].Value }
}
$outDir = Join-Path $root "dist\installer"
$before = @{}
if (Test-Path $outDir) {
    Get-ChildItem $outDir -Filter *.exe -ErrorAction SilentlyContinue | ForEach-Object {
        $before[$_.FullName] = $_.LastWriteTimeUtc
    }
}

& $iscc $iss
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    throw "ISCC.exe failed with exit code $exitCode."
}

if (-not (Test-Path $outDir)) {
    throw "Installer output directory not found: $outDir"
}
$installer = Get-ChildItem $outDir -Filter *.exe -ErrorAction SilentlyContinue |
    Where-Object { -not $before.ContainsKey($_.FullName) -or $_.LastWriteTimeUtc -gt $before[$_.FullName] } |
    Sort-Object LastWriteTimeUtc -Descending |
    Select-Object -First 1
if (-not $installer) {
    $installer = Get-ChildItem $outDir -Filter *.exe -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTimeUtc -Descending |
        Select-Object -First 1
}
if (-not $installer) {
    throw "ISCC.exe reported success but no installer .exe was found in $outDir"
}
if ($expectedVersion -and $installer.Name -notlike "*$expectedVersion*") {
    Write-Warning "Installer name '$($installer.Name)' does not contain expected version '$expectedVersion'."
}

Write-Host "Done. Installer: $($installer.FullName)"
