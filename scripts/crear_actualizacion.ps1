param(
  [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
  [string[]]$IncludeFiles = @(),
  [string]$UpdateName = ""
)

$ErrorActionPreference = "Stop"

function Get-NextUpdateName {
  param([string]$Root)
  $dirs = Get-ChildItem -Path $Root -Directory -Filter "actualizacion_*" -ErrorAction SilentlyContinue
  $max = 0
  foreach ($dir in $dirs) {
    if ($dir.Name -match "^actualizacion_(\d+)$") {
      $n = [int]$Matches[1]
      if ($n -gt $max) { $max = $n }
    }
  }
  return "actualizacion_{0}" -f ($max + 1)
}

function Ensure-FileCopied {
  param(
    [string]$Root,
    [string]$UpdateDir,
    [string]$RelativePath
  )
  $src = Join-Path $Root $RelativePath
  if (-not (Test-Path $src -PathType Leaf)) {
    throw "No existe archivo para incluir: $RelativePath"
  }

  $dst = Join-Path $UpdateDir $RelativePath
  $parent = Split-Path -Path $dst -Parent
  if (-not (Test-Path $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
  }
  Copy-Item -Path $src -Destination $dst -Force
}

function Get-LatestInstaller {
  param(
    [string]$BasePath,
    [string]$Filter
  )
  $file = Get-ChildItem -Path $BasePath -File -Filter $Filter -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
  if (-not $file) {
    throw "No se encontro instalador para filtro: $Filter en $BasePath"
  }
  return $file
}

if (-not (Test-Path $ProjectRoot -PathType Container)) {
  throw "No existe ProjectRoot: $ProjectRoot"
}

$updateFolderName = if ([string]::IsNullOrWhiteSpace($UpdateName)) {
  Get-NextUpdateName -Root $ProjectRoot
} else {
  if ($UpdateName -match "^actualizacion_") { $UpdateName } else { "actualizacion_$UpdateName" }
}

$updateDir = Join-Path $ProjectRoot $updateFolderName
if (Test-Path $updateDir) {
  Remove-Item -Path $updateDir -Recurse -Force
}
New-Item -ItemType Directory -Path $updateDir -Force | Out-Null

$installersRoot = Join-Path $ProjectRoot "dist\installers\windows"
$latestSetup = Get-LatestInstaller -BasePath $installersRoot -Filter "BUEN TRAGO_*_x64-setup.exe"
$latestMsi = Get-LatestInstaller -BasePath $installersRoot -Filter "BUEN TRAGO_*_x64_en-US.msi"

$updateInstallersDir = Join-Path $updateDir "installador_windows"
New-Item -ItemType Directory -Path $updateInstallersDir -Force | Out-Null
Copy-Item -Path $latestSetup.FullName -Destination (Join-Path $updateInstallersDir $latestSetup.Name) -Force
Copy-Item -Path $latestMsi.FullName -Destination (Join-Path $updateInstallersDir $latestMsi.Name) -Force

$baseFiles = @(
  "scripts/ACTUALIZAR_WINDOWS.txt"
)

foreach ($file in $baseFiles) {
  Ensure-FileCopied -Root $ProjectRoot -UpdateDir $updateDir -RelativePath $file
}

foreach ($rel in $IncludeFiles) {
  Ensure-FileCopied -Root $ProjectRoot -UpdateDir $updateDir -RelativePath $rel
}

$windowsGuidePath = Join-Path $updateDir "scripts\ACTUALIZAR_WINDOWS.txt"
if (Test-Path $windowsGuidePath -PathType Leaf) {
  $guide = Get-Content -Path $windowsGuidePath -Raw
  $guide = $guide.Replace("actualizacion_N", $updateFolderName)
  Set-Content -Path $windowsGuidePath -Value $guide -Encoding UTF8
}

$allIncluded = @(
  "installador_windows/$($latestSetup.Name)",
  "installador_windows/$($latestMsi.Name)"
)
$allIncluded += $baseFiles
$allIncluded += $IncludeFiles
$allIncluded = $allIncluded | Sort-Object -Unique

$list = ($allIncluded | ForEach-Object { "- $_" }) -join "`n"
$readme = @"
BUEN TRAGO - $($updateFolderName.ToUpper())

Actualizacion enfocada solo en Windows.

Archivos incluidos:
$list

Instalacion recomendada:
1) Ejecutar:
   installador_windows/$($latestSetup.Name)
2) Si prefieres MSI:
   installador_windows/$($latestMsi.Name)

Guia rapida:
- scripts/ACTUALIZAR_WINDOWS.txt
"@

$readmePath = Join-Path $updateDir ("LEEME_{0}.txt" -f $updateFolderName.ToUpper())
Set-Content -Path $readmePath -Value $readme -Encoding UTF8

Write-Host "Actualizacion generada: $updateDir"
Get-ChildItem -Path $updateDir -Recurse -File | Select-Object FullName, Length
