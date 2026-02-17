param(
  [switch]$InstallVsBuildTools
)

$ErrorActionPreference = "Stop"

Write-Host "Instalando Node.js LTS..."
winget install OpenJS.NodeJS.LTS --accept-source-agreements --accept-package-agreements

Write-Host "Instalando Rustup..."
winget install Rustlang.Rustup --accept-source-agreements --accept-package-agreements

if ($InstallVsBuildTools) {
  Write-Host "Instalando Visual Studio Build Tools (C++)..."
  $override = "--quiet --wait --norestart --nocache --add Microsoft.VisualStudio.Workload.VCTools --add Microsoft.VisualStudio.Component.VC.Tools.x86.x64 --add Microsoft.VisualStudio.Component.Windows11SDK.22621"
  winget install Microsoft.VisualStudio.2022.BuildTools --override $override --accept-source-agreements --accept-package-agreements
}

Write-Host "Listo. Reinicia terminal y verifica con: node -v, npm -v, rustc --version, cargo --version"
