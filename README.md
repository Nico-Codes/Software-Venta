# Sistema de Gestion para Almacen / Vinoteca

Aplicacion de escritorio local (offline) para Windows y Linux con POS rapido, gestion de productos, categorias con margenes editables, inventario y reportes.

## Funcionalidades implementadas

- Venta POS con escaneo por lector de codigo (funciona como teclado + Enter).
- Busqueda manual de productos por nombre.
- Carrito de venta con total grande y cobro por forma de pago.
- Venta por `Contado` o `Cuenta corriente` con pago parcial y saldo.
- Seleccion de cliente en POS con alerta de deuda y detalle de cuenta.
- POS ultra-rapido:
  - atajos de teclado (`F2` escanear, `F3` buscar, `F4` agregar, `F5` cobrar, `F6` vaciar, `F7` tipo venta).
  - modo `solo scanner` para operar sin mouse.
  - busqueda instantanea por texto.
- Registro historico de ventas y precios vendidos.
- Descuento automatico de stock al vender.
- Sistema de ticket:
  - genera ticket por cada venta y lo guarda en `data/tickets/`.
  - vista previa al cobrar con opcion de imprimir o guardar copia.
  - configuracion editable de comercio (nombre, direccion, telefono, pie).
- Dashboard con graficos de ventas y ganancias, top/menos vendidos, stock bajo y alertas de deuda.
- Gestion de clientes y deuda:
  - detalle de compras, pagos y saldos.
  - registro de pagos a deudas (aplicacion automatica a ventas pendientes).
  - alertas por limite de cliente y limite global configurable.
- Usuarios y permisos:
  - `admin` con acceso total.
  - `vendedor` con acceso a venta POS.
- Respaldo y recuperacion:
  - backup automatico diario configurable.
  - backup manual en un clic.
  - restauracion desde backup.
  - exportacion de todas las tablas a CSV (compatible Excel).
- Gestion de productos:
  - nombre, codigo, categoria, costo, precio, stock, stock minimo.
  - precio automatico por categoria o precio manual.
- Gestion de categorias y margenes (%): alta, edicion y eliminacion.
- Recalculo automatico de precios cuando cambia el margen o el redondeo.
- Redondeo configurable (base por defecto 100).
- Inventario y movimientos:
  - compra (entrada), entrada manual, salida manual, ajuste por conteo fisico.
- Panel principal con alertas de stock bajo.
- Reportes de facturacion, ganancia bruta, mas/menos vendidos y serie diaria.
- Reportes ampliados por metodo de pago y clientes con mayor deuda.

## Stack tecnico

- Python 3.11+
- PySide6 (GUI multiplataforma)
- SQLite (base local en `data/venta_local.db`)

## Instalacion

1. Crear entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

En Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r requirements.txt
```

3. Ejecutar:

```bash
python main.py
```

## Acceso inicial

- Admin: `admin` / `admin123`
- Vendedor: `vendedor` / `venta123`

## Uso rapido

1. Cargar o editar categorias y margenes en `Categorias y margenes`.
2. Crear productos en `Productos`.
3. Vender desde `Venta (POS)` escaneando codigo + Enter.
4. Si la venta es a cuenta corriente, seleccionar cliente y monto pagado.
5. Registrar compras y ajustes en `Inventario` (con escaneo para seleccionar producto).
6. Gestionar deudas y pagos en `Clientes y deudas`.
7. Usar `Respaldo` para backup/restore/export CSV.
8. Revisar indicadores en `Panel` y `Reportes`.

## Pruebas

```bash
python -m unittest discover -s tests -v
```

## Ejecutable

Se genera con PyInstaller en modo `onedir`.

Windows:

```powershell
python scripts\build.py
```

o

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Linux:

```bash
python3 scripts/build.py
```

o

```bash
chmod +x scripts/build_linux.sh
./scripts/build_linux.sh
```

Salida:

- Windows: `dist/VentaLocal/VentaLocal.exe`
- Linux: `dist/VentaLocal/VentaLocal`

## Notas

- El sistema es 100% local y no requiere internet.
- El backup automatico corre al iniciar la app (si esta habilitado).
- Los cambios de margen/redondeo afectan automaticamente a productos con precio automatico.
- El historial de ventas mantiene el precio vendido aunque luego cambie el precio del producto.
- En Linux, para impresion de ticket se requiere `lp` o `lpr` instalado.

## Migracion a interfaz moderna (Tauri + React + Rust)

Se agrego una nueva base de migracion en `venta_tauri/` para reemplazar progresivamente la UI de PySide6.

Estado de esta base:

- Navegacion vertical moderna con foco en `Venta rapida` y `Agregar stock`.
- Rama `Utilidades` con submodulos (dashboard, productos, categorias, inventario, reportes, clientes, usuarios, respaldo).
- Transiciones suaves y estructura visual lista para evolucionar.
- Backend Tauri con comando nativo de prueba (`health_check`).

Para iniciar esta nueva app:

```bash
cd venta_tauri
npm install
npm run tauri:dev
```

Script opcional de setup en Windows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_tauri_windows.ps1
powershell -ExecutionPolicy Bypass -File scripts\setup_tauri_windows.ps1 -InstallVsBuildTools
```

## Release automatica de instaladores (GitHub)

Se configuro el workflow `/.github/workflows/build-installers.yml` para:

- Compilar instaladores de Windows y Linux.
- Publicarlos automaticamente como assets en cada release por tag.

Trigger de release:

- `push` de tag con formato `v*` (ejemplo: `v1.0.0`).

Comandos recomendados:

```bash
git add .github/workflows/build-installers.yml
git commit -m "release: v1.0.0"
git tag v1.0.0
git push origin main --follow-tags
```

Assets que sube automaticamente:

- Windows: `.exe` (NSIS), `.msi`.
- Linux: `.deb`, `.AppImage`, `.rpm` (si se genera en build).
- Checksums SHA256 por plataforma y global.
