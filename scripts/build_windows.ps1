$ErrorActionPreference = 'Stop'

if (-not (Test-Path .venv)) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt

.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --windowed --onedir --name VentaLocal main.py

Write-Host "Build finalizado. Ejecutable en dist\\VentaLocal\\VentaLocal.exe"
