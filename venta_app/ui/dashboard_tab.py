from __future__ import annotations

from PySide6.QtCharts import (
    QBarCategoryAxis,
    QBarSeries,
    QBarSet,
    QChart,
    QChartView,
    QLineSeries,
    QValueAxis,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter
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
        root.setSpacing(12)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.month_sales_card = self._create_card("Ventas mes", "$ 0,00")
        self.month_profit_card = self._create_card("Ganancia mes", "$ 0,00")
        self.receivables_card = self._create_card("Deuda clientes", "$ 0,00")
        self.month_tickets_card = self._create_card("Tickets mes", "0")
        cards.addWidget(self.month_sales_card)
        cards.addWidget(self.month_profit_card)
        cards.addWidget(self.receivables_card)
        cards.addWidget(self.month_tickets_card)
        root.addLayout(cards)

        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)

        self.finance_chart = QChartView()
        self.finance_chart.setRenderHint(QPainter.RenderHint.Antialiasing)
        charts_row.addWidget(self._wrap_chart("Finanzas ultimos 30 dias", self.finance_chart), stretch=2)

        self.products_chart = QChartView()
        self.products_chart.setRenderHint(QPainter.RenderHint.Antialiasing)
        charts_row.addWidget(self._wrap_chart("Top vs menos vendidos", self.products_chart), stretch=1)

        root.addLayout(charts_row, stretch=1)

        tables_row = QHBoxLayout()
        tables_row.setSpacing(12)

        self.low_stock_table = QTableWidget(0, 4)
        self.low_stock_table.setHorizontalHeaderLabels(["Producto", "Codigo", "Stock", "Minimo"])
        self.low_stock_table.verticalHeader().setVisible(False)
        self.low_stock_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.low_stock_table.horizontalHeader().setStretchLastSection(True)

        self.debt_alert_table = QTableWidget(0, 4)
        self.debt_alert_table.setHorizontalHeaderLabels(["Cliente", "Telefono", "Deuda", "Limite"])
        self.debt_alert_table.verticalHeader().setVisible(False)
        self.debt_alert_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.debt_alert_table.horizontalHeader().setStretchLastSection(True)

        tables_row.addWidget(self._wrap_table("Alertas de stock", self.low_stock_table), stretch=1)
        tables_row.addWidget(self._wrap_table("Alertas de deuda", self.debt_alert_table), stretch=1)
        root.addLayout(tables_row, stretch=1)

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

    def _wrap_chart(self, title: str, chart: QChartView) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        layout.addWidget(chart, stretch=1)
        return frame

    def _wrap_table(self, title: str, table: QTableWidget) -> QFrame:
        frame = QFrame()
        frame.setObjectName("panel")
        layout = QVBoxLayout(frame)
        title_label = QLabel(title)
        title_label.setObjectName("sectionTitle")
        layout.addWidget(title_label)
        layout.addWidget(table, stretch=1)
        return frame

    def refresh(self) -> None:
        metrics = self.service.get_dashboard_metrics()
        low_stock = self.service.get_low_stock_products()
        debt_alerts = self.service.get_customers_over_limit()
        finance_series = self.service.get_finance_series(30)
        top_products = self.service.get_top_products(limit=5)
        low_products = self.service.get_top_products(limit=5, ascending=True)

        self.month_sales_card.value_label.setText(format_currency(metrics["month_sales_total"]))
        self.month_profit_card.value_label.setText(format_currency(metrics["month_profit_total"]))
        self.receivables_card.value_label.setText(format_currency(metrics["receivables_total"]))
        self.month_tickets_card.value_label.setText(str(metrics["month_tickets"]))

        self._load_low_stock(low_stock)
        self._load_debt_alerts(debt_alerts)
        self._render_finance_chart(finance_series)
        self._render_products_chart(top_products, low_products)

    def _load_low_stock(self, rows: list[dict]) -> None:
        self.low_stock_table.setRowCount(len(rows))
        for idx, item in enumerate(rows):
            self.low_stock_table.setItem(idx, 0, QTableWidgetItem(str(item.get("name", ""))))
            self.low_stock_table.setItem(idx, 1, QTableWidgetItem(str(item.get("barcode") or "-")))
            self.low_stock_table.setItem(idx, 2, QTableWidgetItem(str(item.get("stock"))))
            self.low_stock_table.setItem(idx, 3, QTableWidgetItem(str(item.get("min_stock"))))
        self.low_stock_table.resizeColumnsToContents()

    def _load_debt_alerts(self, rows: list[dict]) -> None:
        self.debt_alert_table.setRowCount(len(rows))
        for idx, item in enumerate(rows):
            self.debt_alert_table.setItem(idx, 0, QTableWidgetItem(str(item.get("name", ""))))
            self.debt_alert_table.setItem(idx, 1, QTableWidgetItem(str(item.get("phone") or "-")))
            self.debt_alert_table.setItem(idx, 2, QTableWidgetItem(format_currency(float(item.get("debt_total", 0)))))
            self.debt_alert_table.setItem(idx, 3, QTableWidgetItem(format_currency(float(item.get("alert_limit", 0)))))
        self.debt_alert_table.resizeColumnsToContents()

    def _render_finance_chart(self, series_data: list[dict]) -> None:
        chart = QChart()
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.setBackgroundVisible(False)

        revenue = QLineSeries()
        revenue.setName("Ventas")
        revenue.setColor(Qt.GlobalColor.darkGreen)

        profit = QLineSeries()
        profit.setName("Ganancia")
        profit.setColor(Qt.GlobalColor.darkBlue)

        max_value = 0.0
        for idx, point in enumerate(series_data):
            day_idx = float(idx + 1)
            revenue_value = float(point.get("revenue", 0))
            profit_value = float(point.get("profit", 0))
            revenue.append(day_idx, revenue_value)
            profit.append(day_idx, profit_value)
            max_value = max(max_value, revenue_value, profit_value)

        chart.addSeries(revenue)
        chart.addSeries(profit)

        axis_x = QValueAxis()
        axis_x.setRange(1, max(1, len(series_data)))
        axis_x.setLabelFormat("%d")
        axis_x.setTitleText("Dias")
        axis_x.setTickCount(8)

        axis_y = QValueAxis()
        upper = max(max_value * 1.15, 1000)
        axis_y.setRange(0, upper)
        axis_y.setLabelFormat("%.0f")
        axis_y.setTitleText("Monto")

        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        revenue.attachAxis(axis_x)
        revenue.attachAxis(axis_y)
        profit.attachAxis(axis_x)
        profit.attachAxis(axis_y)

        self.finance_chart.setChart(chart)

    def _render_products_chart(self, top_products: list[dict], low_products: list[dict]) -> None:
        chart = QChart()
        chart.setAnimationOptions(QChart.AnimationOption.SeriesAnimations)
        chart.legend().setVisible(True)
        chart.legend().setAlignment(Qt.AlignmentFlag.AlignBottom)
        chart.setBackgroundVisible(False)

        top_set = QBarSet("Mas vendidos")
        top_set.setColor(Qt.GlobalColor.darkGreen)
        low_set = QBarSet("Menos vendidos")
        low_set.setColor(Qt.GlobalColor.darkYellow)

        categories: list[str] = []
        for item in top_products:
            name = str(item.get("product_name", ""))[:12]
            categories.append(name)
            top_set.append(float(item.get("units", 0)))
            low_set.append(0.0)

        for item in low_products:
            name = str(item.get("product_name", ""))[:12]
            categories.append(name)
            top_set.append(0.0)
            low_set.append(float(item.get("units", 0)))

        series = QBarSeries()
        series.append(top_set)
        series.append(low_set)
        chart.addSeries(series)

        axis_x = QBarCategoryAxis()
        axis_x.append(categories if categories else ["Sin datos"])
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        axis_y = QValueAxis()
        max_unit = 1.0
        for item in top_products + low_products:
            max_unit = max(max_unit, float(item.get("units", 0)))
        axis_y.setRange(0, max_unit * 1.2)
        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        self.products_chart.setChart(chart)
