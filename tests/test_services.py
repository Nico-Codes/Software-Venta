from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from venta_app.database import Database
from venta_app.services import WarehouseService


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


if __name__ == "__main__":
    unittest.main()
