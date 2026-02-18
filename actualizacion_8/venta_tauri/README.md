# Venta Modern (Tauri + React + TypeScript)

Este modulo inicia la migracion completa de interfaz a stack moderno desktop:

- Frontend: React + TypeScript + Vite
- Desktop runtime: Tauri v2
- Backend nativo: Rust (comandos Tauri)

## Estado actual

- Shell principal con navegacion vertical
- Secciones base: `Venta rapida`, `Agregar stock`, `Utilidades`
- Transiciones suaves entre vistas
- Estilo moderno orientado a mostrador
- Comando nativo de prueba (`health_check`) conectado

## Prerrequisitos

1. Node.js LTS
2. Rust toolchain (`rustup`, `cargo`)
3. En Windows: Visual Studio Build Tools con componente C++

Si no quieres instalar Node global, puedes usar Node portable local:

```powershell
mkdir .tools
Invoke-WebRequest -Uri https://nodejs.org/dist/v24.13.1/node-v24.13.1-win-x64.zip -OutFile .tools\node.zip
Expand-Archive .tools\node.zip -DestinationPath .tools -Force
$env:PATH = \"$PWD\\.tools\\node-v24.13.1-win-x64;$env:PATH\"
```

## Ejecutar en desarrollo

```bash
cd venta_tauri
npm install
npm run tauri:dev
```

## Build de escritorio

```bash
cd venta_tauri
npm run tauri:build
```

## Siguiente fase

1. Conectar SQLite local desde Rust
2. Migrar casos de uso: ventas, stock, deudas, reportes
3. Reemplazar placeholders por pantallas productivas
4. Empaquetado final con instalador Windows/Linux

## Setup rapido en Windows (global)

```powershell
powershell -ExecutionPolicy Bypass -File ..\\scripts\\setup_tauri_windows.ps1 -InstallVsBuildTools
```
