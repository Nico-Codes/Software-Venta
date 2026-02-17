#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TAURI_ROOT="$PROJECT_ROOT/venta_tauri"
TAURI_SRC="$TAURI_ROOT/src-tauri"
BUNDLE_DIR="$TAURI_SRC/target/release/bundle"
OUTPUT_DIR="$PROJECT_ROOT/dist/installers/linux"

if [[ ! -d "$TAURI_ROOT" ]]; then
  echo "No se encontro carpeta venta_tauri en $PROJECT_ROOT" >&2
  exit 1
fi

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "Este script debe ejecutarse en Linux (o en CI Linux)." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm no esta instalado en PATH" >&2
  exit 1
fi

if ! command -v cargo >/dev/null 2>&1; then
  echo "cargo no esta instalado en PATH" >&2
  exit 1
fi

echo "Compilando instaladores Linux (Tauri bundle)..."
cd "$TAURI_ROOT"
npm run tauri:build

mkdir -p "$OUTPUT_DIR"
found=0

if [[ -d "$BUNDLE_DIR/deb" ]]; then
  cp -f "$BUNDLE_DIR"/deb/*.deb "$OUTPUT_DIR"/ 2>/dev/null || true
fi

if [[ -d "$BUNDLE_DIR/appimage" ]]; then
  cp -f "$BUNDLE_DIR"/appimage/*.AppImage "$OUTPUT_DIR"/ 2>/dev/null || true
fi

if [[ -d "$BUNDLE_DIR/rpm" ]]; then
  cp -f "$BUNDLE_DIR"/rpm/*.rpm "$OUTPUT_DIR"/ 2>/dev/null || true
fi

if compgen -G "$OUTPUT_DIR/*" >/dev/null; then
  found=1
fi

if [[ "$found" -ne 1 ]]; then
  echo "No se encontraron instaladores Linux en $BUNDLE_DIR" >&2
  exit 1
fi

echo "Instaladores listos en: $OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"
