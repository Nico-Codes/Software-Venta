from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from ..services import ValidationError, WarehouseService


class TicketDialog(QDialog):
    def __init__(
        self,
        service: WarehouseService,
        sale_id: int,
        ticket_text: str,
        ticket_path: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.sale_id = sale_id
        self.ticket_text = ticket_text
        self.ticket_path = ticket_path

        self.setWindowTitle(f"Ticket venta #{sale_id}")
        self.resize(560, 680)

        root = QVBoxLayout(self)

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(ticket_text)
        mono_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.preview.setFont(mono_font)

        root.addWidget(self.preview, stretch=1)

        buttons = QHBoxLayout()
        self.print_btn = QPushButton("Imprimir")
        self.print_btn.clicked.connect(self.print_ticket)

        self.export_btn = QPushButton("Guardar copia")
        self.export_btn.clicked.connect(self.export_ticket)

        self.close_btn = QPushButton("Cerrar")
        self.close_btn.clicked.connect(self.accept)

        buttons.addWidget(self.print_btn)
        buttons.addWidget(self.export_btn)
        buttons.addStretch(1)
        buttons.addWidget(self.close_btn)

        root.addLayout(buttons)

    def print_ticket(self) -> None:
        try:
            self.service.print_sale_ticket(self.sale_id)
        except (ValidationError, OSError, RuntimeError) as exc:
            QMessageBox.warning(self, "No se pudo imprimir", str(exc))
            return

        QMessageBox.information(self, "Impresion", "Ticket enviado a la impresora")

    def export_ticket(self) -> None:
        default_name = Path(self.ticket_path).name
        target, _ = QFileDialog.getSaveFileName(
            self,
            "Guardar ticket",
            str(Path.home() / default_name),
            "Archivo de texto (*.txt)",
        )
        if not target:
            return

        try:
            self.service.export_sale_ticket(self.sale_id, target)
        except (ValidationError, OSError) as exc:
            QMessageBox.warning(self, "No se pudo exportar", str(exc))
            return

        QMessageBox.information(self, "Guardado", "Ticket guardado correctamente")
