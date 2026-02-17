from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ..services import WarehouseService
from .common import format_currency


class CustomerAccountDialog(QDialog):
    def __init__(self, service: WarehouseService, customer_id: int, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.customer_id = customer_id

        account = self.service.get_customer_account(customer_id)
        customer = account["customer"]
        summary = account["summary"]

        self.setWindowTitle(f"Cuenta corriente - {customer['name']}")
        self.resize(820, 620)

        root = QVBoxLayout(self)

        summary_row = QHBoxLayout()
        summary_row.addWidget(QLabel(f"Cliente: {customer['name']}"))
        summary_row.addWidget(QLabel(f"Telefono: {customer.get('phone') or '-'}"))
        summary_row.addWidget(QLabel(f"Compras: {format_currency(float(summary['total_purchases']))}"))
        summary_row.addWidget(QLabel(f"Pagado: {format_currency(float(summary['total_paid']))}"))
        summary_row.addWidget(QLabel(f"Deuda: {format_currency(float(summary['total_debt']))}"))
        root.addLayout(summary_row)

        open_title = QLabel("Ventas con saldo")
        open_title.setObjectName("sectionTitle")
        root.addWidget(open_title)

        open_table = QTableWidget(0, 6)
        open_table.setHorizontalHeaderLabels(["Venta", "Fecha", "Total", "Pagado", "Saldo", "Estado"])
        open_table.verticalHeader().setVisible(False)
        open_table.horizontalHeader().setStretchLastSection(True)
        open_sales = account["open_sales"]
        open_table.setRowCount(len(open_sales))
        for idx, sale in enumerate(open_sales):
            open_table.setItem(idx, 0, QTableWidgetItem(str(sale["id"])))
            open_table.setItem(idx, 1, QTableWidgetItem(str(sale["sold_at"])))
            open_table.setItem(idx, 2, QTableWidgetItem(format_currency(float(sale["total"]))))
            open_table.setItem(idx, 3, QTableWidgetItem(format_currency(float(sale["paid_amount"]))))
            open_table.setItem(idx, 4, QTableWidgetItem(format_currency(float(sale["balance_due"]))))
            open_table.setItem(idx, 5, QTableWidgetItem(str(sale["status"])))
        open_table.resizeColumnsToContents()
        root.addWidget(open_table, stretch=1)

        pay_title = QLabel("Pagos")
        pay_title.setObjectName("sectionTitle")
        root.addWidget(pay_title)

        pay_table = QTableWidget(0, 5)
        pay_table.setHorizontalHeaderLabels(["Fecha", "Monto", "Metodo", "Venta", "Nota"])
        pay_table.verticalHeader().setVisible(False)
        pay_table.horizontalHeader().setStretchLastSection(True)
        payments = account["payments"]
        pay_table.setRowCount(len(payments))
        for idx, payment in enumerate(payments):
            sale_ref = f"#{payment['sale_id']}" if payment.get("sale_id") else "-"
            pay_table.setItem(idx, 0, QTableWidgetItem(str(payment["paid_at"])))
            pay_table.setItem(idx, 1, QTableWidgetItem(format_currency(float(payment["amount"]))))
            pay_table.setItem(idx, 2, QTableWidgetItem(str(payment["payment_method"])))
            pay_table.setItem(idx, 3, QTableWidgetItem(sale_ref))
            pay_table.setItem(idx, 4, QTableWidgetItem(str(payment.get("note") or "-")))
        pay_table.resizeColumnsToContents()
        root.addWidget(pay_table, stretch=1)

        actions = QHBoxLayout()
        close_btn = QPushButton("Cerrar")
        close_btn.clicked.connect(self.accept)
        actions.addStretch(1)
        actions.addWidget(close_btn)
        root.addLayout(actions)
