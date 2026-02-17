from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
import shutil
from typing import Any, Iterator


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = self._open_connection()

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def reopen(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass
        self.conn = self._open_connection()

    def initialize(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                margin_percent REAL NOT NULL DEFAULT 30,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                barcode TEXT UNIQUE,
                category_id INTEGER NOT NULL,
                cost REAL NOT NULL DEFAULT 0,
                sale_price REAL NOT NULL DEFAULT 0,
                auto_price INTEGER NOT NULL DEFAULT 1,
                stock REAL NOT NULL DEFAULT 0,
                min_stock REAL NOT NULL DEFAULT 0,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                alert_limit REAL NOT NULL DEFAULT 50000,
                notes TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                last_login TEXT
            );

            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sold_at TEXT NOT NULL,
                payment_method TEXT NOT NULL,
                total REAL NOT NULL,
                notes TEXT,
                customer_id INTEGER,
                sale_type TEXT NOT NULL DEFAULT 'cash',
                paid_amount REAL NOT NULL DEFAULT 0,
                balance_due REAL NOT NULL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'paid',
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                subtotal REAL NOT NULL,
                cost_at_sale REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE CASCADE,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER,
                customer_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                payment_method TEXT NOT NULL,
                paid_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                note TEXT,
                reference_type TEXT,
                reference_id INTEGER,
                FOREIGN KEY (sale_id) REFERENCES sales(id) ON DELETE SET NULL,
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                movement_type TEXT NOT NULL,
                quantity REAL NOT NULL,
                stock_before REAL NOT NULL,
                stock_after REAL NOT NULL,
                unit_cost REAL,
                reference_type TEXT,
                reference_id INTEGER,
                note TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            """
        )

        # Backward-compatible migrations for existing databases.
        self._ensure_column("sales", "customer_id", "INTEGER")
        self._ensure_column("sales", "sale_type", "TEXT NOT NULL DEFAULT 'cash'")
        self._ensure_column("sales", "paid_amount", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("sales", "balance_due", "REAL NOT NULL DEFAULT 0")
        self._ensure_column("sales", "status", "TEXT NOT NULL DEFAULT 'paid'")

        self._ensure_column("customers", "phone", "TEXT")
        self._ensure_column("customers", "email", "TEXT")
        self._ensure_column("customers", "alert_limit", "REAL NOT NULL DEFAULT 50000")
        self._ensure_column("customers", "notes", "TEXT")
        self._ensure_column("customers", "active", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("customers", "updated_at", "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP")

        self._ensure_column("users", "active", "INTEGER NOT NULL DEFAULT 1")
        self._ensure_column("users", "last_login", "TEXT")

        self._ensure_column("payments", "reference_type", "TEXT")
        self._ensure_column("payments", "reference_id", "INTEGER")

        self.conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
            CREATE INDEX IF NOT EXISTS idx_products_barcode ON products(barcode);
            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_sales_sold_at ON sales(sold_at);
            CREATE INDEX IF NOT EXISTS idx_sales_customer ON sales(customer_id);
            CREATE INDEX IF NOT EXISTS idx_sales_status ON sales(status);
            CREATE INDEX IF NOT EXISTS idx_sale_items_product ON sale_items(product_id);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_product ON stock_movements(product_id);
            CREATE INDEX IF NOT EXISTS idx_stock_movements_created_at ON stock_movements(created_at);
            CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);
            CREATE INDEX IF NOT EXISTS idx_payments_customer ON payments(customer_id);
            CREATE INDEX IF NOT EXISTS idx_payments_sale ON payments(sale_id);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            """
        )

        # Normalize existing sales rows from old schema.
        self.conn.execute(
            """
            UPDATE sales
            SET
                sale_type = CASE
                    WHEN sale_type IS NULL OR sale_type = '' THEN 'cash'
                    ELSE sale_type
                END
            """
        )

        self.conn.execute(
            """
            UPDATE sales
            SET
                paid_amount = CASE
                    WHEN paid_amount IS NULL THEN
                        CASE WHEN sale_type = 'cash' THEN total ELSE 0 END
                    ELSE paid_amount
                END,
                balance_due = CASE
                    WHEN balance_due IS NULL THEN
                        CASE WHEN sale_type = 'cash' THEN 0 ELSE MAX(total - COALESCE(paid_amount, 0), 0) END
                    ELSE balance_due
                END
            """
        )

        self.conn.execute(
            """
            UPDATE sales
            SET
                status = CASE
                    WHEN balance_due > 0 THEN
                        CASE WHEN paid_amount > 0 THEN 'partial' ELSE 'credit' END
                    ELSE 'paid'
                END
            """
        )

        self.conn.commit()

    def _table_columns(self, table_name: str) -> set[str]:
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_column(self, table_name: str, column_name: str, definition: str) -> None:
        if column_name in self._table_columns(table_name):
            return
        self.conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Cursor:
        cur = self.conn.execute(query, params)
        self.conn.commit()
        return cur

    def executemany(self, query: str, params: list[tuple[Any, ...]]) -> sqlite3.Cursor:
        cur = self.conn.executemany(query, params)
        self.conn.commit()
        return cur

    def query_all(self, query: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        cur = self.conn.execute(query, params)
        return cur.fetchall()

    def query_one(self, query: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        cur = self.conn.execute(query, params)
        return cur.fetchone()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        try:
            self.conn.execute("BEGIN")
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def close(self) -> None:
        self.conn.close()

    def backup_to(self, destination: str | Path) -> Path:
        destination_path = Path(destination)
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        backup_conn = sqlite3.connect(destination_path)
        try:
            self.conn.backup(backup_conn)
        finally:
            backup_conn.close()
        return destination_path

    def restore_from(self, source: str | Path) -> Path:
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"No existe el backup: {source_path}")

        self.conn.close()
        shutil.copy2(source_path, self.db_path)
        self.conn = self._open_connection()
        return self.db_path
