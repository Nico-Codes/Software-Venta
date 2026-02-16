# Sistema de Gestion para Almacen / Vinoteca

Aplicacion de escritorio local (offline) para Windows y Linux con POS rapido, gestion de productos, categorias con margenes editables, inventario y reportes.

## Funcionalidades implementadas

- Venta POS con escaneo por lector de codigo (funciona como teclado + Enter).
- Busqueda manual de productos por nombre.
- Carrito de venta con total grande y cobro por forma de pago.
- Registro historico de ventas y precios vendidos.
- Descuento automatico de stock al vender.
- Sistema de ticket:
  - genera ticket por cada venta y lo guarda en `data/tickets/`.
  - vista previa al cobrar con opcion de imprimir o guardar copia.
  - configuracion editable de comercio (nombre, direccion, telefono, pie).
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

## Uso rapido

1. Cargar o editar categorias y margenes en `Categorias y margenes`.
2. Crear productos en `Productos`.
3. Vender desde `Venta (POS)` escaneando codigo + Enter.
4. Registrar compras y ajustes en `Inventario`.
5. Revisar indicadores en `Panel` y `Reportes`.

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
- Los cambios de margen/redondeo afectan automaticamente a productos con precio automatico.
- El historial de ventas mantiene el precio vendido aunque luego cambie el precio del producto.
- En Linux, para impresion de ticket se requiere `lp` o `lpr` instalado.
