from __future__ import annotations

import csv
import hashlib
import hmac
import os
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
        "Credito",
        "Debito",
        "Transferencia",
    )
    USER_ROLES = ("admin", "seller")

    def __init__(self, db: Database) -> None:
        self.db = db
        self.bootstrap_defaults()

    @staticmethod
    def _safe_positive_int(value: int, default: int = 1) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return default
        return parsed if parsed > 0 else default

    def bootstrap_defaults(self) -> None:
        defaults = {
            "rounding_base": "100",
            "store_name": "Mi Almacen / Vinoteca",
            "store_address": "",
            "store_phone": "",
            "ticket_footer": "Gracias por su compra",
            "debt_global_alert_limit": "100000",
            "last_auto_backup_date": "",
            "auto_backup_enabled": "1",
            "auto_backup_keep_days": "30",
        }
        for key, value in defaults.items():
            if self.get_setting(key) is None:
                self.set_setting(key, value)

        if not self.list_categories():
            self.create_category("Vinos", 30)
            self.create_category("Gaseosas", 35)
            self.create_category("Papel higienico", 50)

        self._ensure_default_users()

    # ----------------------
    # Settings
    # ----------------------
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

    def data_dir(self) -> Path:
        return self.db.db_path.parent

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

    def get_debt_global_alert_limit(self) -> float:
        raw = self.get_setting("debt_global_alert_limit")
        return float(raw) if raw else 100000.0

    def set_debt_global_alert_limit(self, amount: float) -> None:
        if amount < 0:
            raise ValidationError("El limite global no puede ser negativo")
        self.set_setting("debt_global_alert_limit", str(amount))

    def backup_dir(self) -> Path:
        path = self.data_dir() / "backups"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _backup_file_name(self, prefix: str = "manual") -> str:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_prefix = prefix.strip().lower().replace(" ", "_") or "manual"
        return f"{safe_prefix}_{stamp}.db"

    def create_backup(self, prefix: str = "manual") -> dict[str, Any]:
        destination = self.backup_dir() / self._backup_file_name(prefix)
        path = self.db.backup_to(destination)
        stat = path.stat()
        return {
            "path": str(path),
            "name": path.name,
            "size_bytes": int(stat.st_size),
            "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "type": prefix,
        }

    def list_backups(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.backup_dir().glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = path.stat()
            prefix = path.stem.split("_", 1)[0] if "_" in path.stem else "manual"
            items.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "size_bytes": int(stat.st_size),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
                    "type": prefix,
                }
            )
        return items

    def restore_database_from_backup(self, source_path: str) -> dict[str, Any]:
        path = Path(source_path)
        if not path.exists():
            raise ValidationError("El archivo de backup no existe")
        restored = self.db.restore_from(path)
        self.db.initialize()
        self.bootstrap_defaults()
        return {"restored_to": str(restored), "source": str(path)}

    def get_auto_backup_settings(self) -> dict[str, Any]:
        enabled = (self.get_setting("auto_backup_enabled") or "1").strip() == "1"
        keep_days_raw = self.get_setting("auto_backup_keep_days") or "30"
        keep_days = max(1, int(float(keep_days_raw)))
        return {
            "enabled": enabled,
            "keep_days": keep_days,
            "last_date": self.get_setting("last_auto_backup_date") or "",
        }

    def set_auto_backup_settings(self, *, enabled: bool, keep_days: int) -> None:
        if keep_days < 1:
            raise ValidationError("Debes conservar al menos 1 dia de backups")
        self.set_setting("auto_backup_enabled", "1" if enabled else "0")
        self.set_setting("auto_backup_keep_days", str(keep_days))

    def cleanup_old_backups(self, keep_days: int) -> int:
        cutoff = datetime.now() - timedelta(days=keep_days)
        removed = 0
        for path in self.backup_dir().glob("*.db"):
            modified = datetime.fromtimestamp(path.stat().st_mtime)
            if modified < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def auto_backup_if_needed(self) -> dict[str, Any] | None:
        settings = self.get_auto_backup_settings()
        if not settings["enabled"]:
            return None

        today_label = date.today().isoformat()
        last_date = str(settings.get("last_date") or "").strip()
        if last_date == today_label:
            self.cleanup_old_backups(int(settings["keep_days"]))
            return None

        backup = self.create_backup(prefix="auto")
        self.set_setting("last_auto_backup_date", today_label)
        removed = self.cleanup_old_backups(int(settings["keep_days"]))
        backup["old_removed"] = removed
        return backup

    def export_all_tables_to_csv(self, destination_dir: str | None = None) -> dict[str, Any]:
        export_dir = Path(destination_dir) if destination_dir else self.data_dir() / "exports" / datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir.mkdir(parents=True, exist_ok=True)

        tables = [
            "categories",
            "products",
            "customers",
            "users",
            "sales",
            "sale_items",
            "payments",
            "stock_movements",
            "settings",
        ]

        written: list[str] = []
        for table in tables:
            rows = self.db.query_all(f"SELECT * FROM {table}")
            csv_path = export_dir / f"{table}.csv"
            with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                if rows:
                    headers = list(rows[0].keys())
                else:
                    pragma = self.db.query_all(f"PRAGMA table_info({table})")
                    headers = [str(col["name"]) for col in pragma]
                writer.writerow(headers)
                for row in rows:
                    writer.writerow([row[h] for h in headers])
            written.append(str(csv_path))

        return {"directory": str(export_dir), "files": written}

    # ----------------------
    # Users and auth
    # ----------------------
    def _hash_password(self, password: str, salt_hex: str | None = None) -> str:
        if not password:
            raise ValidationError("La clave no puede estar vacia")
        salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return f"{salt.hex()}${digest.hex()}"

    def _verify_password(self, password: str, stored_hash: str) -> bool:
        try:
            salt_hex, expected = stored_hash.split("$", 1)
        except ValueError:
            return False
        candidate = self._hash_password(password, salt_hex=salt_hex).split("$", 1)[1]
        return hmac.compare_digest(candidate, expected)

    def _ensure_default_users(self) -> None:
        row = self.db.query_one("SELECT COUNT(*) AS total FROM users")
        if row and int(row["total"]) > 0:
            return
        self.create_user("admin", "admin123", role="admin")
        self.create_user("vendedor", "venta123", role="seller")

    def list_users(self) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT id, username, role, active, created_at, last_login
            FROM users
            ORDER BY username
            """
        )
        return [dict(row) for row in rows]

    def create_user(self, username: str, password: str, role: str = "seller") -> int:
        clean_username = username.strip().lower()
        if not clean_username:
            raise ValidationError("El usuario es obligatorio")
        if role not in self.USER_ROLES:
            raise ValidationError("Rol invalido")

        password_hash = self._hash_password(password)
        try:
            cur = self.db.execute(
                "INSERT INTO users(username, password_hash, role, active) VALUES (?, ?, ?, 1)",
                (clean_username, password_hash, role),
            )
        except sqlite3.IntegrityError as exc:
            raise ValidationError("Ya existe un usuario con ese nombre") from exc
        return int(cur.lastrowid)

    def update_user(self, user_id: int, *, role: str, active: bool, password: str | None = None) -> None:
        if role not in self.USER_ROLES:
            raise ValidationError("Rol invalido")
        current = self.db.query_one("SELECT id, role, active FROM users WHERE id = ?", (user_id,))
        if not current:
            raise ValidationError("Usuario no encontrado")

        current_role = str(current["role"])
        current_active = bool(current["active"])
        would_remove_active_admin = (
            current_role == "admin"
            and current_active
            and not (role == "admin" and active)
        )
        if would_remove_active_admin:
            remaining = self.db.query_one(
                "SELECT COUNT(*) AS total FROM users WHERE role = 'admin' AND active = 1 AND id <> ?",
                (user_id,),
            )
            if remaining and int(remaining["total"]) <= 0:
                raise ValidationError("Debe quedar al menos un administrador activo")

        with self.db.transaction() as conn:
            if password and password.strip():
                password_hash = self._hash_password(password.strip())
                conn.execute(
                    """
                    UPDATE users
                    SET role = ?, active = ?, password_hash = ?
                    WHERE id = ?
                    """,
                    (role, 1 if active else 0, password_hash, user_id),
                )
            else:
                conn.execute(
                    "UPDATE users SET role = ?, active = ? WHERE id = ?",
                    (role, 1 if active else 0, user_id),
                )

    def authenticate_user(self, username: str, password: str) -> dict[str, Any]:
        clean_username = username.strip().lower()
        row = self.db.query_one(
            "SELECT id, username, password_hash, role, active FROM users WHERE username = ?",
            (clean_username,),
        )
        if not row:
            raise ValidationError("Usuario o clave incorrectos")
        if not bool(row["active"]):
            raise ValidationError("Usuario inactivo")
        if not self._verify_password(password, row["password_hash"]):
            raise ValidationError("Usuario o clave incorrectos")

        self.db.execute(
            "UPDATE users SET last_login = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), row["id"]),
        )
        return {"id": int(row["id"]), "username": row["username"], "role": row["role"]}

    # ----------------------
    # Categories
    # ----------------------
    def list_categories(self) -> list[dict[str, Any]]:
        rows = self.db.query_all("SELECT id, name, margin_percent, created_at FROM categories ORDER BY name")
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
        row = self.db.query_one("SELECT margin_percent FROM categories WHERE id = ?", (category_id,))
        if not row:
            raise ValidationError("Categoria no encontrada")
        return float(row["margin_percent"])

    # ----------------------
    # Products
    # ----------------------
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
                p.id, p.name, p.barcode, p.category_id,
                c.name AS category_name, c.margin_percent,
                p.cost, p.sale_price, p.auto_price, p.stock, p.min_stock,
                p.active, p.updated_at
            FROM products p
            JOIN categories c ON c.id = p.category_id
            WHERE {' AND '.join(conditions)}
            ORDER BY p.name
            """,
            tuple(params),
        )
        return [dict(row) for row in rows]

    def search_products_by_name(self, term: str, limit: int = 25) -> list[dict[str, Any]]:
        safe_limit = self._safe_positive_int(limit, default=25)
        rows = self.db.query_all(
            """
            SELECT id, name, barcode, sale_price, stock
            FROM products
            WHERE active = 1 AND name LIKE ?
            ORDER BY name
            LIMIT ?
            """,
            (f"%{term.strip()}%", safe_limit),
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
        if stock <= 0:
            raise ValidationError("El stock inicial debe ser mayor a cero")
        if min_stock < 0:
            raise ValidationError("El stock minimo no puede ser negativo")

        margin = self._get_category_margin(category_id)
        final_price = calculate_auto_price(cost, margin, self.get_rounding_base()) if auto_price else sale_price
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
        final_price = calculate_auto_price(cost, margin, self.get_rounding_base()) if auto_price else sale_price
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
                        name = ?, barcode = ?, category_id = ?,
                        cost = ?, sale_price = ?, auto_price = ?,
                        stock = ?, min_stock = ?, active = ?,
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
        category = self.db.query_one("SELECT margin_percent FROM categories WHERE id = ?", (category_id,))
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

    # ----------------------
    # Customers and debt
    # ----------------------
    def list_customers(self, search: str = "", include_inactive: bool = False) -> list[dict[str, Any]]:
        conditions = ["1 = 1"]
        params: list[Any] = []
        if not include_inactive:
            conditions.append("c.active = 1")
        if search.strip():
            conditions.append("(c.name LIKE ? OR c.phone LIKE ?)")
            term = f"%{search.strip()}%"
            params.extend([term, term])

        rows = self.db.query_all(
            f"""
            SELECT
                c.id, c.name, c.phone, c.email, c.alert_limit, c.notes,
                c.active, c.created_at, c.updated_at,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total,
                COUNT(CASE WHEN s.balance_due > 0 THEN 1 END) AS open_sales
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE {' AND '.join(conditions)}
            GROUP BY c.id, c.name, c.phone, c.email, c.alert_limit, c.notes, c.active, c.created_at, c.updated_at
            ORDER BY c.name
            """,
            tuple(params),
        )
        result = [dict(row) for row in rows]
        for customer in result:
            customer["debt_total"] = float(customer["debt_total"])
            customer["open_sales"] = int(customer["open_sales"])
            customer["over_limit"] = customer["debt_total"] >= float(customer["alert_limit"])
        return result

    def get_customer(self, customer_id: int) -> dict[str, Any]:
        row = self.db.query_one(
            """
            SELECT c.*,
                   COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.id = ?
            GROUP BY c.id
            """,
            (customer_id,),
        )
        if not row:
            raise ValidationError("Cliente no encontrado")
        customer = dict(row)
        customer["debt_total"] = float(customer["debt_total"])
        customer["over_limit"] = customer["debt_total"] >= float(customer["alert_limit"])
        return customer

    def create_customer(
        self,
        *,
        name: str,
        phone: str = "",
        email: str = "",
        alert_limit: float = 50000,
        notes: str = "",
    ) -> int:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("El nombre del cliente es obligatorio")
        if alert_limit < 0:
            raise ValidationError("El limite de alerta no puede ser negativo")

        cur = self.db.execute(
            """
            INSERT INTO customers(name, phone, email, alert_limit, notes, active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (clean_name, phone.strip() or None, email.strip() or None, alert_limit, notes.strip() or None),
        )
        return int(cur.lastrowid)

    def update_customer(
        self,
        customer_id: int,
        *,
        name: str,
        phone: str,
        email: str,
        alert_limit: float,
        notes: str,
        active: bool,
    ) -> None:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("El nombre del cliente es obligatorio")
        if alert_limit < 0:
            raise ValidationError("El limite de alerta no puede ser negativo")

        cur = self.db.execute(
            """
            UPDATE customers
            SET
                name = ?, phone = ?, email = ?, alert_limit = ?,
                notes = ?, active = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                clean_name,
                phone.strip() or None,
                email.strip() or None,
                alert_limit,
                notes.strip() or None,
                1 if active else 0,
                customer_id,
            ),
        )
        if cur.rowcount == 0:
            raise ValidationError("Cliente no encontrado")

    def get_or_create_customer(self, name: str, phone: str = "") -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise ValidationError("El nombre del cliente es obligatorio")
        row = self.db.query_one(
            "SELECT id FROM customers WHERE lower(name) = lower(?) AND active = 1 LIMIT 1",
            (clean_name,),
        )
        if row:
            return self.get_customer(int(row["id"]))
        customer_id = self.create_customer(name=clean_name, phone=phone)
        return self.get_customer(customer_id)

    def get_customer_open_sales(self, customer_id: int) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT id, sold_at, payment_method, total, paid_amount, balance_due, status, sale_type, notes
            FROM sales
            WHERE customer_id = ? AND balance_due > 0
            ORDER BY sold_at ASC, id ASC
            """,
            (customer_id,),
        )
        return [dict(row) for row in rows]

    def get_customer_payments(self, customer_id: int, limit: int = 300) -> list[dict[str, Any]]:
        rows = self.db.query_all(
            """
            SELECT p.id, p.sale_id, p.customer_id, p.amount, p.payment_method, p.paid_at, p.note,
                   p.reference_type, p.reference_id
            FROM payments p
            WHERE p.customer_id = ?
            ORDER BY p.paid_at DESC, p.id DESC
            LIMIT ?
            """,
            (customer_id, limit),
        )
        return [dict(row) for row in rows]

    def get_customer_account(self, customer_id: int) -> dict[str, Any]:
        customer = self.get_customer(customer_id)
        open_sales = self.get_customer_open_sales(customer_id)
        payments = self.get_customer_payments(customer_id)
        sales_rows = self.db.query_all(
            """
            SELECT id, sold_at, payment_method, total, paid_amount, balance_due, status, sale_type, notes
            FROM sales
            WHERE customer_id = ?
            ORDER BY sold_at DESC, id DESC
            LIMIT 500
            """,
            (customer_id,),
        )

        total_purchases = sum(float(row["total"]) for row in sales_rows)
        total_paid = sum(float(row["paid_amount"]) for row in sales_rows)
        total_debt = sum(float(row["balance_due"]) for row in sales_rows)

        return {
            "customer": customer,
            "summary": {
                "total_purchases": total_purchases,
                "total_paid": total_paid,
                "total_debt": total_debt,
                "open_sales": len(open_sales),
                "over_limit": total_debt >= float(customer["alert_limit"]),
            },
            "sales": [dict(row) for row in sales_rows],
            "open_sales": open_sales,
            "payments": payments,
        }

    def normalize_payment_method(self, payment_method: str) -> str:
        clean = payment_method.strip().lower()
        aliases = {
            "efectivo": "Efectivo",
            "debito": "Debito",
            "débito": "Debito",
            "credito": "Credito",
            "crédito": "Credito",
            "transferencia": "Transferencia",
            "deuda": "Deuda",
            "cuenta corriente": "Deuda",
            "cuenta_corriente": "Deuda",
        }
        normalized = aliases.get(clean)
        if not normalized:
            raise ValidationError("Metodo de pago invalido")
        return normalized
    def register_customer_payment(
        self,
        *,
        customer_id: int,
        amount: float,
        payment_method: str,
        note: str = "",
        sale_id: int | None = None,
    ) -> dict[str, Any]:
        if amount <= 0:
            raise ValidationError("El pago debe ser mayor a cero")
        clean_payment_method = self.normalize_payment_method(payment_method)
        if clean_payment_method == "Deuda":
            raise ValidationError("El pago de deuda debe registrarse con efectivo, credito, debito o transferencia")
        customer = self.get_customer(customer_id)
        if customer["debt_total"] <= 0:
            raise ValidationError("El cliente no tiene deuda")

        if sale_id is not None:
            candidate_rows = self.db.query_all(
                """
                SELECT id, balance_due, paid_amount
                FROM sales
                WHERE id = ? AND customer_id = ? AND balance_due > 0
                ORDER BY sold_at ASC, id ASC
                """,
                (sale_id, customer_id),
            )
        else:
            candidate_rows = self.db.query_all(
                """
                SELECT id, balance_due, paid_amount
                FROM sales
                WHERE customer_id = ? AND balance_due > 0
                ORDER BY sold_at ASC, id ASC
                """,
                (customer_id,),
            )
        if not candidate_rows:
            raise ValidationError("No hay deudas abiertas para aplicar el pago")

        remaining = amount
        allocations: list[dict[str, Any]] = []
        with self.db.transaction() as conn:
            for row in candidate_rows:
                if remaining <= 0:
                    break
                current_balance = float(row["balance_due"])
                payment = min(remaining, current_balance)
                new_balance = current_balance - payment
                new_paid = float(row["paid_amount"]) + payment
                new_status = "paid" if new_balance <= 1e-9 else "partial"

                conn.execute(
                    "UPDATE sales SET paid_amount = ?, balance_due = ?, status = ? WHERE id = ?",
                    (new_paid, max(new_balance, 0.0), new_status, row["id"]),
                )
                conn.execute(
                    """
                    INSERT INTO payments(
                        sale_id, customer_id, amount, payment_method,
                        note, reference_type, reference_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["id"],
                        customer_id,
                        payment,
                        clean_payment_method,
                        note.strip() or None,
                        "debt_payment",
                        row["id"],
                    ),
                )

                allocations.append(
                    {
                        "sale_id": int(row["id"]),
                        "applied_amount": payment,
                        "new_balance": max(new_balance, 0.0),
                    }
                )
                remaining -= payment

        return {
            "customer_id": customer_id,
            "requested_amount": amount,
            "applied_amount": amount - remaining,
            "remaining_unapplied": remaining,
            "allocations": allocations,
        }

    # ----------------------
    # Stock
    # ----------------------
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

        new_cost = float(product["cost"]) if unit_cost is None or unit_cost < 0 else unit_cost
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
        if abs(delta) <= 1e-9:
            return
        self.register_stock_movement(
            product_id=product_id,
            movement_type="adjustment",
            quantity=delta,
            note=note or "Ajuste por conteo fisico",
            reference_type="adjustment",
        )

    # ----------------------
    # Sales
    # ----------------------
    def create_sale(
        self,
        items: list[dict[str, Any]],
        payment_method: str,
        notes: str = "",
        customer_id: int | None = None,
        sale_type: str = "cash",
        paid_amount: float | None = None,
        initial_payment_method: str | None = None,
    ) -> dict[str, Any]:
        if not items:
            raise ValidationError("No hay productos en el carrito")
        method = self.normalize_payment_method(payment_method)
        requested_mode = sale_type.strip().lower() if sale_type.strip() else "cash"
        if requested_mode not in {"cash", "credit"}:
            raise ValidationError("Tipo de venta invalido")
        mode = requested_mode
        if customer_id is not None:
            customer = self.get_customer(customer_id)
            if not bool(customer["active"]):
                raise ValidationError("El cliente esta inactivo")

        sold_at = datetime.now().isoformat(timespec="seconds")
        with self.db.transaction() as conn:
            sale_cur = conn.execute(
                """
                INSERT INTO sales(
                    sold_at, payment_method, total, notes,
                    customer_id, sale_type, paid_amount, balance_due, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (sold_at, method, 0, notes.strip() or None, customer_id, mode, 0, 0, "paid"),
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

            if paid_amount is None:
                raw_paid = 0.0 if method == "Deuda" else total
            else:
                raw_paid = float(paid_amount)
            if raw_paid < 0:
                raise ValidationError("El pago no puede ser negativo")
            if raw_paid - total > 1e-9:
                raise ValidationError("El pago no puede superar el total")

            balance_due = max(total - raw_paid, 0.0)
            mode = "credit" if balance_due > 1e-9 else "cash"
            if balance_due > 1e-9 and customer_id is None:
                raise ValidationError("Para pago parcial o deuda debes seleccionar un cliente")
            if balance_due <= 1e-9:
                status = "paid"
            elif raw_paid > 0:
                status = "partial"
            else:
                status = "credit"

            sale_method = method if method != "Deuda" else "Efectivo"
            conn.execute(
                "UPDATE sales SET payment_method = ?, sale_type = ?, total = ?, paid_amount = ?, balance_due = ?, status = ? WHERE id = ?",
                (sale_method, mode, total, raw_paid, balance_due, status, sale_id),
            )

            if customer_id is not None and raw_paid > 0:
                selected_payment = initial_payment_method or method
                applied_method = self.normalize_payment_method(selected_payment)
                if applied_method == "Deuda":
                    applied_method = "Efectivo"
                conn.execute(
                    """
                    INSERT INTO payments(
                        sale_id, customer_id, amount, payment_method,
                        note, reference_type, reference_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sale_id,
                        customer_id,
                        raw_paid,
                        applied_method,
                        "Pago inicial de venta",
                        "sale_payment",
                        sale_id,
                    ),
                )

        return {
            "sale_id": sale_id,
            "sold_at": sold_at,
            "total": total,
            "payment_method": sale_method,
            "sale_type": mode,
            "customer_id": customer_id,
            "paid_amount": raw_paid,
            "balance_due": balance_due,
            "status": status,
            "initial_payment_method": applied_method if raw_paid > 0 and customer_id is not None else None,
        }

    def get_sale(self, sale_id: int) -> dict[str, Any]:
        row = self.db.query_one(
            """
            SELECT s.id, s.sold_at, s.payment_method, s.total, s.notes,
                   s.customer_id, s.sale_type, s.paid_amount, s.balance_due, s.status,
                   c.name AS customer_name, c.phone AS customer_phone
            FROM sales s
            LEFT JOIN customers c ON c.id = s.customer_id
            WHERE s.id = ?
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

    def list_sales(self, days: int = 30, customer_id: int | None = None) -> list[dict[str, Any]]:
        days = self._safe_positive_int(days, default=30)
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        if customer_id is None:
            rows = self.db.query_all(
                """
                SELECT s.id, s.sold_at, s.payment_method, s.total,
                       s.paid_amount, s.balance_due, s.status, s.sale_type,
                       c.name AS customer_name
                FROM sales s
                LEFT JOIN customers c ON c.id = s.customer_id
                WHERE date(s.sold_at) >= date(?)
                ORDER BY s.sold_at DESC, s.id DESC
                """,
                (start_date,),
            )
        else:
            rows = self.db.query_all(
                """
                SELECT s.id, s.sold_at, s.payment_method, s.total,
                       s.paid_amount, s.balance_due, s.status, s.sale_type,
                       c.name AS customer_name
                FROM sales s
                LEFT JOIN customers c ON c.id = s.customer_id
                WHERE date(s.sold_at) >= date(?) AND s.customer_id = ?
                ORDER BY s.sold_at DESC, s.id DESC
                """,
                (start_date, customer_id),
            )
        return [dict(row) for row in rows]

    # ----------------------
    # Ticketing
    # ----------------------
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

    # ----------------------
    # Movements and reports
    # ----------------------
    def list_stock_movements(self, limit: int = 300) -> list[dict[str, Any]]:
        safe_limit = self._safe_positive_int(limit, default=300)
        rows = self.db.query_all(
            """
            SELECT
                m.id, m.created_at, m.movement_type, m.quantity,
                m.stock_before, m.stock_after, m.note, m.reference_type, m.reference_id,
                p.name AS product_name, p.barcode
            FROM stock_movements m
            JOIN products p ON p.id = m.product_id
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            (safe_limit,),
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

    def get_customers_over_limit(self) -> list[dict[str, Any]]:
        global_limit = float(self.get_debt_global_alert_limit())
        rows = self.db.query_all(
            """
            SELECT
                c.id, c.name, c.phone, c.alert_limit,
                COALESCE(SUM(CASE WHEN s.balance_due > 0 THEN s.balance_due ELSE 0 END), 0) AS debt_total
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.active = 1
            GROUP BY c.id, c.name, c.phone, c.alert_limit
            HAVING debt_total >= c.alert_limit OR debt_total >= ?
            ORDER BY debt_total DESC
            """,
            (global_limit,),
        )
        return [dict(row) for row in rows]

    def get_dashboard_metrics(self) -> dict[str, Any]:
        total_products = self.db.query_one("SELECT COUNT(*) AS total FROM products WHERE active = 1")["total"]
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
        month_profit = self.db.query_one(
            """
            SELECT COALESCE(SUM(si.subtotal - (si.cost_at_sale * si.quantity)), 0) AS total
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            WHERE strftime('%Y-%m', s.sold_at) = strftime('%Y-%m', 'now', 'localtime')
            """
        )["total"]
        receivables = self.db.query_one(
            "SELECT COALESCE(SUM(balance_due), 0) AS total FROM sales WHERE balance_due > 0"
        )["total"]
        month_tickets = self.db.query_one(
            """
            SELECT COUNT(*) AS total
            FROM sales
            WHERE strftime('%Y-%m', sold_at) = strftime('%Y-%m', 'now', 'localtime')
            """
        )["total"]
        return {
            "total_products": int(total_products),
            "low_stock_products": int(low_stock),
            "today_sales_total": float(today_sales),
            "month_sales_total": float(month_sales),
            "month_profit_total": float(month_profit),
            "receivables_total": float(receivables),
            "month_tickets": int(month_tickets),
            "customers_over_limit": len(self.get_customers_over_limit()),
        }

    def get_sales_summary(self, days: int = 30) -> dict[str, Any]:
        days = self._safe_positive_int(days, default=30)
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        summary = self.db.query_one(
            """
            SELECT
                COALESCE((SELECT SUM(total) FROM sales WHERE date(sold_at) >= date(?)), 0) AS revenue,
                COALESCE(
                    (
                        SELECT SUM(si.quantity)
                        FROM sale_items si
                        JOIN sales s ON s.id = si.sale_id
                        WHERE date(s.sold_at) >= date(?)
                    ),
                    0
                ) AS units,
                COALESCE(
                    (
                        SELECT SUM(si.subtotal - (si.cost_at_sale * si.quantity))
                        FROM sale_items si
                        JOIN sales s ON s.id = si.sale_id
                        WHERE date(s.sold_at) >= date(?)
                    ),
                    0
                ) AS gross_profit,
                COALESCE((SELECT COUNT(*) FROM sales WHERE date(sold_at) >= date(?)), 0) AS tickets,
                COALESCE((SELECT SUM(balance_due) FROM sales WHERE date(sold_at) >= date(?)), 0) AS pending
            """,
            (start_date, start_date, start_date, start_date, start_date),
        )
        return {
            "revenue": float(summary["revenue"]),
            "units": float(summary["units"]),
            "gross_profit": float(summary["gross_profit"]),
            "tickets": int(summary["tickets"]),
            "pending": float(summary["pending"]),
            "from": start_date,
            "to": date.today().isoformat(),
            "days": days,
        }

    def get_top_products(
        self,
        limit: int = 10,
        ascending: bool = False,
        days: int | None = None,
    ) -> list[dict[str, Any]]:
        safe_limit = self._safe_positive_int(limit, default=10)
        direction = "ASC" if ascending else "DESC"
        if days is None:
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
                (safe_limit,),
            )
        else:
            safe_days = self._safe_positive_int(days, default=30)
            start_date = (date.today() - timedelta(days=safe_days - 1)).isoformat()
            rows = self.db.query_all(
                f"""
                SELECT
                    si.product_id,
                    si.product_name,
                    SUM(si.quantity) AS units,
                    SUM(si.subtotal) AS revenue
                FROM sale_items si
                JOIN sales s ON s.id = si.sale_id
                WHERE date(s.sold_at) >= date(?)
                GROUP BY si.product_id, si.product_name
                ORDER BY units {direction}, revenue {direction}
                LIMIT ?
                """,
                (start_date, safe_limit),
            )
        return [dict(row) for row in rows]

    def get_sales_series(self, days: int = 14) -> list[dict[str, Any]]:
        days = self._safe_positive_int(days, default=14)
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

    def get_finance_series(self, days: int = 30) -> list[dict[str, Any]]:
        days = self._safe_positive_int(days, default=30)
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        revenue_rows = self.db.query_all(
            """
            SELECT
                date(sold_at) AS day,
                COALESCE(SUM(total), 0) AS revenue
            FROM sales
            WHERE date(sold_at) >= date(?)
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date,),
        )
        profit_rows = self.db.query_all(
            """
            SELECT
                date(s.sold_at) AS day,
                COALESCE(SUM(si.subtotal - (si.cost_at_sale * si.quantity)), 0) AS profit
            FROM sales s
            JOIN sale_items si ON si.sale_id = s.id
            WHERE date(s.sold_at) >= date(?)
            GROUP BY day
            ORDER BY day ASC
            """,
            (start_date,),
        )
        values: dict[str, dict[str, float]] = {}
        for row in revenue_rows:
            values[str(row["day"])] = {
                "revenue": float(row["revenue"]),
                "profit": 0.0,
            }
        for row in profit_rows:
            day = str(row["day"])
            if day not in values:
                values[day] = {"revenue": 0.0, "profit": 0.0}
            values[day]["profit"] = float(row["profit"])

        result: list[dict[str, Any]] = []
        for idx in range(days):
            current_day = (date.today() - timedelta(days=days - 1 - idx)).isoformat()
            found = values.get(current_day, {"revenue": 0.0, "profit": 0.0})
            result.append({"day": current_day, "revenue": found["revenue"], "profit": found["profit"]})
        return result

    def get_payment_method_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        days = self._safe_positive_int(days, default=30)
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()
        rows = self.db.query_all(
            """
            SELECT payment_method, COALESCE(SUM(total), 0) AS total, COUNT(*) AS tickets
            FROM sales
            WHERE date(sold_at) >= date(?)
            GROUP BY payment_method
            ORDER BY total DESC
            """,
            (start_date,),
        )
        return [dict(row) for row in rows]

    def get_collection_method_breakdown(self, days: int = 30) -> list[dict[str, Any]]:
        days = self._safe_positive_int(days, default=30)
        start_date = (date.today() - timedelta(days=days - 1)).isoformat()

        # Ventas sin cliente: no generan registros en payments.
        direct_sale_rows = self.db.query_all(
            """
            SELECT
                payment_method,
                COALESCE(SUM(paid_amount), 0) AS total,
                COUNT(*) AS operations
            FROM sales
            WHERE date(sold_at) >= date(?) AND customer_id IS NULL AND paid_amount > 0
            GROUP BY payment_method
            """,
            (start_date,),
        )

        # Compatibilidad con datos historicos: cliente con paid_amount pero sin movimientos en payments.
        legacy_customer_rows = self.db.query_all(
            """
            SELECT
                s.payment_method AS payment_method,
                COALESCE(
                    SUM(
                        CASE
                            WHEN s.paid_amount > COALESCE(p.total_payments, 0)
                            THEN s.paid_amount - COALESCE(p.total_payments, 0)
                            ELSE 0
                        END
                    ),
                    0
                ) AS total,
                COALESCE(
                    SUM(
                        CASE
                            WHEN s.paid_amount > COALESCE(p.total_payments, 0) THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS operations
            FROM sales s
            LEFT JOIN (
                SELECT sale_id, COALESCE(SUM(amount), 0) AS total_payments
                FROM payments
                GROUP BY sale_id
            ) p ON p.sale_id = s.id
            WHERE date(s.sold_at) >= date(?) AND s.customer_id IS NOT NULL AND s.paid_amount > 0
            GROUP BY s.payment_method
            HAVING total > 0
            """,
            (start_date,),
        )

        # Movimientos de cobro registrados (inicial y/o deuda).
        payment_rows = self.db.query_all(
            """
            SELECT
                payment_method,
                COALESCE(SUM(amount), 0) AS total,
                COUNT(*) AS operations
            FROM payments
            WHERE date(paid_at) >= date(?)
              AND (reference_type IN ('sale_payment', 'debt_payment') OR reference_type IS NULL)
            GROUP BY payment_method
            """,
            (start_date,),
        )

        merged: dict[str, dict[str, Any]] = {}
        for row in direct_sale_rows + legacy_customer_rows + payment_rows:
            method = str(row["payment_method"] or "Sin metodo")
            bucket = merged.get(method)
            if not bucket:
                bucket = {"payment_method": method, "total": 0.0, "operations": 0}
                merged[method] = bucket
            bucket["total"] = float(bucket["total"]) + float(row["total"])
            bucket["operations"] = int(bucket["operations"]) + int(row["operations"])

        result = list(merged.values())
        result.sort(key=lambda item: float(item["total"]), reverse=True)
        return result

    def get_top_customers_by_debt(self, limit: int = 10) -> list[dict[str, Any]]:
        safe_limit = self._safe_positive_int(limit, default=10)
        rows = self.db.query_all(
            """
            SELECT
                c.id, c.name, c.phone, c.alert_limit,
                COALESCE(SUM(s.balance_due), 0) AS debt_total
            FROM customers c
            LEFT JOIN sales s ON s.customer_id = c.id
            WHERE c.active = 1
            GROUP BY c.id, c.name, c.phone, c.alert_limit
            HAVING debt_total > 0
            ORDER BY debt_total DESC
            LIMIT ?
            """,
            (safe_limit,),
        )
        return [dict(row) for row in rows]

