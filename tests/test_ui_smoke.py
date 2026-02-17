from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None  # type: ignore[assignment]

from venta_app.database import Database
from venta_app.services import WarehouseService
from venta_app.ui.main_window import MainWindow


@unittest.skipIf(QApplication is None, "PySide6 no disponible")
class UISmokeTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        db_path = Path(self.tmpdir.name) / "ui_smoke.db"
        self.db = Database(db_path)
        self.db.initialize()
        self.service = WarehouseService(self.db)

        category_id = int(self.service.list_categories()[0]["id"])
        self.service.create_product(
            name="Producto UI",
            barcode="779009991111",
            category_id=category_id,
            cost=100,
            sale_price=150,
            stock=5,
            min_stock=1,
            auto_price=False,
        )

    def tearDown(self) -> None:
        self.db.close()
        self.tmpdir.cleanup()

    def test_admin_window_navigation_smoke(self) -> None:
        window = MainWindow(self.service, current_user={"id": 1, "username": "admin", "role": "admin"})
        window.refresh_all()
        window.select_page("venta")
        window.select_page("stock")
        window.select_page("panel")
        window.close()

    def test_seller_window_smoke(self) -> None:
        window = MainWindow(self.service, current_user={"id": 2, "username": "vendedor", "role": "seller"})
        window.refresh_all()
        window.select_page("venta")
        window.close()
