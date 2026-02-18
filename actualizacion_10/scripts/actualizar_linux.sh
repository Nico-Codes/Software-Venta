#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_UPDATE_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

PROJECT_DIR="${HOME}/Downloads/Software Venta"
UPDATE_ROOT="$DEFAULT_UPDATE_ROOT"
PATCH_FILE="${UPDATE_ROOT}/venta_app/ui/main_window.py"
UI_MODE="auto" # auto | python | tauri
RUNTIME_MODE=""
REBUILD=0
CREATE_SHORTCUT=0
CREATE_SHORTCUT_GLOBAL=0
CREATE_DESKTOP_ICON=0
RUN_APP=1

TAURI_ROOT_REL="venta_tauri"
TAURI_BIN_REL="venta_tauri/src-tauri/target/release/venta_tauri"

usage() {
  cat <<'EOF'
Uso:
  bash scripts/actualizar_linux.sh [opciones]

Opciones:
  --project-dir <ruta>    Ruta local del proyecto.
                          Default: ~/Downloads/Software Venta
  --update-root <ruta>    Carpeta actualizacion_N en pendrive.
                          Default: carpeta padre del propio script
  --patch-file <ruta>     Ruta fallback para main_window.py
                          (si update-root no trae archivos de codigo)
  --ui <auto|python|tauri>
                          Runtime de UI a usar:
                            auto   = prioriza Tauri/React si esta disponible
                            python = fuerza UI PySide
                            tauri  = fuerza UI Tauri/React
  --rebuild               Recompila runtime activo (Python o Tauri)
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

tauri_root_path() {
  printf '%s' "${PROJECT_DIR}/${TAURI_ROOT_REL}"
}

tauri_release_dir_path() {
  printf '%s' "${PROJECT_DIR}/venta_tauri/src-tauri/target/release"
}

find_tauri_binary() {
  local release_dir
  release_dir="$(tauri_release_dir_path)"

  if [[ ! -d "$release_dir" ]]; then
    return 1
  fi

  local candidate_names=("venta_tauri" "alto-trago" "ALTO TRAGO" "ALTO_TRAGO")
  local name
  for name in "${candidate_names[@]}"; do
    local candidate_path="${release_dir}/${name}"
    if [[ -x "$candidate_path" ]]; then
      printf '%s' "$candidate_path"
      return 0
    fi
  done

  local discovered
  discovered="$(
    find "$release_dir" -maxdepth 1 -type f -perm -111 \
      ! -name "*.so" \
      ! -name "*.d" \
      ! -name "*.rlib" \
      ! -name "*.a" \
      ! -name "*.o" \
      ! -name "build-script-*" \
      ! -name "rustc-*" \
      | head -n 1
  )"

  if [[ -n "$discovered" ]]; then
    printf '%s' "$discovered"
    return 0
  fi

  return 1
}

tauri_binary_path() {
  local discovered
  discovered="$(find_tauri_binary || true)"
  if [[ -n "$discovered" ]]; then
    printf '%s' "$discovered"
    return 0
  fi
  printf '%s' "${PROJECT_DIR}/${TAURI_BIN_REL}"
}

python_binary_path() {
  printf '%s' "${PROJECT_DIR}/dist/VentaLocal/VentaLocal"
}

python_venv_path() {
  printf '%s' "${PROJECT_DIR}/.venv/bin/python"
}

python_main_path() {
  printf '%s' "${PROJECT_DIR}/main.py"
}

