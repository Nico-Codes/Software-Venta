param(
  [string]$ProjectRoot = "C:\Software Venta"
)

$ErrorActionPreference = "Stop"

$tauriRoot = Join-Path $ProjectRoot "venta_tauri"
$tauriSrc = Join-Path $tauriRoot "src-tauri"
$outputDir = Join-Path $ProjectRoot "dist\installers\windows"
$bundleDir = Join-Path $tauriSrc "target\release\bundle"

if (-not (Test-Path $tauriRoot)) {
  throw "No se encontro carpeta venta_tauri en $ProjectRoot"
}

$vsDevCmd = "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path $vsDevCmd)) {
  throw "No se encontro VsDevCmd.bat. Instala Visual Studio Build Tools C++."
}

$nodeDir = Join-Path $ProjectRoot ".tools\node-v24.13.1-win-x64"
if (-not (Test-Path (Join-Path $nodeDir "npm.cmd"))) {
  throw "No se encontro npm.cmd en $nodeDir"
}

$cargoBin = Join-Path $env:USERPROFILE ".cargo\bin"
if (-not (Test-Path (Join-Path $cargoBin "cargo.exe"))) {
  throw "No se encontro cargo.exe en $cargoBin"
}

$cmd = @(
  "`"$vsDevCmd`" -arch=x64",
  "set PATH=$cargoBin;$nodeDir;%PATH%",
  "cd /d `"$tauriRoot`"",
  "npm.cmd run tauri:build"
) -join " && "

Write-Host "Compilando instaladores Windows (Tauri bundle)..."
cmd /c $cmd
if ($LASTEXITCODE -ne 0) {
  throw "Fallo la compilacion de instaladores Tauri para Windows."
}

$files = @()
if (Test-Path (Join-Path $bundleDir "msi")) {
  $files += Get-ChildItem -Path (Join-Path $bundleDir "msi") -File -Filter *.msi
}
if (Test-Path (Join-Path $bundleDir "nsis")) {
  $files += Get-ChildItem -Path (Join-Path $bundleDir "nsis") -File -Filter *.exe
}

if ($files.Count -eq 0) {
  throw "No se encontraron instaladores Windows en $bundleDir"
}

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
foreach ($file in $files) {
  Copy-Item $file.FullName (Join-Path $outputDir $file.Name) -Force
}

Write-Host "Instaladores listos en: $outputDir"
Get-ChildItem $outputDir -File | Select-Object Name, Length
