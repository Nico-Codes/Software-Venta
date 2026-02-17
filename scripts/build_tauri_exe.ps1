param(
  [string]$ProjectRoot = "C:\Software Venta"
)

$ErrorActionPreference = "Stop"

$tauriRoot = Join-Path $ProjectRoot "venta_tauri"
$tauriSrc = Join-Path $tauriRoot "src-tauri"
$outputExe = Join-Path $ProjectRoot "dist\VentaModern.exe"
$buildExe = Join-Path $tauriSrc "target\release\venta_tauri.exe"

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

Write-Host "Compilando Tauri..."
cmd /c $cmd
if ($LASTEXITCODE -ne 0) {
  throw "Fallo la compilacion Tauri."
}

if (-not (Test-Path $buildExe)) {
  throw "No se genero el exe esperado en $buildExe"
}

New-Item -ItemType Directory -Path (Split-Path $outputExe -Parent) -Force | Out-Null
Copy-Item $buildExe $outputExe -Force

$info = Get-Item $outputExe
Write-Host "OK -> $($info.FullName) ($([math]::Round($info.Length / 1MB, 2)) MB)"
