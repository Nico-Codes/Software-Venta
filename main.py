from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication, QDialog

from venta_app.database import Database
from venta_app.services import WarehouseService
from venta_app.ui.login_dialog import LoginDialog
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
    app.setStyle("Fusion")

    db = Database(build_data_path())
    db.initialize()
    service = WarehouseService(db)
    try:
        service.auto_backup_if_needed()
    except OSError:
        # If disk permissions or paths fail, keep app usable and let user back up manually.
        pass

    login = LoginDialog(service)
    if login.exec() != QDialog.DialogCode.Accepted or not login.user:
        db.close()
        return 0

    window = MainWindow(service, current_user=login.user)
    window.show()

    exit_code = app.exec()
    db.close()
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
