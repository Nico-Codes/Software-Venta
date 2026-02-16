from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


def _format_money(value: float) -> str:
    formatted = f"{value:,.2f}"
    formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
    return f"$ {formatted}"


def _format_qty(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".")


def _fit(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 1:
        return value[:width]
    return value[: width - 1] + "~"


def _center(value: str, width: int) -> str:
    return value.center(width)[:width]


def build_ticket_text(
    sale: dict[str, Any],
    items: list[dict[str, Any]],
    ticket_config: dict[str, str],
    width: int = 42,
) -> str:
    now_label = datetime.now().strftime("%d/%m/%Y %H:%M")

    store_name = ticket_config.get("store_name", "ALMACEN / VINOTECA").strip() or "ALMACEN / VINOTECA"
    store_address = ticket_config.get("store_address", "").strip()
    store_phone = ticket_config.get("store_phone", "").strip()
    footer = ticket_config.get("ticket_footer", "Gracias por su compra").strip() or "Gracias por su compra"

    lines: list[str] = []
    lines.append(_center(store_name.upper(), width))
    if store_address:
        lines.append(_center(store_address, width))
    if store_phone:
        lines.append(_center(f"Tel: {store_phone}", width))

    lines.append("-" * width)
    lines.append(_fit(f"Ticket: {sale['id']}", width))
    lines.append(_fit(f"Fecha : {sale['sold_at']}", width))
    lines.append(_fit(f"Emitido: {now_label}", width))
    lines.append(_fit(f"Pago  : {sale['payment_method']}", width))
    lines.append("-" * width)

    for item in items:
        name = str(item.get("product_name", ""))
        qty = _format_qty(float(item.get("quantity", 0)))
        unit = _format_money(float(item.get("unit_price", 0)))
        subtotal = _format_money(float(item.get("subtotal", 0)))

        lines.append(_fit(name, width))
        detail = f"{qty} x {unit}"
        spacing = width - len(detail) - len(subtotal)
        if spacing < 1:
            spacing = 1
        lines.append(f"{detail}{' ' * spacing}{subtotal}")

    lines.append("-" * width)
    total_label = _format_money(float(sale.get("total", 0)))
    prefix = "TOTAL"
    spacing = width - len(prefix) - len(total_label)
    if spacing < 1:
        spacing = 1
    lines.append(f"{prefix}{' ' * spacing}{total_label}")
    lines.append("-" * width)
    lines.append(_center(footer, width))

    return "\n".join(lines) + "\n"


def build_ticket_path(base_dir: Path, sale_id: int) -> Path:
    ticket_dir = base_dir / "tickets"
    ticket_dir.mkdir(parents=True, exist_ok=True)
    return ticket_dir / f"ticket_{sale_id:08d}.txt"


def save_ticket_file(path: Path, ticket_text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(ticket_text, encoding="utf-8")
    return path


def copy_ticket_file(source_path: Path, destination_path: Path) -> Path:
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source_path, destination_path)
    return destination_path


def print_ticket_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"No existe el archivo de ticket: {path}")

    system = platform.system().lower()
    if "windows" in system:
        os.startfile(str(path), "print")  # type: ignore[attr-defined]
        return

    for command in (["lp", str(path)], ["lpr", str(path)]):
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode == 0:
            return

    raise RuntimeError("No se encontro un comando de impresion (lp/lpr)")
