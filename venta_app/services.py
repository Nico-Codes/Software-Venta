from __future__ import annotations

import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .database import Database
from .pricing import calculate_auto_price
from .ticketing import (
    build_ticket_path,
    build_ticket_text,
    copy_ticket_file,
    print_ticket_file,
    save_ticket_file,
)


class ValidationError(Exception):
    pass


class WarehouseService:
    PAYMENT_METHODS = (
        "Efectivo",
        "Debito",
        "Credito",
        "Transferencia",
        "Cuenta corriente",
    )

    def __init__(self, db: Database) -> None:
        self.db = db
        self.bootstrap_defaults()

    def bootstrap_defaults(self) -> None:
        if self.get_setting("rounding_base") is None:
            self.set_setting("rounding_base", "100")
        if self.get_setting("store_name") is None:
            self.set_setting("store_name", "Mi Almacen / Vinoteca")
        if self.get_setting("store_address") is None:
            self.set_setting("store_address", "")
        if self.get_setting("store_phone") is None:
            self.set_setting("store_phone", "")
        if self.get_setting("ticket_footer") is None:
            self.set_setting("ticket_footer", "Gracias por su compra")

        if not self.list_categories():
            self.create_category("Vinos", 30)
            self.create_category("Gaseosas", 35)
            self.create_category("Papel higienico", 50)

    def get_setting(self, key: str) -> str | None:
        row = self.db.query_one("SELECT value FROM settings WHERE key = ?", (key,))
        return row["value"] if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.db.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, str(value)),
        )

    def get_rounding_base(self) -> int:
        value = self.get_setting("rounding_base")
        return int(value) if value else 100

    def set_rounding_base(self, base: int) -> None:
        if base <= 0:
            raise ValidationError("La base de redondeo debe ser mayor a cero")
        if base % 100 != 0:
            raise ValidationError("La base de redondeo debe ser multiplo de 100")

        self.set_setting("rounding_base", str(base))
        self.recalculate_all_auto_prices()

    def data_dir(self) -> Path:
        return self.db.db_path.parent

    def get_ticket_config(self) -> dict[str, str]:
        return {
            "store_name": self.get_setting("store_name") or "Mi Almacen / Vinoteca",
            "store_address": self.get_setting("store_address") or "",
            "store_phone": self.get_setting("store_phone") or "",
            "ticket_footer": self.get_setting("ticket_footer") or "Gracias por su compra",
        }

    def set_ticket_config(
        self,
        *,
        store_name: str,
        store_address: str,
        store_phone: str,
        ticket_footer: str,
    ) -> None:
        clean_store_name = store_name.strip()
        clean_footer = ticket_footer.strip()
        if not clean_store_name:
            raise ValidationError("El nombre del comercio es obligatorio")
        if not clean_footer:
            raise ValidationError("El pie del ticket es obligatorio")

        self.set_setting("store_name", clean_store_name)
        self.set_setting("store_address", store_address.strip())
        self.set_setting("store_phone", store_phone.strip())
        self.set_setting("ticket_footer", clean_footer)

    def list_categories(self) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            "SELECT id, name, margin_percent, created_at FROM categories ORDER BY name"
        )
        return [dict(row) for row in rows]

    def create_category(self, name: str, margin_percent: float) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("El nombre de la categoria es obligatorio")
        if margin_percent < 0:
            raise ValidationError("El margen no puede ser negativo")

        try:
            cur = self.db.execute(
                "INSERT INTO categories(name, margin_percent) VALUES (?, ?)",
                (clean_name, margin_percent),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Ya existe una categoria con ese nombre") from exc

        self.recalculate_auto_prices_for_category(cur.lastrowid)
        return int(cur.lastrowid)

    def update_category(self, category_id: int, name: str, margin_percent: float) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("El nombre de la categoria es obligatorio")
        if margin_percent < 0:
            raise ValidationError("El margen no puede ser negativo")

        try:
            cur = self.db.execute(
                """
                UPDATE categories
                SET name = ?, margin_percent = ?
                WHERE id = ?
                """,
                (clean_name, margin_percent, category_id),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Ya existe una categoria con ese nombre") from exc

        if cur.rowcount == 0:
            raise ValidationError("Categoria no encontrada")

        self.recalculate_auto_prices_for_category(category_id)

    def delete_category(self, category_id: int) -> None:
        in_use = self.db.query_one(
            "SELECT COUNT(*) AS total FROM products WHERE category_id = ?",
            (category_id,),
        )
        if in_use and in_use["total"] > 0:
            raise ValidationError("No se puede eliminar: la categoria tiene productos asociados")

        cur = self.db.execute("DELETE FROM categories WHERE id = ?", (category_id,))
        if cur.rowcount == 0:
            raise ValidationError("Categoria no encontrada")

    def _get_category_margin(self, category_id: int) -> float:
        row = self.db.query_one(
            "SELECT margin_percent FROM categories WHERE id = ?",
            (category_id,),
        )
        if not row:
            raise ValidationError("Categoria no encontrada")
        return float(row["margin_percent"])

    def list_products(self, search: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        params: list[Any] = []

        if not include_inactive:
            conditions.append("p.active = 1")

        if search.strip():
            conditions.append("(p.name LIKE ? OR p.barcode LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        rows = self.db.query_all(
            f"""
            SELECT
                p.id,
                p.name,
                p.barcode,
                p.category_id,
                c.name AS category_name,
                c.margin_percent,
                p.cost,
                p.sale_price,
                p.auto_price,
                p.stock,
                p.min_stock,
                p.active,
                p.updated_at
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE {' AND '.join(conditions)}
            ORDER BY p.name
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    def search_products_by_name(self, term: str, limit: int = 25) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT id, name, barcode, sale_price, stock
            FROM products
            WHERE active = 1 AND name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (f"%{term.strip()}%", limit),
        )
        return [dict(row) for row in rows]

    def get_product_by_barcode(self, barcode: str) -> dict[str, Any] | None:
        row = self.db.query_one(
            """
            SELECT p.*, c.name AS category_name, c.margin_percent
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.active = 1 AND p.barcode = ?
            """,
            (barcode.strip(),),
        )
        return dict(row) if row else None

    def get_product(self, product_id: int) -> dict[str, Any]:
        row = self.db.query_one(
            """
            SELECT p.*, c.margin_percent, c.name AS category_name
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.id = ?
            """,
            (product_id,),
        )
        if not row:
            raise ValidationError("Producto no encontrado")
        return dict(row)

    def create_product(
        self,
        *,
        name: str,
        barcode: str,
        category_id: int,
        cost: float,
        sale_price: float,
        stock: float,
        min_stock: float,
        auto_price: bool,
    ) -> int:
        clean_name = name.strip()
        clean_barcode = barcode.strip()

        if not clean_name:
            raise ValidationError("El nombre del producto es obligatorio")
        if cost < 0:
            raise ValidationError("El costo no puede ser negativo")
        if stock < 0:
            raise ValidationError("El stock inicial no puede ser negativo")
        if min_stock < 0:
            raise ValidationError("El stock minimo no puede ser negativo")

        margin = self._get_category_margin(category_id)
        final_price = sale_price
        if auto_price:
            final_price = calculate_auto_price(cost, margin, self.get_rounding_base())

        if final_price < 0:
            raise ValidationError("El precio de venta no puede ser negativo")

        try:
            cur = self.db.execute(
                """
                INSERT INTO products(
                    name, barcode, category_id, cost, sale_price,
                    auto_price, stock, min_stock
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    clean_name,
                    clean_barcode or None,
                    category_id,
                    cost,
                    final_price,
                    1 if auto_price else 0,
                    stock,
                    min_stock,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("El codigo de barras ya existe") from exc

        return int(cur.lastrowid)

    def update_product(
        self,
        product_id: int,
        *,
        name: str,
        barcode: str,
        category_id: int,
        cost: float,
        sale_price: float,
        stock: float,
        min_stock: float,
        auto_price: bool,
        active: bool,
    ) -> None:
        clean_name = name.strip()
        clean_barcode = barcode.strip()

        if not clean_name:
            raise ValidationError("El nombre del producto es obligatorio")
        if cost < 0:
            raise ValidationError("El costo no puede ser negativo")
        if stock < 0:
            raise ValidationError("El stock no puede ser negativo")
        if min_stock < 0:
            raise ValidationError("El stock minimo no puede ser negativo")

        margin = self._get_category_margin(category_id)
        final_price = sale_price
        if auto_price:
            final_price = calculate_auto_price(cost, margin, self.get_rounding_base())

        if final_price < 0:
            raise ValidationError("El precio de venta no puede ser negativo")

        current = self.get_product(product_id)
        manual_delta = stock - float(current["stock"])

        try:
            with self.db.transaction() as conn:
                cur = conn.execute(
                    """
                    UPDATE products
                    SET
                        name = ?,
                        barcode = ?,
                        category_id = ?,
                        cost = ?,
                        sale_price = ?,
                        auto_price = ?,
                        stock = ?,
                        min_stock = ?,
                        active = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        clean_name,
                        clean_barcode or None,
                        category_id,
                        cost,
                        final_price,
                        1 if auto_price else 0,
                        stock,
                        min_stock,
                        1 if active else 0,
                        product_id,
                    ),
                )
                if cur.rowcount == 0:
                    raise ValidationError("Producto no encontrado")

                if abs(manual_delta) > 1e-9:
                    conn.execute(
                        """
                        INSERT INTO stock_movements(
                            product_id, movement_type, quantity, stock_before,
                            stock_after, unit_cost, reference_type, reference_id, note
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            product_id,
                            "adjustment",
                            manual_delta,
                            current["stock"],
                            stock,
                            cost,
                            "product_edit",
                            product_id,
                            "Ajuste desde ficha de producto",
                        ),
                    )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("El codigo de barras ya existe") from exc

    def recalculate_auto_prices_for_category(self, category_id: int) -> None:
        category = self.db.query_one(
            "SELECT margin_percent FROM categories WHERE id = ?",
            (category_id,),
        )
        if not category:
            return

        margin = float(category["margin_percent"])
        round_base = self.get_rounding_base()

        rows = self.db.query_all(
            "SELECT id, cost FROM products WHERE category_id = ? AND auto_price = 1",
            (category_id,),
        )

        for row in rows:
            new_price = calculate_auto_price(float(row["cost"]), margin, round_base)
            self.db.execute(
                "UPDATE products SET sale_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_price, row["id"]),
            )

    def recalculate_all_auto_prices(self) -> None:
        rows = self.db.query_all(
            """
            SELECT p.id, p.cost, c.margin_percent
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE p.auto_price = 1
            """
        )
        round_base = self.get_rounding_base()

        for row in rows:
            new_price = calculate_auto_price(float(row["cost"]), float(row["margin_percent"]), round_base)
            self.db.execute(
                "UPDATE products SET sale_price = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_price, row["id"]),
            )

    def register_stock_movement(
        self,
        *,
        product_id: int,
        movement_type: str,
        quantity: float,
        note: str = "",
        unit_cost: float | None = None,
        reference_type: str | None = None,
        reference_id: int | None = None,
    ) -> None:
        if quantity == 0:
            raise ValidationError("La cantidad debe ser distinta de cero")

        product = self.get_product(product_id)
        stock_before = float(product["stock"])
        stock_after = stock_before + quantity

        if stock_after < 0:
            raise ValidationError("Stock insuficiente para realizar la operacion")

        new_cost = float(product["cost"])
        if unit_cost is not None and unit_cost >= 0:
            new_cost = unit_cost

        auto_price = bool(product["auto_price"])
        margin = float(product["margin_percent"])
        new_sale_price = float(product["sale_price"])
        if auto_price and unit_cost is not None and unit_cost >= 0:
            new_sale_price = calculate_auto_price(new_cost, margin, self.get_rounding_base())

        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE products
                SET stock = ?, cost = ?, sale_price = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (stock_after, new_cost, new_sale_price, product_id),
            )

            conn.execute(
                """
                INSERT INTO stock_movements(
                    product_id, movement_type, quantity, stock_before,
                    stock_after, unit_cost, reference_type, reference_id, note
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    movement_type,
                    quantity,
                    stock_before,
                    stock_after,
                    unit_cost,
                    reference_type,
                    reference_id,
                    note.strip() or None,
                ),
            )

    def add_purchase(self, product_id: int, quantity: float, unit_cost: float, note: str = "") -> None:
        if quantity <= 0:
            raise ValidationError("La cantidad de compra debe ser mayor a cero")
        if unit_cost < 0:
            raise ValidationError("El costo no puede ser negativo")

        self.register_stock_movement(
            product_id=product_id,
            movement_type="purchase",
            quantity=quantity,
            note=note,
            unit_cost=unit_cost,
            reference_type="purchase",
        )

    def remove_stock_manual(self, product_id: int, quantity: float, note: str = "") -> None:
        if quantity <= 0:
            raise ValidationError("La salida debe ser mayor a cero")

        self.register_stock_movement(
            product_id=product_id,
            movement_type="manual_out",
            quantity=-abs(quantity),
            note=note,
            reference_type="manual",
        )

    def add_stock_manual(self, product_id: int, quantity: float, note: str = "") -> None:
        if quantity <= 0:
            raise ValidationError("La entrada debe ser mayor a cero")

        self.register_stock_movement(
            product_id=product_id,
            movement_type="manual_in",
            quantity=abs(quantity),
            note=note,
            reference_type="manual",
        )

    def adjust_stock(self, product_id: int, new_stock: float, note: str = "") -> None:
        if new_stock < 0:
            raise ValidationError("El stock fisico no puede ser negativo")

        product = self.get_product(product_id)
        delta = new_stock - float(product["stock"])
        if delta == 0:
            return

        self.register_stock_movement(
            product_id=product_id,
            movement_type="adjustment",
            quantity=delta,
            note=note or "Ajuste por conteo fisico",
            reference_type="adjustment",
        )

    def create_sale(self, items: list[dict[str, Any]], payment_method: str, notes: str = "") -> dict[str, Any]:
        if not items:
            raise ValidationError("No hay productos en el carrito")

        method = payment_method.strip()
        if not method:
            raise ValidationError("La forma de pago es obligatoria")

        sold_at = datetime.now().isoformat(timespec="seconds")

        with self.db.transaction() as conn:
            sale_cur = conn.execute(
                "INSERT INTO sales(sold_at, payment_method, total, notes) VALUES (?, ?, ?, ?)",
                (sold_at, method, 0, notes.strip() or None),
            )
            sale_id = int(sale_cur.lastrowid)
            total = 0.0

            for item in items:
                product_id = int(item["product_id"])
                quantity = float(item["quantity"])
                if quantity <= 0:
                    raise ValidationError("Las cantidades deben ser mayores a cero")

                product = conn.execute(
                    """
                    SELECT p.id, p.name, p.stock, p.cost, p.sale_price
                    FROM products p
                    WHERE p.id = ? AND p.active = 1
                    """,
                    (product_id,),
                ).fetchone()

                if not product:
                    raise ValidationError("Producto no encontrado o inactivo")

                stock_before = float(product["stock"])
                stock_after = stock_before - quantity
                if stock_after < 0:
                    raise ValidationError(f"Stock insuficiente para {product['name']}")

                unit_price = float(product["sale_price"])
                subtotal = unit_price * quantity
                total += subtotal

                conn.execute(
                    "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (stock_after, product_id),
                )

                conn.execute(
                    """
                    INSERT INTO sale_items(
                        sale_id, product_id, product_name, quantity,
                        unit_price, subtotal, cost_at_sale
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        product_id,
                        product["name"],
                        quantity,
                        unit_price,
                        subtotal,
                        float(product["cost"]),
                    ),
                )

                conn.execute(
                    """
                    INSERT INTO stock_movements(
                        product_id, movement_type, quantity, stock_before,
                        stock_after, unit_cost, reference_type, reference_id, note
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        product_id,
                        "sale",
                        -quantity,
                        stock_before,
                        stock_after,
                        float(product["cost"]),
                        "sale",
                        sale_id,
                        "Venta POS",
                    ),
                )

            conn.execute("UPDATE sales SET total = ? WHERE id = ?", (total, sale_id))

        return {
            "sale_id": sale_id,
            "sold_at": sold_at,
            "total": total,
            "payment_method": method,
        }

    def get_sale(self, sale_id: int) -> dict[str, Any]:
        row = self.db.query_one(
            """
            SELECT id, sold_at, payment_method, total, notes
            FROM sales
            WHERE id = ?
            """,
            (sale_id,),
        )
        if not row:
            raise ValidationError("Venta no encontrada")
        return dict(row)

    def get_sale_items(self, sale_id: int) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT product_id, product_name, quantity, unit_price, subtotal, cost_at_sale
            FROM sale_items
            WHERE sale_id = ?
            ORDER BY id ASC
            """,
            (sale_id,),
        )
        return [dict(row) for row in rows]

    def create_sale_ticket(self, sale_id: int) -> dict[str, Any]:
        sale = self.get_sale(sale_id)
        items = self.get_sale_items(sale_id)
        config = self.get_ticket_config()

        text = build_ticket_text(sale=sale, items=items, ticket_config=config)
        path = build_ticket_path(self.data_dir(), sale_id)
        save_ticket_file(path, text)
        return {"path": str(path), "text": text}

    def print_sale_ticket(self, sale_id: int) -> dict[str, Any]:
        ticket = self.create_sale_ticket(sale_id)
        print_ticket_file(Path(ticket["path"]))
        return ticket

    def export_sale_ticket(self, sale_id: int, destination_path: str) -> str:
        ticket = self.create_sale_ticket(sale_id)
        source = Path(ticket["path"])
        destination = Path(destination_path)
        copy_ticket_file(source, destination)
        return str(destination)

    def list_stock_movements(self, limit: int = 300) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT
                m.id,
                m.created_at,
                m.movement_type,
                m.quantity,
                m.stock_before,
                m.stock_after,
                m.note,
                m.reference_type,
                m.reference_id,
                p.name AS product_name,
                p.barcode
            FROM stock_movements m
            JOIN products p ON p.id = m.product_id
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def get_low_stock_products(self) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT p.id, p.name, p.stock, p.min_stock, p.barcode
            FROM products p
            WHERE p.active = 1 AND p.stock <= p.min_stock
            ORDER BY p.stock ASC, p.name ASC
            """
        )
        return [dict(row) for row in rows]

    def get_dashboard_metrics(self) -> dict[str, Any]:
        total_products = self.db.query_one(
            "SELECT COUNT(*) AS total FROM products WHERE active = 1"
        )["total"]

        low_stock = self.db.query_one(
            "SELECT COUNT(*) AS total FROM products WHERE active = 1 AND stock <= min_stock"
        )["total"]

        today_sales = self.db.query_one(
            """
            SELECT COALESCE(SUM(total), 0) AS total
            FROM sales
            WHERE date(sold_at) = date('now', 'localtime')
            """
        )["total"]

        month_sales = self.db.query_one(
            """
            SELECT COALESCE(SUM(total), 0) AS total
            FROM sales
            WHERE strftime('%Y-%m', sold_at) = strftime('%Y-%m', 'now', 'localtime')
            """
        )["total"]

        return {
            "total_products": int(total_products),
            "low_stock_products": int(low_stock),
            "today_sales_total": float(today_sales),
            "month_sales_total": float(month_sales),
        }

    def get_sales_summary(self, days: int = 30) -> dict[str, Any]:
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        summary = self.db.query_one(
            """
            SELECT
                COALESCE(SUM(s.total), 0) AS revenue,
                COALESCE(SUM(si.quantity), 0) AS units,
                COALESCE(SUM(si.subtotal - (si.cost_at_sale * si.quantity)), 0) AS gross_profit,
                COUNT(DISTINCT s.id) AS tickets
            FROM sales s
            LEFT JOIN sale_items si ON si.sale_id = s.id
            WHERE date(s.sold_at) >= date(?)
            """,
            (start_date,),
        )

        return {
            "revenue": float(summary["revenue"]),
            "units": float(summary["units"]),
            "gross_profit": float(summary["gross_profit"]),
            "tickets": int(summary["tickets"]),
            "from": start_date,
            "to": date.today().isoformat(),
            "days": days,
        }

    def get_top_products(self, limit: int = 10, ascending: bool = False) -> list[dict[str, Any]]:
        direction = "ASC" if ascending else "DESC"
        rows = self.db.query_all(
            f"""
            SELECT
                si.product_id,
                si.product_name,
                SUM(si.quantity) AS units,
                SUM(si.subtotal) AS revenue
            FROM sale_items si
            GROUP BY si.product_id, si.product_name
            ORDER BY units {direction}, revenue {direction}
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in rows]

    def get_sales_series(self, days: int = 14) -> list[dict[str, Any]]:
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        rows = self.db.query_all(
            """
            SELECT
                date(sold_at) AS day,
                COALESCE(SUM(total), 0) AS total
            FROM sales
            WHERE date(sold_at) >= date(?)
            GROUP BY date(sold_at)
            ORDER BY day ASC
            """,
            (start_date,),
        )

        totals_by_day = {row["day"]: float(row["total"]) for row in rows}
        series: list[dict[str, Any]] = []

        for idx in range(days):
            current_day = (date.today() - timedelta(days=days - 1 - idx)).isoformat()
            series.append({"day": current_day, "total": totals_by_day.get(current_day, 0.0)})

        return series
