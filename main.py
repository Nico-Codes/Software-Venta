from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from venta_app.database import Database
from venta_app.services import WarehouseService
from venta_app.ui.main_window import MainWindow


def app_base_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd()


def build_data_path() -> Path:
    base_dir = app_base_path() / "data"
    base_dir.mkdir(parents=True, exist_ok=True)
    return base_dir / "venta_local.db"


def main() -> int:
    app = QApplication(sys.argv)

    db = Database(build_data_path())
    db.initialize()
    service = WarehouseService(db)

    window = MainWindow(service)
    window.show()

    exit_code = app.exec()
    db.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
