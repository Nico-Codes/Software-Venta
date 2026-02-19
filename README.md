# BUEN TRAGO (Windows)

Sistema de gestion para almacen/vinoteca, local y offline, enfocado en uso rapido de mostrador.

## Estado actual

- Plataforma objetivo: **Windows**
- Interfaz: **Tauri + React**
- Base de datos: **SQLite local**
- Instalador: **NSIS setup + MSI**

## Ejecutar en desarrollo (Windows)

1. Instalar Node.js 20+ y Rust.
2. Abrir terminal en `venta_tauri`.
3. Ejecutar:

```powershell
npm install
npm run tauri:dev
```

## Generar instalador Windows

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_windows_installer.ps1
```

Salida:

- `dist/installers/windows/BUEN TRAGO_*_x64-setup.exe`
- `dist/installers/windows/BUEN TRAGO_*_x64_en-US.msi`

## Version visible en app

La version se muestra en:

- Login
- Sidebar
- Topbar

Cada cambio de release incrementa version.

## Credenciales por defecto

- `admin / admin`
- `usuario / usuario`

## Actualizaciones

Script para empaquetar actualizacion Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/crear_actualizacion.ps1
```

Genera carpeta `actualizacion_N` con instalador Windows y guia de instalacion.
