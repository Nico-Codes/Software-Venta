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

# Archivos base siempre incluidos en cada actualizacion.
$baseFiles = @(
  "scripts/actualizar_linux.sh",
  "scripts/ACTUALIZAR_LINUX.txt"
)

foreach ($file in $baseFiles) {
  Ensure-FileCopied -Root $ProjectRoot -UpdateDir $updateDir -RelativePath $file
}

$filesToInclude = @()
if ($IncludeFiles.Count -gt 0) {
  $filesToInclude = $IncludeFiles
}

foreach ($rel in $filesToInclude) {
  Ensure-FileCopied -Root $ProjectRoot -UpdateDir $updateDir -RelativePath $rel
}

# Customize Linux guide inside each generated update folder so it references
# the concrete update number (actualizacion_5, actualizacion_6, etc.).
$linuxGuidePath = Join-Path $updateDir "scripts\ACTUALIZAR_LINUX.txt"
if (Test-Path $linuxGuidePath -PathType Leaf) {
  $guide = Get-Content -Path $linuxGuidePath -Raw
  $guide = $guide.Replace("actualizacion_N", $updateFolderName)
  Set-Content -Path $linuxGuidePath -Value $guide -Encoding UTF8
}

$allIncluded = @($baseFiles + $filesToInclude | Sort-Object -Unique)
$list = ($allIncluded | ForEach-Object { "- $_" }) -join "`n"
$readme = @"
ALTO TRAGO - $($updateFolderName.ToUpper())

Esta carpeta se copia completa al pendrive.

Archivos incluidos:
$list

Uso recomendado en Linux:
chmod +x "/media/`$USER/Ventoy/Software Venta/$updateFolderName/scripts/actualizar_linux.sh"

bash "/media/`$USER/Ventoy/Software Venta/$updateFolderName/scripts/actualizar_linux.sh" \
  --project-dir "`$HOME/Downloads/Software Venta" \
  --update-root "/media/`$USER/Ventoy/Software Venta/$updateFolderName"
"@

$readmePath = Join-Path $updateDir ("LEEME_{0}.txt" -f $updateFolderName.ToUpper())
Set-Content -Path $readmePath -Value $readme -Encoding UTF8

Write-Host "Actualizacion generada: $updateDir"
Get-ChildItem -Path $updateDir -Recurse -File | Select-Object FullName, Length