resolve_runtime_mode() {
  local tauri_root
  local tauri_bin
  tauri_root="$(tauri_root_path)"
  tauri_bin="$(find_tauri_binary || true)"

  case "$UI_MODE" in
    python)
      echo "python"
      ;;
    tauri)
      echo "tauri"
      ;;
    auto)
      if [[ -n "$tauri_bin" && -x "$tauri_bin" ]]; then
        echo "tauri"
      elif [[ -d "$tauri_root" && -f "$tauri_root/package.json" ]]; then
        if command -v npm >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
          echo "tauri"
        else
          echo "python"
        fi
      else
        echo "python"
      fi
      ;;
    *)
      echo "python"
      ;;
  esac
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
  local runtime_mode="$1"
  local desktop_dir="${HOME}/.local/share/applications"
  local desktop_file="${desktop_dir}/alto-trago.desktop"
  local exec_line=""

  mkdir -p "$desktop_dir"

  if [[ "$runtime_mode" == "tauri" ]]; then
    local tauri_bin
    local db_path
    tauri_bin="$(tauri_binary_path)"
    db_path="${PROJECT_DIR}/data/venta_local.db"
    if [[ ! -x "$tauri_bin" ]]; then
      echo "No se pudo crear acceso directo Tauri: no existe binario en $tauri_bin" >&2
      return 1
    fi
    exec_line="env VENTA_DB_PATH=$(escape_desktop_path "$db_path") $(escape_desktop_path "$tauri_bin")"
  else
    local binary_path
    local py_path
    local main_path
    binary_path="$(python_binary_path)"
    py_path="$(python_venv_path)"
    main_path="$(python_main_path)"
    if [[ -x "$binary_path" ]]; then
      exec_line="$(escape_desktop_path "$binary_path")"
    else
      if [[ ! -x "$py_path" || ! -f "$main_path" ]]; then
        echo "No se pudo crear acceso directo: falta binario y no hay runtime Python valido." >&2
        return 1
      fi
      exec_line="$(escape_desktop_path "$py_path") $(escape_desktop_path "$main_path")"
    fi
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
  echo "Launcher actual: $(grep '^Exec=' "$desktop_file" || true)"

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
      ! -name "*.txt" \
      ! -name ".goutputstream-*" \
      ! -name "Thumbs.db"
  )

  if [[ "$copied" -gt 0 ]]; then
    echo "Archivos de actualizacion aplicados: $copied"
    return 0
  fi

  return 1
}

ensure_python_runtime() {
  cd "$PROJECT_DIR"
  if [[ ! -d ".venv" ]]; then
    python3 -m venv .venv
  fi
  # shellcheck source=/dev/null
  source .venv/bin/activate
  python -m py_compile main.py
  if [[ -f "venta_app/ui/main_window.py" ]]; then
    python -m py_compile venta_app/ui/main_window.py
  fi
}

ensure_tauri_runtime() {
  local force_build="${1:-0}"
  local tauri_root
  local tauri_bin
  tauri_root="$(tauri_root_path)"
  tauri_bin="$(find_tauri_binary || true)"

  if [[ ! -d "$tauri_root" || ! -f "$tauri_root/package.json" ]]; then
    echo "No se encontro proyecto Tauri en: $tauri_root" >&2
    return 1
  fi

  if [[ "$force_build" -eq 1 || -z "$tauri_bin" || ! -x "$tauri_bin" ]]; then
    if ! command -v npm >/dev/null 2>&1; then
      echo "npm no esta instalado. Instala Node.js para compilar Tauri." >&2
      return 1
    fi
    if ! command -v cargo >/dev/null 2>&1; then
      echo "cargo no esta instalado. Instala Rust para compilar Tauri." >&2
      return 1
    fi
    (
      cd "$tauri_root"
      if [[ ! -d "node_modules" ]]; then
        npm install
      fi
      npm run tauri:build
    )
  fi

  tauri_bin="$(find_tauri_binary || true)"
  if [[ -z "$tauri_bin" || ! -x "$tauri_bin" ]]; then
    echo "No se encontro binario Tauri compilado en target/release." >&2
    echo "Ruta esperada por defecto: ${PROJECT_DIR}/${TAURI_BIN_REL}" >&2
    return 1
  fi

  echo "Binario Tauri detectado: $tauri_bin"

  return 0
}

