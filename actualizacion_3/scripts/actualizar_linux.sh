#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_UPDATE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_DIR="${HOME}/Downloads/Software Venta"
UPDATE_ROOT="$DEFAULT_UPDATE_ROOT"
PATCH_FILE="${UPDATE_ROOT}/venta_app/ui/main_window.py"
REBUILD=0
CREATE_SHORTCUT=0
CREATE_SHORTCUT_GLOBAL=0
CREATE_DESKTOP_ICON=0
RUN_APP=1

usage() {
  cat <<'EOF'
Uso:
  bash scripts/actualizar_linux.sh [opciones]

Opciones:
  --project-dir <ruta>    Ruta local del proyecto.
                          Default: ~/Downloads/Software Venta
  --update-root <ruta>    Carpeta actualizacion_N en pendrive.
                          Default: carpeta padre del propio script
  --patch-file <ruta>     Ruta del archivo parcheado main_window.py
                          (Fallback si update-root no trae archivos de codigo)
  --rebuild               Recompila binario Linux con scripts/build_linux.sh
  --shortcut              Crea/actualiza acceso directo ALTO TRAGO en el menu
  --shortcut-global       Copia tambien el acceso directo a /usr/share/applications
  --desktop-icon          Crea/actualiza icono directo en Desktop/Escritorio
  --no-run                No abre la app al finalizar
  -h, --help              Mostrar ayuda
EOF
}

escape_desktop_path() {
  printf '%s' "$1" | sed 's/ /\\ /g'
}

refresh_menu_cache() {
  local desktop_dir="${HOME}/.local/share/applications"
  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$desktop_dir" >/dev/null 2>&1 || true
  fi
  if command -v xdg-desktop-menu >/dev/null 2>&1; then
    xdg-desktop-menu forceupdate >/dev/null 2>&1 || true
  fi
  rm -f "${HOME}/.cache/menus/"* 2>/dev/null || true
  if command -v xfce4-panel >/dev/null 2>&1; then
    xfce4-panel -r >/dev/null 2>&1 || true
  fi
}

create_or_update_shortcut() {
  local desktop_dir="${HOME}/.local/share/applications"
  local desktop_file="${desktop_dir}/alto-trago.desktop"
  local binary_path="${PROJECT_DIR}/dist/VentaLocal/VentaLocal"
  local python_path="${PROJECT_DIR}/.venv/bin/python"
  local main_path="${PROJECT_DIR}/main.py"
  local exec_line=""

  mkdir -p "$desktop_dir"

  if [[ -x "$binary_path" ]]; then
    exec_line="$(escape_desktop_path "$binary_path")"
  else
    if [[ ! -x "$python_path" || ! -f "$main_path" ]]; then
      echo "No se pudo crear acceso directo: falta binario y no hay runtime Python valido." >&2
      return 1
    fi
    exec_line="$(escape_desktop_path "$python_path") $(escape_desktop_path "$main_path")"
  fi

  cat >"$desktop_file" <<EOF
[Desktop Entry]
Version=1.0
Name=ALTO TRAGO
GenericName=Punto de venta
Comment=Gestion de vinoteca
Exec=$exec_line
Icon=applications-office
Terminal=false
Type=Application
Categories=Office;Utility;
Keywords=vinoteca;ventas;pos;stock;
StartupNotify=true
NoDisplay=false
EOF

  chmod 644 "$desktop_file"
  if command -v desktop-file-validate >/dev/null 2>&1; then
    desktop-file-validate "$desktop_file" >/dev/null 2>&1 || true
  fi
  refresh_menu_cache

  echo "Acceso directo actualizado: $desktop_file"

  if [[ "$CREATE_SHORTCUT_GLOBAL" -eq 1 ]]; then
    create_or_update_shortcut_global "$desktop_file"
  fi
}

create_or_update_shortcut_global() {
  local desktop_file_local="$1"
  local desktop_file_global="/usr/share/applications/alto-trago.desktop"

  if ! command -v sudo >/dev/null 2>&1; then
    echo "No se encontro sudo; no se pudo crear acceso directo global." >&2
    return 1
  fi

  sudo cp "$desktop_file_local" "$desktop_file_global"
  sudo chmod 644 "$desktop_file_global"
  if command -v update-desktop-database >/dev/null 2>&1; then
    sudo update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
  fi
  refresh_menu_cache

  echo "Acceso directo global actualizado: $desktop_file_global"
}

