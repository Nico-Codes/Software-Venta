from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..services import WarehouseService
from .categories_tab import CategoriesTab
from .dashboard_tab import DashboardTab
from .inventory_tab import InventoryTab
from .pos_tab import POSTab
from .products_tab import ProductsTab
from .reports_tab import ReportsTab


APP_STYLE = """
QMainWindow {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #f2f7f5, stop: 1 #dce9e4);
}

QWidget {
    color: #1f2d2a;
    font-family: 'Segoe UI', 'Trebuchet MS', sans-serif;
    font-size: 13px;
}

QLabel#appTitle {
    font-size: 24px;
    font-weight: 700;
    color: #15322d;
    padding-bottom: 4px;
}

QLabel#appSubtitle {
    color: #4e6760;
    font-size: 12px;
    padding-bottom: 8px;
}

QFrame#panel {
    background: rgba(255, 255, 255, 0.75);
    border: 1px solid #c7d9d2;
    border-radius: 12px;
}

QFrame#kpiCard {
    background: rgba(255, 255, 255, 0.78);
    border: 1px solid #c7d9d2;
    border-radius: 12px;
}

QLabel#kpiTitle {
    color: #496661;
    font-size: 12px;
}

QLabel#kpiValue {
    font-size: 20px;
    font-weight: 700;
    color: #102822;
}

QLabel#sectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #173731;
}

QLabel#mutedText {
    color: #5a726d;
    font-size: 12px;
}

QFrame#totalPanel {
    background: #113b34;
    border-radius: 14px;
    padding: 8px;
}

QLabel#totalTitle {
    color: #d4ebe3;
    font-size: 14px;
    font-weight: 600;
}

QLabel#totalValue {
    color: #ffffff;
    font-size: 30px;
    font-weight: 800;
    letter-spacing: 1px;
}

QPushButton {
    background: #1e6b5b;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: #237763;
}

QPushButton:pressed {
    background: #165446;
}

QPushButton#chargeButton {
    background: #de6a1b;
    padding: 12px 22px;
    font-size: 16px;
    border-radius: 10px;
}

QPushButton#chargeButton:hover {
    background: #f17a2a;
}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #b8cec6;
    border-radius: 8px;
    padding: 6px;
}

QTableWidget, QListWidget {
    background: rgba(255, 255, 255, 0.95);
    border: 1px solid #c4d6d0;
    border-radius: 10px;
    gridline-color: #e5efeb;
    alternate-background-color: #f5faf8;
}

QHeaderView::section {
    background: #e4f0ec;
    border: none;
    border-right: 1px solid #d1e1db;
    border-bottom: 1px solid #d1e1db;
    padding: 6px;
    font-weight: 600;
}

QTabWidget::pane {
    border: 1px solid #c4d6d0;
    border-radius: 10px;
    background: rgba(255, 255, 255, 0.65);
}

QTabBar::tab {
    background: #dbe9e4;
    border: 1px solid #bfd4cc;
    border-bottom: none;
    padding: 8px 12px;
    margin-right: 3px;
    border-top-left-radius: 8px;
    border-top-right-radius: 8px;
}

QTabBar::tab:selected {
    background: #ffffff;
    color: #12332d;
}
"""


class MainWindow(QMainWindow):
    def __init__(self, service: WarehouseService) -> None:
        super().__init__()
        self.service = service

        self.setWindowTitle("Venta Local - Almacen/Vinoteca")
        self.resize(1400, 860)
        self.setStyleSheet(APP_STYLE)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(16, 14, 16, 16)

        title = QLabel("Sistema de Gestion para Almacen / Vinoteca")
        title.setObjectName("appTitle")
        subtitle = QLabel("Local, offline y optimizado para mostrador")
        subtitle.setObjectName("appSubtitle")

        root.addWidget(title)
        root.addWidget(subtitle)

        self.tabs = QTabWidget()

        self.dashboard_tab = DashboardTab(self.service)
        self.pos_tab = POSTab(self.service, on_data_changed=self.refresh_all)
        self.products_tab = ProductsTab(self.service, on_data_changed=self.refresh_all)
        self.categories_tab = CategoriesTab(self.service, on_data_changed=self.refresh_all)
        self.inventory_tab = InventoryTab(self.service, on_data_changed=self.refresh_all)
        self.reports_tab = ReportsTab(self.service)

        self.tabs.addTab(self.dashboard_tab, "Panel")
        self.tabs.addTab(self.pos_tab, "Venta (POS)")
        self.tabs.addTab(self.products_tab, "Productos")
        self.tabs.addTab(self.categories_tab, "Categorias y margenes")
        self.tabs.addTab(self.inventory_tab, "Inventario")
        self.tabs.addTab(self.reports_tab, "Reportes")

        self.tabs.currentChanged.connect(self.on_tab_change)

        root.addWidget(self.tabs, stretch=1)

        self.setCentralWidget(container)

        self.refresh_all()

    def on_tab_change(self, index: int) -> None:
        tab_text = self.tabs.tabText(index)
        if tab_text == "Venta (POS)":
            self.pos_tab.focus_scan()

    def refresh_all(self) -> None:
        self.dashboard_tab.refresh()
        self.pos_tab.refresh()
        self.products_tab.refresh()
        self.categories_tab.refresh()
        self.inventory_tab.refresh()
        self.reports_tab.refresh()