run_runtime() {
  local runtime_mode="$1"
  cd "$PROJECT_DIR"

  if [[ "$runtime_mode" == "tauri" ]]; then
    local tauri_bin
    local db_path
    tauri_bin="$(tauri_binary_path)"
    db_path="${PROJECT_DIR}/data/venta_local.db"
    if [[ ! -x "$tauri_bin" ]]; then
      echo "No se puede iniciar Tauri: binario inexistente en $tauri_bin" >&2
      return 1
    fi
    VENTA_DB_PATH="$db_path" "$tauri_bin"
    return
  fi

  # shellcheck source=/dev/null
  source .venv/bin/activate
  python main.py
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
    --ui)
      UI_MODE="$2"
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

if [[ "$UI_MODE" != "auto" && "$UI_MODE" != "python" && "$UI_MODE" != "tauri" ]]; then
  echo "Valor invalido para --ui: $UI_MODE (usa auto, python o tauri)." >&2
  exit 1
fi

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "No existe el proyecto: $PROJECT_DIR" >&2
  exit 1
fi

if [[ ! -d "$UPDATE_ROOT" ]]; then
  echo "No existe update-root: $UPDATE_ROOT" >&2
  exit 1
fi

echo "Proyecto local: $PROJECT_DIR"
echo "Carpeta actualizacion: $UPDATE_ROOT"
echo "Modo UI solicitado: $UI_MODE"

echo "[1/6] Cerrando app si esta abierta..."
pkill -f "main.py|VentaLocal|venta_tauri|alto-trago" 2>/dev/null || true

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
  local_target_file="${PROJECT_DIR}/venta_app/ui/main_window.py"
  if [[ ! -f "$PATCH_FILE" || ! -f "$local_target_file" ]]; then
    echo "No hay archivos de codigo en update-root y tampoco existe fallback usable." >&2
    exit 1
  fi
  cp "$local_target_file" "${local_target_file}.bak_${TS}"
  cp "$PATCH_FILE" "$local_target_file"
  echo "Aplicado fallback patch-file: $PATCH_FILE"
fi

echo "[4/6] Validando runtime..."
RUNTIME_MODE="$(resolve_runtime_mode)"
echo "Modo UI efectivo: $RUNTIME_MODE"

if [[ "$RUNTIME_MODE" == "tauri" ]]; then
  if ! ensure_tauri_runtime 0; then
    if [[ "$UI_MODE" == "auto" ]]; then
      echo "Tauri no disponible en este entorno. Fallback a Python."
      RUNTIME_MODE="python"
    else
      exit 1
    fi
  fi
fi

if [[ "$RUNTIME_MODE" == "python" ]]; then
  ensure_python_runtime
fi

if [[ "$REBUILD" -eq 1 ]]; then
  if [[ "$RUNTIME_MODE" == "tauri" ]]; then
    echo "[5/6] Recompilando Tauri Linux..."
    ensure_tauri_runtime 1
  else
    echo "[5/6] Recompilando binario Python Linux..."
    cd "$PROJECT_DIR"
    chmod +x scripts/build_linux.sh
    ./scripts/build_linux.sh
  fi
else
  echo "[5/6] Rebuild omitido (usa --rebuild para compilar runtime activo)."
fi

if [[ "$CREATE_SHORTCUT" -eq 1 ]]; then
  echo "[6/7] Creando/actualizando acceso directo..."
  create_or_update_shortcut "$RUNTIME_MODE"
  if [[ "$CREATE_DESKTOP_ICON" -eq 1 ]]; then
    create_or_update_desktop_icon
  fi
  if [[ "$RUN_APP" -eq 1 ]]; then
    echo "[7/7] Iniciando app..."
    run_runtime "$RUNTIME_MODE"
  else
    echo "[7/7] Listo. No se ejecuto la app (--no-run)."
  fi
  exit 0
fi

if [[ "$RUN_APP" -eq 1 ]]; then
  echo "[6/6] Iniciando app..."
  run_runtime "$RUNTIME_MODE"
else
  echo "[6/6] Listo. No se ejecuto la app (--no-run)."
fi
