from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import WarehouseService
from .common import format_currency, format_number


class ReportsTab(QWidget):
    def __init__(self, service: WarehouseService) -> None:
        super().__init__()
        self.service = service

        root = QVBoxLayout(self)
        root.setSpacing(12)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Periodo (dias)"))
        self.days_input = QSpinBox()
        self.days_input.setRange(1, 365)
        self.days_input.setValue(30)
        self.refresh_btn = QPushButton("Actualizar")
        self.refresh_btn.clicked.connect(self.refresh)

        controls.addWidget(self.days_input)
        controls.addWidget(self.refresh_btn)
        controls.addStretch(1)
        root.addLayout(controls)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)

        self.revenue_card = self._create_card("Facturacion", "$ 0,00")
        self.profit_card = self._create_card("Ganancia bruta", "$ 0,00")
        self.tickets_card = self._create_card("Tickets", "0")
        self.units_card = self._create_card("Unidades", "0")
        self.pending_card = self._create_card("Saldo pendiente", "$ 0,00")

        summary_row.addWidget(self.revenue_card)
        summary_row.addWidget(self.profit_card)
        summary_row.addWidget(self.tickets_card)
        summary_row.addWidget(self.units_card)
        summary_row.addWidget(self.pending_card)

        root.addLayout(summary_row)

        tables_row = QHBoxLayout()
        tables_row.setSpacing(12)

        self.top_table = QTableWidget(0, 3)
        self.top_table.setHorizontalHeaderLabels(["Producto", "Unidades", "Facturacion"])
        self.top_table.verticalHeader().setVisible(False)
        self.top_table.horizontalHeader().setStretchLastSection(True)

        self.low_table = QTableWidget(0, 3)
        self.low_table.setHorizontalHeaderLabels(["Producto", "Unidades", "Facturacion"])
        self.low_table.verticalHeader().setVisible(False)
        self.low_table.horizontalHeader().setStretchLastSection(True)

        top_block = QVBoxLayout()
        top_title = QLabel("Mas vendidos")
        top_title.setObjectName("sectionTitle")
        top_block.addWidget(top_title)
        top_block.addWidget(self.top_table)

        low_block = QVBoxLayout()
        low_title = QLabel("Menos vendidos")
        low_title.setObjectName("sectionTitle")
        low_block.addWidget(low_title)
        low_block.addWidget(self.low_table)

        top_widget = QWidget()
        top_widget.setLayout(top_block)
        low_widget = QWidget()
        low_widget.setLayout(low_block)

        tables_row.addWidget(top_widget, stretch=1)
        tables_row.addWidget(low_widget, stretch=1)

        root.addLayout(tables_row, stretch=1)

        finance_tables = QHBoxLayout()
        finance_tables.setSpacing(12)

        self.methods_table = QTableWidget(0, 3)
        self.methods_table.setHorizontalHeaderLabels(["Metodo", "Facturacion", "Tickets"])
        self.methods_table.verticalHeader().setVisible(False)
        self.methods_table.horizontalHeader().setStretchLastSection(True)

        self.collections_table = QTableWidget(0, 3)
        self.collections_table.setHorizontalHeaderLabels(["Metodo", "Cobrado", "Movimientos"])
        self.collections_table.verticalHeader().setVisible(False)
        self.collections_table.horizontalHeader().setStretchLastSection(True)

        self.debtors_table = QTableWidget(0, 3)
        self.debtors_table.setHorizontalHeaderLabels(["Cliente", "Telefono", "Deuda"])
        self.debtors_table.verticalHeader().setVisible(False)
        self.debtors_table.horizontalHeader().setStretchLastSection(True)

        methods_block = QVBoxLayout()
        methods_title = QLabel("Ventas por metodo de pago")
        methods_title.setObjectName("sectionTitle")
        methods_block.addWidget(methods_title)
        methods_block.addWidget(self.methods_table)

        collections_block = QVBoxLayout()
        collections_title = QLabel("Cobranzas por metodo de pago")
        collections_title.setObjectName("sectionTitle")
        collections_block.addWidget(collections_title)
        collections_block.addWidget(self.collections_table)

        debtors_block = QVBoxLayout()
        debtors_title = QLabel("Clientes con mayor deuda")
        debtors_title.setObjectName("sectionTitle")
        debtors_block.addWidget(debtors_title)
        debtors_block.addWidget(self.debtors_table)

        methods_widget = QWidget()
        methods_widget.setLayout(methods_block)
        collections_widget = QWidget()
        collections_widget.setLayout(collections_block)
        debtors_widget = QWidget()
        debtors_widget.setLayout(debtors_block)
        finance_tables.addWidget(methods_widget, stretch=1)
        finance_tables.addWidget(collections_widget, stretch=1)
        finance_tables.addWidget(debtors_widget, stretch=1)

        root.addLayout(finance_tables, stretch=1)

        series_title = QLabel("Serie diaria")
        series_title.setObjectName("sectionTitle")
        root.addWidget(series_title)

        self.series_table = QTableWidget(0, 2)
        self.series_table.setHorizontalHeaderLabels(["Fecha", "Total"])
        self.series_table.verticalHeader().setVisible(False)
        self.series_table.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.series_table, stretch=1)

    def _create_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)

        title_label = QLabel(title)
        title_label.setObjectName("kpiTitle")
        value_label = QLabel(value)
        value_label.setObjectName("kpiValue")

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        card.value_label = value_label
        return card

    def refresh(self) -> None:
        days = int(self.days_input.value())

        summary = self.service.get_sales_summary(days)
        top = self.service.get_top_products(limit=10, days=days)
        low = self.service.get_top_products(limit=10, ascending=True, days=days)
        series = self.service.get_sales_series(days)
        methods = self.service.get_payment_method_breakdown(days)
        collections = self.service.get_collection_method_breakdown(days)
        debtors = self.service.get_top_customers_by_debt(limit=10)

        self.revenue_card.value_label.setText(format_currency(float(summary["revenue"])))
        self.profit_card.value_label.setText(format_currency(float(summary["gross_profit"])))
        self.tickets_card.value_label.setText(str(summary["tickets"]))
        self.units_card.value_label.setText(format_number(float(summary["units"])))
        self.pending_card.value_label.setText(format_currency(float(summary["pending"])))

        self._load_product_table(self.top_table, top)
        self._load_product_table(self.low_table, low)

        self.series_table.setRowCount(len(series))
        for idx, point in enumerate(series):
            self.series_table.setItem(idx, 0, QTableWidgetItem(point["day"]))
            self.series_table.setItem(idx, 1, QTableWidgetItem(format_currency(float(point["total"]))))

        self.series_table.resizeColumnsToContents()

        self.methods_table.setRowCount(len(methods))
        for idx, item in enumerate(methods):
            self.methods_table.setItem(idx, 0, QTableWidgetItem(str(item.get("payment_method", ""))))
            self.methods_table.setItem(idx, 1, QTableWidgetItem(format_currency(float(item.get("total", 0)))))
            self.methods_table.setItem(idx, 2, QTableWidgetItem(str(item.get("tickets", 0))))
        self.methods_table.resizeColumnsToContents()

        self.collections_table.setRowCount(len(collections))
        for idx, item in enumerate(collections):
            self.collections_table.setItem(idx, 0, QTableWidgetItem(str(item.get("payment_method", ""))))
            self.collections_table.setItem(idx, 1, QTableWidgetItem(format_currency(float(item.get("total", 0)))))
            self.collections_table.setItem(idx, 2, QTableWidgetItem(str(item.get("operations", 0))))
        self.collections_table.resizeColumnsToContents()

        self.debtors_table.setRowCount(len(debtors))
        for idx, item in enumerate(debtors):
            self.debtors_table.setItem(idx, 0, QTableWidgetItem(str(item.get("name", ""))))
            self.debtors_table.setItem(idx, 1, QTableWidgetItem(str(item.get("phone") or "-")))
            self.debtors_table.setItem(idx, 2, QTableWidgetItem(format_currency(float(item.get("debt_total", 0)))))
        self.debtors_table.resizeColumnsToContents()

    def _load_product_table(self, table: QTableWidget, items: list[dict]) -> None:
        table.setRowCount(len(items))
        for idx, item in enumerate(items):
            table.setItem(idx, 0, QTableWidgetItem(str(item.get("product_name", ""))))
            table.setItem(idx, 1, QTableWidgetItem(format_number(float(item.get("units", 0)))))
            table.setItem(idx, 2, QTableWidgetItem(format_currency(float(item.get("revenue", 0)))))
        table.resizeColumnsToContents()