create_or_update_desktop_icon() {
  local source_file="${HOME}/.local/share/applications/alto-trago.desktop"
  local targets=()

  if [[ ! -f "$source_file" ]]; then
    echo "No se encontro launcher local para crear icono de escritorio." >&2
    return 1
  fi

  if [[ -d "${HOME}/Desktop" ]]; then
    targets+=("${HOME}/Desktop/ALTO TRAGO.desktop")
  fi
  if [[ -d "${HOME}/Escritorio" ]]; then
    targets+=("${HOME}/Escritorio/ALTO TRAGO.desktop")
  fi
  if [[ ${#targets[@]} -eq 0 ]]; then
    mkdir -p "${HOME}/Desktop"
    targets+=("${HOME}/Desktop/ALTO TRAGO.desktop")
  fi

  for target in "${targets[@]}"; do
    cp "$source_file" "$target"
    chmod +x "$target"
    if command -v gio >/dev/null 2>&1; then
      gio set "$target" metadata::trusted true >/dev/null 2>&1 || true
    fi
    echo "Icono de escritorio actualizado: $target"
  done
}

copy_update_files() {
  local backup_code_dir="$1"
  local copied=0

  while IFS= read -r src; do
    local rel="${src#${UPDATE_ROOT}/}"
    local dst="${PROJECT_DIR}/${rel}"
    local dst_dir
    dst_dir="$(dirname "$dst")"
    mkdir -p "$dst_dir"

    if [[ -f "$dst" ]]; then
      local backup_dst="${backup_code_dir}/${rel}"
      local backup_dir
      backup_dir="$(dirname "$backup_dst")"
      mkdir -p "$backup_dir"
      cp "$dst" "$backup_dst"
    fi

    cp "$src" "$dst"
    copied=$((copied + 1))
    echo "Aplicado: $rel"
  done < <(
    find "$UPDATE_ROOT" -type f \
      ! -path "$UPDATE_ROOT/scripts/*" \
      ! -name "LEEME_*" \
      ! -name "*.txt"
  )

  if [[ "$copied" -gt 0 ]]; then
    echo "Archivos de actualizacion aplicados: $copied"
    return 0
  fi

  return 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --update-root)
      UPDATE_ROOT="$2"
      shift 2
      ;;
    --patch-file)
      PATCH_FILE="$2"
      shift 2
      ;;
    --rebuild)
      REBUILD=1
      shift
      ;;
    --shortcut)
      CREATE_SHORTCUT=1
      shift
      ;;
    --shortcut-global)
      CREATE_SHORTCUT=1
      CREATE_SHORTCUT_GLOBAL=1
      shift
      ;;
    --desktop-icon)
      CREATE_SHORTCUT=1
      CREATE_DESKTOP_ICON=1
      shift
      ;;
    --no-run)
      RUN_APP=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Opcion no reconocida: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "No existe el proyecto: $PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -d "$UPDATE_ROOT" ]]; then
  echo "No existe update-root: $UPDATE_ROOT" >&2
  exit 1
fi

TARGET_FILE="$PROJECT_DIR/venta_app/ui/main_window.py"
if [[ ! -f "$TARGET_FILE" ]]; then
  echo "No existe archivo destino: $TARGET_FILE" >&2
  exit 1
fi

echo "Proyecto local: $PROJECT_DIR"
echo "Carpeta actualizacion: $UPDATE_ROOT"

echo "[1/6] Cerrando app si esta abierta..."
pkill -f "main.py|VentaLocal" 2>/dev/null || true

echo "[2/6] Creando backups de datos..."
BACKUP_DIR="${HOME}/alto-trago-backups"
TS="$(date +%F_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [[ -d "$PROJECT_DIR/data" ]]; then
  tar -czf "$BACKUP_DIR/data_source_${TS}.tar.gz" -C "$PROJECT_DIR" data
fi
if [[ -d "$PROJECT_DIR/dist/VentaLocal/data" ]]; then
  tar -czf "$BACKUP_DIR/data_runtime_${TS}.tar.gz" -C "$PROJECT_DIR/dist/VentaLocal" data
fi
if [[ -d "$PROJECT_DIR/data/tickets" ]]; then
  tar -czf "$BACKUP_DIR/tickets_${TS}.tar.gz" -C "$PROJECT_DIR/data" tickets
fi

echo "[3/6] Aplicando parche..."
BACKUP_CODE_DIR="${BACKUP_DIR}/code_${TS}"
mkdir -p "$BACKUP_CODE_DIR"

if ! copy_update_files "$BACKUP_CODE_DIR"; then
  if [[ ! -f "$PATCH_FILE" ]]; then
    echo "No hay archivos de codigo en update-root y tampoco existe patch-file: $PATCH_FILE" >&2
    exit 1
  fi
  cp "$TARGET_FILE" "${TARGET_FILE}.bak_${TS}"
  cp "$PATCH_FILE" "$TARGET_FILE"
  echo "Aplicado fallback patch-file: $PATCH_FILE"
fi

echo "[4/6] Validando Python..."
cd "$PROJECT_DIR"
if [[ ! -d ".venv" ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m py_compile venta_app/ui/main_window.py

if [[ "$REBUILD" -eq 1 ]]; then
  echo "[5/6] Recompilando binario Linux..."
  chmod +x scripts/build_linux.sh
  ./scripts/build_linux.sh
else
  echo "[5/6] Rebuild omitido (usa --rebuild para compilar binario)."
fi

if [[ "$CREATE_SHORTCUT" -eq 1 ]]; then
  echo "[6/7] Creando/actualizando acceso directo..."
  create_or_update_shortcut
  if [[ "$CREATE_DESKTOP_ICON" -eq 1 ]]; then
    create_or_update_desktop_icon
  fi
  if [[ "$RUN_APP" -eq 1 ]]; then
    echo "[7/7] Iniciando app..."
    python main.py
  else
    echo "[7/7] Listo. No se ejecuto la app (--no-run)."
  fi
  exit 0
fi

if [[ "$RUN_APP" -eq 1 ]]; then
  echo "[6/6] Iniciando app..."
  python main.py
else
  echo "[6/6] Listo. No se ejecuto la app (--no-run)."
fi
