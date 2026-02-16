#!/usr/bin/env bash
set -euo pipefail

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements-dev.txt

.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --onedir --name VentaLocal main.py

echo "Build finalizado. Ejecutable en dist/VentaLocal/VentaLocal"
