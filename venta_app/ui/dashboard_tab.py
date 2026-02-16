from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import WarehouseService
from .common import format_currency


class DashboardTab(QWidget):
    def __init__(self, service: WarehouseService) -> None:
        super().__init__()
        self.service = service

        root = QVBoxLayout(self)
        root.setSpacing(16)

        cards = QHBoxLayout()
        cards.setSpacing(12)

        self.products_card = self._create_card("Productos activos", "0")
        self.low_stock_card = self._create_card("Stock bajo", "0")
        self.today_card = self._create_card("Ventas hoy", "$ 0,00")
        self.month_card = self._create_card("Ventas mes", "$ 0,00")

        cards.addWidget(self.products_card)
        cards.addWidget(self.low_stock_card)
        cards.addWidget(self.today_card)
        cards.addWidget(self.month_card)

        root.addLayout(cards)

        low_stock_title = QLabel("Alertas de stock bajo")
        low_stock_title.setObjectName("sectionTitle")
        root.addWidget(low_stock_title)

        self.low_stock_table = QTableWidget(0, 4)
        self.low_stock_table.setHorizontalHeaderLabels(["Producto", "Codigo", "Stock", "Minimo"])
        self.low_stock_table.verticalHeader().setVisible(False)
        self.low_stock_table.setAlternatingRowColors(True)
        self.low_stock_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.low_stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.low_stock_table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(self.low_stock_table, stretch=1)

    def _create_card(self, title: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("kpiCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)

        title_label = QLabel(title)
        title_label.setObjectName("kpiTitle")
        value_label = QLabel(value)
        value_label.setObjectName("kpiValue")
        value_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)

        layout.addWidget(title_label)
        layout.addWidget(value_label)
        card.value_label = value_label
        return card

    def refresh(self) -> None:
        metrics = self.service.get_dashboard_metrics()
        low_stock = self.service.get_low_stock_products()

        self.products_card.value_label.setText(str(metrics["total_products"]))
        self.low_stock_card.value_label.setText(str(metrics["low_stock_products"]))
        self.today_card.value_label.setText(format_currency(metrics["today_sales_total"]))
        self.month_card.value_label.setText(format_currency(metrics["month_sales_total"]))

        self.low_stock_table.setRowCount(len(low_stock))
        for row_idx, item in enumerate(low_stock):
            self.low_stock_table.setItem(row_idx, 0, QTableWidgetItem(item["name"]))
            self.low_stock_table.setItem(row_idx, 1, QTableWidgetItem(item.get("barcode") or "-"))
            self.low_stock_table.setItem(row_idx, 2, QTableWidgetItem(str(item["stock"])))
            self.low_stock_table.setItem(row_idx, 3, QTableWidgetItem(str(item["min_stock"])))
