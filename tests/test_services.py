from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from venta_app.database import Database
from venta_app.services import ValidationError, WarehouseService


class ServiceFlowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "test.db"
        self.db = Database(db_path)
        self.db.initialize()
        self.service = WarehouseService(self.db)

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    def _category_id(self, name: str) -> int:
        categories = self.service.list_categories()
        for category in categories:
            if category["name"] == name:
                return int(category["id"])
        raise AssertionError(f"Categoria no encontrada: {name}")

    def test_margin_update_recalculates_auto_price(self) -> None:
        vinos_id = self._category_id("Vinos")
        product_id = self.service.create_product(
            name="Vino Tinto",
            barcode="779000000001",
            category_id=vinos_id,
            cost=1000,
            sale_price=0,
            stock=5,
            min_stock=1,
            auto_price=True,
        )

        product = self.service.get_product(product_id)
        self.assertEqual(float(product["sale_price"]), 1300)

        self.service.update_category(vinos_id, "Vinos", 50)
        updated = self.service.get_product(product_id)
        self.assertEqual(float(updated["sale_price"]), 1500)

    def test_sale_keeps_historical_price_and_updates_stock(self) -> None:
        category_id = self._category_id("Gaseosas")
        product_id = self.service.create_product(
            name="Gaseosa Cola",
            barcode="779000000002",
            category_id=category_id,
            cost=100,
            sale_price=250,
            stock=10,
            min_stock=2,
            auto_price=False,
        )

        sale = self.service.create_sale(
            [{"product_id": product_id, "quantity": 2}],
            payment_method="Efectivo",
        )
        self.assertGreater(sale["sale_id"], 0)
        self.assertEqual(float(sale["total"]), 500)

        product = self.service.get_product(product_id)
        self.assertEqual(float(product["stock"]), 8)

        item = self.db.query_one(
            "SELECT unit_price, quantity FROM sale_items WHERE sale_id = ?",
            (sale["sale_id"],),
        )
        assert item is not None
        self.assertEqual(float(item["unit_price"]), 250)
        self.assertEqual(float(item["quantity"]), 2)

        self.service.update_product(
            product_id,
            name="Gaseosa Cola",
            barcode="779000000002",
            category_id=category_id,
            cost=120,
            sale_price=300,
            stock=8,
            min_stock=2,
            auto_price=False,
            active=True,
        )

        after_update_item = self.db.query_one(
            "SELECT unit_price FROM sale_items WHERE sale_id = ?",
            (sale["sale_id"],),
        )
        assert after_update_item is not None
        self.assertEqual(float(after_update_item["unit_price"]), 250)

    def test_ticket_generation_and_export(self) -> None:
        category_id = self._category_id("Vinos")
        product_id = self.service.create_product(
            name="Vino Malbec",
            barcode="779000000099",
            category_id=category_id,
            cost=1000,
            sale_price=1500,
            stock=10,
            min_stock=2,
            auto_price=False,
        )

        self.service.set_ticket_config(
            store_name="Vinoteca Central",
            store_address="Av. Siempre Viva 123",
            store_phone="11-4444-5555",
            ticket_footer="Vuelva pronto",
        )

        sale = self.service.create_sale(
            [{"product_id": product_id, "quantity": 2}],
            payment_method="Debito",
        )
        ticket = self.service.create_sale_ticket(int(sale["sale_id"]))
        self.assertIn("VINOTECA CENTRAL", ticket["text"])
        self.assertIn("Vino Malbec", ticket["text"])
        self.assertTrue(Path(ticket["path"]).exists())

        destination = Path(self.tmpdir.name) / "ticket_copia.txt"
        exported = self.service.export_sale_ticket(int(sale["sale_id"]), str(destination))
        self.assertEqual(str(destination), exported)
        self.assertTrue(destination.exists())

    def test_default_users_and_auth(self) -> None:
        users = self.service.list_users()
        usernames = {u["username"] for u in users}
        self.assertIn("admin", usernames)
        self.assertIn("vendedor", usernames)

        admin = self.service.authenticate_user("admin", "admin123")
        self.assertEqual(admin["role"], "admin")

        seller = self.service.authenticate_user("vendedor", "venta123")
        self.assertEqual(seller["role"], "seller")

        with self.assertRaises(ValidationError):
            self.service.authenticate_user("admin", "clave-invalida")

    def test_cannot_remove_last_active_admin(self) -> None:
        users = self.service.list_users()
        admin_user = next(u for u in users if u["username"] == "admin")
        admin_id = int(admin_user["id"])

        with self.assertRaises(ValidationError):
            self.service.update_user(admin_id, role="seller", active=True)

        with self.assertRaises(ValidationError):
            self.service.update_user(admin_id, role="admin", active=False)

        second_admin_id = self.service.create_user("admin2", "admin2pass", role="admin")
        self.service.update_user(admin_id, role="seller", active=True)

        updated_admin = next(u for u in self.service.list_users() if int(u["id"]) == admin_id)
        self.assertEqual(updated_admin["role"], "seller")
        self.assertTrue(any(int(u["id"]) == second_admin_id and u["role"] == "admin" for u in self.service.list_users()))

    def test_credit_sale_and_payment_flow(self) -> None:
        category_id = self._category_id("Vinos")
        product_id = self.service.create_product(
            name="Cabernet",
            barcode="779000001111",
            category_id=category_id,
            cost=1000,
            sale_price=1600,
            stock=12,
            min_stock=2,
            auto_price=False,
        )
        customer_id = self.service.create_customer(name="Juan Perez", phone="11-1234")

        sale = self.service.create_sale(
            [{"product_id": product_id, "quantity": 3}],
            payment_method="Efectivo",
            customer_id=customer_id,
            sale_type="credit",
            paid_amount=1000,
        )
        self.assertEqual(float(sale["total"]), 4800)
        self.assertEqual(float(sale["paid_amount"]), 1000)
        self.assertEqual(float(sale["balance_due"]), 3800)
        self.assertEqual(str(sale["status"]), "partial")

        account = self.service.get_customer_account(customer_id)
        self.assertEqual(float(account["summary"]["total_debt"]), 3800)
        self.assertEqual(int(account["summary"]["open_sales"]), 1)

        pay_result = self.service.register_customer_payment(
            customer_id=customer_id,
            amount=2000,
            payment_method="Transferencia",
            note="Pago parcial",
        )
        self.assertEqual(float(pay_result["applied_amount"]), 2000)

        refreshed = self.service.get_customer_account(customer_id)
        self.assertEqual(float(refreshed["summary"]["total_debt"]), 1800)

    def test_backup_export_and_restore(self) -> None:
        category_id = self._category_id("Vinos")
        self.service.create_product(
            name="Producto Backup",
            barcode="779000009999",
            category_id=category_id,
            cost=500,
            sale_price=900,
            stock=4,
            min_stock=1,
            auto_price=False,
        )

        backup = self.service.create_backup(prefix="manual")
        backup_path = Path(str(backup["path"]))
        self.assertTrue(backup_path.exists())

        export_dir = Path(self.tmpdir.name) / "csv"
        export_result = self.service.export_all_tables_to_csv(str(export_dir))
        self.assertTrue((export_dir / "products.csv").exists())
        self.assertGreaterEqual(len(export_result["files"]), 5)

        self.service.create_customer(name="Cliente Temporal")
        customers_before_restore = self.service.list_customers()
        self.assertGreaterEqual(len(customers_before_restore), 1)

        self.service.restore_database_from_backup(str(backup_path))
        restored_customers = self.service.list_customers()
        names = {c["name"] for c in restored_customers}
        self.assertNotIn("Cliente Temporal", names)

    def test_auto_backup_if_needed(self) -> None:
        self.service.set_auto_backup_settings(enabled=True, keep_days=30)
        self.service.set_setting("last_auto_backup_date", "2000-01-01")

        created = self.service.auto_backup_if_needed()
        self.assertIsNotNone(created)
        assert created is not None
        self.assertTrue(Path(str(created["path"])).exists())

        second = self.service.auto_backup_if_needed()
        self.assertIsNone(second)

    def test_create_product_requires_initial_stock_greater_than_zero(self) -> None:
        category_id = self._category_id("Vinos")
        with self.assertRaises(ValidationError):
            self.service.create_product(
                name="Sin Stock Inicial",
                barcode="779009990001",
                category_id=category_id,
                cost=100,
                sale_price=200,
                stock=0,
                min_stock=1,
                auto_price=False,
            )

    def test_partial_sale_without_customer_fails(self) -> None:
        category_id = self._category_id("Vinos")
        product_id = self.service.create_product(
            name="Prueba parcial sin cliente",
            barcode="779009990002",
            category_id=category_id,
            cost=100,
            sale_price=200,
            stock=5,
            min_stock=1,
            auto_price=False,
        )

        with self.assertRaises(ValidationError):
            self.service.create_sale(
                [{"product_id": product_id, "quantity": 2}],
                payment_method="Efectivo",
                paid_amount=100,
            )

    def test_collection_method_breakdown_counts_initial_and_debt_payments(self) -> None:
        category_id = self._category_id("Vinos")
        p1 = self.service.create_product(
            name="Cobro Debito",
            barcode="779009990020",
            category_id=category_id,
            cost=50,
            sale_price=300,
            stock=20,
            min_stock=1,
            auto_price=False,
        )
        p2 = self.service.create_product(
            name="Cobro Parcial",
            barcode="779009990021",
            category_id=category_id,
            cost=40,
            sale_price=200,
            stock=20,
            min_stock=1,
            auto_price=False,
        )

        self.service.create_sale([{"product_id": p1, "quantity": 1}], payment_method="Debito")

        customer_id = self.service.create_customer(name="Cliente Cobros")
        self.service.create_sale(
            [{"product_id": p2, "quantity": 4}],
            payment_method="Efectivo",
            customer_id=customer_id,
            sale_type="credit",
            paid_amount=300,
        )
        self.service.register_customer_payment(
            customer_id=customer_id,
            amount=250,
            payment_method="Transferencia",
            note="Abono deuda",
        )

        breakdown = self.service.get_collection_method_breakdown(days=30)
        totals = {str(item["payment_method"]): float(item["total"]) for item in breakdown}
        operations = {str(item["payment_method"]): int(item["operations"]) for item in breakdown}

        self.assertEqual(totals.get("Debito"), 300.0)
        self.assertEqual(totals.get("Efectivo"), 300.0)
        self.assertEqual(totals.get("Transferencia"), 250.0)
        self.assertEqual(operations.get("Debito"), 1)
        self.assertEqual(operations.get("Efectivo"), 1)
        self.assertEqual(operations.get("Transferencia"), 1)

    def test_reports_summary_and_finance_series_do_not_duplicate_sale_totals(self) -> None:
        category_id = self._category_id("Vinos")
        p1 = self.service.create_product(
            name="Producto A",
            barcode="779009990010",
            category_id=category_id,
            cost=10,
            sale_price=100,
            stock=10,
            min_stock=1,
            auto_price=False,
        )
        p2 = self.service.create_product(
            name="Producto B",
            barcode="779009990011",
            category_id=category_id,
            cost=20,
            sale_price=200,
            stock=10,
            min_stock=1,
            auto_price=False,
        )

        self.service.create_sale(
            [{"product_id": p1, "quantity": 1}, {"product_id": p2, "quantity": 1}],
            payment_method="Efectivo",
        )

        summary = self.service.get_sales_summary(days=30)
        self.assertEqual(float(summary["revenue"]), 300)
        self.assertEqual(float(summary["units"]), 2)
        self.assertEqual(float(summary["gross_profit"]), 270)
        self.assertEqual(int(summary["tickets"]), 1)
        self.assertEqual(float(summary["pending"]), 0)

        today = self.service.get_finance_series(days=1)[0]
        self.assertEqual(float(today["revenue"]), 300)
        self.assertEqual(float(today["profit"]), 270)

    def test_top_products_respects_period_days(self) -> None:
        category_id = self._category_id("Vinos")
        p_recent = self.service.create_product(
            name="Reciente",
            barcode="779009990030",
            category_id=category_id,
            cost=20,
            sale_price=200,
            stock=30,
            min_stock=1,
            auto_price=False,
        )
        p_old = self.service.create_product(
            name="Antiguo",
            barcode="779009990031",
            category_id=category_id,
            cost=10,
            sale_price=100,
            stock=30,
            min_stock=1,
            auto_price=False,
        )

        recent_sale = self.service.create_sale(
            [{"product_id": p_recent, "quantity": 3}],
            payment_method="Efectivo",
        )
        old_sale = self.service.create_sale(
            [{"product_id": p_old, "quantity": 5}],
            payment_method="Efectivo",
        )

        # Fuerza una venta fuera de ventana de 30 dias para validar el filtro por periodo.
        self.db.execute(
            "UPDATE sales SET sold_at = date('now', '-90 day') WHERE id = ?",
            (int(old_sale["sale_id"]),),
        )

        top_30 = self.service.get_top_products(limit=10, days=30)
        names_30 = [str(item["product_name"]) for item in top_30]
        self.assertIn("Reciente", names_30)
        self.assertNotIn("Antiguo", names_30)

        top_all = self.service.get_top_products(limit=10)
        names_all = [str(item["product_name"]) for item in top_all]
        self.assertIn("Reciente", names_all)
        self.assertIn("Antiguo", names_all)


if __name__ == "__main__":
    unittest.main()
