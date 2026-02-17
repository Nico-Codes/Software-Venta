from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QStackedWidget,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import WarehouseService
from .backup_tab import BackupTab
from .categories_tab import CategoriesTab
from .customers_tab import CustomersTab
from .dashboard_tab import DashboardTab
from .inventory_tab import InventoryTab
from .pos_tab import POSTab
from .products_tab import ProductsTab
from .reports_tab import ReportsTab
from .users_tab import UsersTab
from .effects import apply_button_effects


COMBO_ARROW_DOWN_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAwAAAAICAYAAADN5B7xAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAgElEQVQYlWMWsIy1//Hk0kMGAkDIKqaeW16PkYmF+T+jkFVMPSHFDAxMjG+OLDnA9ObIkgMMDEw4NcEUvzu2qAFNIq4BXZOQVUy9kFUcqkJcmnApZsSmiYHhvzwDA+NDDGcwMDAwoQu8O7aogZHxP+O////343QKNiBiE+OATRwAq8osbKnOX4gAAAAASUVORK5CYII="
)

COMBO_ARROW_RIGHT_ICON_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAgAAAAMCAYAAABfnvydAAAACXBIWXMAAA7EAAAOxAGVKw4bAAAAR0lEQVQYlWMQsYlxYMADmP79Y7AXsoprwKeIQcgqpp52ihixKWJgYGL89///fhbm/xjyUEWx84WtYxaQ7hYaSQpYxtrjC24AOm8e26IdwfkAAAAASUVORK5CYII="
)


def _write_temp_icon(filename: str, icon_b64: str) -> str:
    target = Path(tempfile.gettempdir()) / filename
    try:
        if not target.exists():
            target.write_bytes(base64.b64decode(icon_b64))
        return target.as_posix()
    except OSError:
        return ""


APP_STYLE_TEMPLATE = """
QMainWindow {
    background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 1,
        stop: 0 #e9f2ff, stop: 0.48 #f4f9ff, stop: 1 #ffffff);
}

QWidget {
    color: #122b42;
    font-family: 'Segoe UI Variable', 'Segoe UI', 'Calibri', sans-serif;
    font-size: 13px;
}

QLabel#appTitle {
    font-size: 24px;
    font-weight: 800;
    color: #0f2f4c;
    letter-spacing: 0.5px;
}

QLabel#appSubtitle {
    color: #60758a;
    font-size: 12px;
}

QLabel#roleBadge {
    background: #ecf5ff;
    color: #0f5188;
    border: 1px solid #c6def7;
    border-radius: 12px;
    padding: 7px 13px;
    font-weight: 700;
}

QFrame#headerPanel {
    background: #f9fcff;
    border: 1px solid #d2e4f8;
    border-radius: 18px;
}

QFrame#shellPanel {
    background: #f7fbff;
    border: 1px solid #d3e5f8;
    border-radius: 18px;
}

QFrame#panel {
    background: #fbfdff;
    border: 1px solid #d6e6f7;
    border-radius: 15px;
}

QFrame#kpiCard {
    background: #ffffff;
    border: 1px solid #d7e7f8;
    border-radius: 15px;
}

QLabel#kpiTitle {
    color: #5e7488;
    font-size: 12px;
}

QLabel#kpiValue {
    font-size: 22px;
    font-weight: 800;
    color: #0e3a63;
}

QLabel#sectionTitle {
    font-size: 14px;
    font-weight: 800;
    color: #124268;
    letter-spacing: 0.2px;
}

QLabel#mutedText {
    color: #61778d;
    font-size: 12px;
}

QLabel#dangerText {
    color: #cb4f45;
    font-size: 12px;
    font-weight: 700;
}

QLabel#successText {
    color: #187a53;
    font-size: 12px;
    font-weight: 700;
}

QFrame#totalPanel {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0f3f71, stop:1 #1f5f9f);
    border: 1px solid #1b5b97;
    border-radius: 15px;
    padding: 10px;
}

QLabel#totalTitle {
    color: #dbeafc;
    font-size: 14px;
    font-weight: 700;
}

QLabel#totalValue {
    color: #ffffff;
    font-size: 32px;
    font-weight: 900;
    letter-spacing: 0.7px;
}

QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2e7de9, stop:1 #2571dd);
    color: #ffffff;
    border: 1px solid #1f67cf;
    border-radius: 11px;
    padding: 9px 15px;
    font-weight: 700;
    text-align: center;
}

QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3d8bf2, stop:1 #317ce7);
}

QPushButton:pressed {
    background: #2365c5;
}

QPushButton:checked {
    background: #1e5cb2;
}

QPushButton:disabled {
    background: #b5c8de;
    border: 1px solid #b5c8de;
    color: #f1f6fb;
}

QPushButton#chargeButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #007fd9, stop:1 #0369be);
    border: 1px solid #025da9;
    padding: 12px 20px;
    font-size: 16px;
    border-radius: 12px;
}

QPushButton#chargeButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #0a8ce8, stop:1 #0b74cc);
}

QPushButton#chargeButton:pressed {
    background: #045da8;
}

QPushButton#partialToggleButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #5f7ea0, stop:1 #4a6b8f);
    border: 1px solid #456280;
}

QPushButton#partialToggleButton:hover {
    background: #5a80a9;
}

QPushButton#partialToggleButton:checked {
    background: #1d5cb1;
    border: 1px solid #194f99;
}

QPushButton#stepPlusButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3391f6, stop:1 #257de0);
    border: 1px solid #236fc6;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    border-radius: 17px;
    font-size: 18px;
    font-weight: 700;
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    text-align: center;
    padding: 0 0 1px 0;
}

QPushButton#stepPlusButton:hover {
    background: #48a1ff;
}

QPushButton#stepPlusButton:pressed {
    background: #2470ca;
}

QPushButton#stepMinusButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #6887ac, stop:1 #56779f);
    border: 1px solid #4e6d92;
    min-width: 34px;
    max-width: 34px;
    min-height: 34px;
    max-height: 34px;
    border-radius: 17px;
    font-size: 18px;
    font-weight: 700;
    font-family: 'Segoe UI Symbol', 'Segoe UI', sans-serif;
    text-align: center;
    padding: 0 0 1px 0;
}

QPushButton#stepMinusButton:hover {
    background: #7596bb;
}

QPushButton#stepMinusButton:pressed {
    background: #4c6f98;
}

QLineEdit#scanInput, QLineEdit#stockScanInput {
    font-size: 17px;
    font-weight: 700;
    color: #0e355a;
    padding: 9px 11px;
    border: 2px solid #88b8e6;
    border-radius: 12px;
    background: #ffffff;
}

QLineEdit#scanInput:focus, QLineEdit#stockScanInput:focus {
    border: 2px solid #1f87e3;
}

QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QTextEdit {
    background: #ffffff;
    border: 1px solid #c6dcee;
    border-radius: 11px;
    padding: 7px;
    selection-background-color: #d6e9ff;
    selection-color: #133551;
}

QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #2f85dd;
    background: #ffffff;
}

QComboBox, QSpinBox, QDoubleSpinBox {
    padding-right: 30px;
}

QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {
    border: 1px solid #7caee0;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid #bfd7ef;
    background: #e7f2ff;
    border-top-right-radius: 11px;
    border-bottom-right-radius: 11px;
}

QComboBox::down-arrow {
    image: url("__COMBO_ARROW_RIGHT__");
    width: 12px;
    height: 8px;
}

QComboBox:on::down-arrow {
    image: url("__COMBO_ARROW_DOWN__");
}

QComboBox:on {
    border: 1px solid #3188df;
}

QComboBox:on::drop-down {
    background: #d9ebff;
}

QSpinBox::up-button, QDoubleSpinBox::up-button {
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 22px;
    border-left: 1px solid #cbdaee;
    border-bottom: 1px solid #d9e6f3;
    border-top-right-radius: 11px;
    background: #edf5ff;
}

QSpinBox::down-button, QDoubleSpinBox::down-button {
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 22px;
    border-left: 1px solid #cbdaee;
    border-bottom-right-radius: 11px;
    background: #edf5ff;
}

QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
    background: #e0eeff;
}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
    width: 10px;
    height: 10px;
}

QComboBox QAbstractItemView {
    background: #fbfeff;
    border: 1px solid #bdd4ea;
    border-radius: 10px;
    selection-background-color: #d9ebff;
    selection-color: #143352;
    outline: 0;
    padding: 4px;
}

QComboBox#customerCombo,
QComboBox#paymentCombo {
    min-height: 36px;
    border: 1px solid #b9d4ec;
    background: #ffffff;
    font-weight: 700;
    color: #123a5d;
    padding-left: 10px;
}

QComboBox#customerCombo:hover,
QComboBox#paymentCombo:hover {
    border: 1px solid #8db8e0;
    background: #fbfdff;
}

QComboBox#customerCombo:focus,
QComboBox#paymentCombo:focus {
    border: 1px solid #3188df;
}

QComboBox#paymentCombo {
    min-width: 180px;
}

QComboBox#customerCombo::drop-down,
QComboBox#paymentCombo::drop-down {
    width: 30px;
    border-left: 1px solid #c4daef;
    background: #e9f3ff;
    border-top-right-radius: 11px;
    border-bottom-right-radius: 11px;
}

QComboBox#customerCombo QLineEdit {
    border: 0;
    background: transparent;
    color: #123a5d;
    font-weight: 600;
    padding: 0 4px 0 0;
}

QComboBox#customerCombo QAbstractItemView::item,
QComboBox#paymentCombo QAbstractItemView::item {
    min-height: 28px;
    padding: 6px 8px;
    border-radius: 6px;
}

QComboBox#customerCombo QAbstractItemView::item:selected,
QComboBox#paymentCombo QAbstractItemView::item:selected {
    background: #d7eaff;
    border: 0;
    outline: 0;
}

QTableWidget, QListWidget {
    background: #ffffff;
    border: 1px solid #d3e2f1;
    border-radius: 12px;
    gridline-color: #e6eef7;
    alternate-background-color: #f8fbff;
}

QTableWidget::item:selected, QListWidget::item:selected {
    background: #d9ebff;
    color: #133450;
}

QHeaderView::section {
    background: #f0f6fd;
    border: none;
    border-right: 1px solid #d9e6f3;
    border-bottom: 1px solid #d9e6f3;
    padding: 7px 6px;
    font-weight: 700;
    color: #1a4268;
}

QTreeWidget#sideNav {
    background: #fbfdff;
    border: 1px solid #d3e4f4;
    border-radius: 13px;
    padding: 9px;
    outline: 0;
    show-decoration-selected: 1;
}

QTreeWidget#sideNav::item {
    border: 1px solid transparent;
    border-radius: 10px;
    padding: 9px 9px;
    margin: 2px 0;
    color: #1d4568;
    font-weight: 600;
}

QTreeWidget#sideNav::item:selected,
QTreeWidget#sideNav::item:selected:active {
    background: #d8ebff;
    border: 1px solid #b9d8f7;
    border-left: 4px solid #2288e5;
    color: #0f3a60;
}

QTreeWidget#sideNav::item:hover:!selected {
    background: #edf5ff;
    border: 1px solid #dce9f7;
}

QTreeWidget#sideNav::branch:has-children {
    background: transparent;
}

QTreeWidget#sideNav::branch:open:has-children:has-siblings,
QTreeWidget#sideNav::branch:closed:has-children:has-siblings {
    border-image: none;
}

QStackedWidget#contentStack {
    background: #f8fcff;
    border: 1px solid #d3e5f8;
    border-radius: 13px;
}

QFrame#stackPage {
    background: #f9fdff;
    border-radius: 12px;
}

QScrollBar:vertical {
    background: transparent;
    width: 11px;
    margin: 2px;
}

QScrollBar::handle:vertical {
    background: #bfd8f2;
    min-height: 30px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #a9cdef;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
"""

APP_STYLE = (
    APP_STYLE_TEMPLATE
    .replace("__COMBO_ARROW_RIGHT__", _write_temp_icon("venta_local_combo_arrow_right.png", COMBO_ARROW_RIGHT_ICON_B64))
    .replace("__COMBO_ARROW_DOWN__", _write_temp_icon("venta_local_combo_arrow_down.png", COMBO_ARROW_DOWN_ICON_B64))
)


class MainWindow(QMainWindow):
    def __init__(self, service: WarehouseService, current_user: dict[str, str]) -> None:
        super().__init__()
        self.service = service
        self.current_user = current_user
        self.is_admin = self.current_user["role"] == "admin"
        self.current_page_key = ""

        self.setWindowTitle("Venta Local - Almacen/Vinoteca")
        self.resize(1500, 900)
        self.setStyleSheet(APP_STYLE)

        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(16, 14, 16, 16)
        root.setSpacing(10)

        header_card = QFrame()
        header_card.setObjectName("headerPanel")
        header = QHBoxLayout(header_card)
        header.setContentsMargins(14, 11, 14, 11)

        title_box = QVBoxLayout()
        title = QLabel("Sistema de Gestion para Almacen / Vinoteca")
        title.setObjectName("appTitle")
        subtitle = QLabel("Local, offline, optimizado para mostrador y control de deudas")
        subtitle.setObjectName("appSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)

        role_text = "Administrador" if self.current_user["role"] == "admin" else "Vendedor"
        role_badge = QLabel(f"{role_text}: {self.current_user['username']}")
        role_badge.setObjectName("roleBadge")

        header.addLayout(title_box)
        header.addStretch(1)
        header.addWidget(role_badge)
        root.addWidget(header_card)

        shell = QFrame()
        shell.setObjectName("shellPanel")
        content = QHBoxLayout(shell)
        content.setContentsMargins(10, 10, 10, 10)
        content.setSpacing(10)

        self.nav = QTreeWidget()
        self.nav.setObjectName("sideNav")
        self.nav.setHeaderHidden(True)
        self.nav.setRootIsDecorated(False)
        self.nav.setIndentation(14)
        self.nav.setMinimumWidth(238)
        self.nav.setIconSize(QSize(18, 18))
        self.nav.setUniformRowHeights(True)
        self.nav.setExpandsOnDoubleClick(False)
        self.nav.setAnimated(True)
        self.nav.itemClicked.connect(self.on_nav_clicked)

        self.stack = QStackedWidget()
        self.stack.setObjectName("contentStack")
        self.stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        content.addWidget(self.nav, stretch=0)
        content.addWidget(self.stack, stretch=1)
        root.addWidget(shell, stretch=1)

        self.dashboard_tab = DashboardTab(self.service)
        self.pos_tab = POSTab(self.service, on_data_changed=self.refresh_all)

        self.products_tab: ProductsTab | None = None
        self.categories_tab: CategoriesTab | None = None
        self.inventory_tab: InventoryTab | None = None
        self.customers_tab: CustomersTab | None = None
        self.reports_tab: ReportsTab | None = None
        self.users_tab: UsersTab | None = None
        self.backup_tab: BackupTab | None = None

        self.page_map: dict[str, QWidget] = {}
        self.item_map: dict[str, QTreeWidgetItem] = {}

        self._build_navigation(show_stock=self.is_admin, show_utilities=self.is_admin)

        if self.is_admin:
            self._add_page("venta", self.pos_tab, "Venta rapida", self._icon("play"))

            self.products_tab = ProductsTab(self.service, on_data_changed=self.refresh_all)
            self.categories_tab = CategoriesTab(self.service, on_data_changed=self.refresh_all)
            self.inventory_tab = InventoryTab(self.service, on_data_changed=self.refresh_all)
            self.customers_tab = CustomersTab(self.service, on_data_changed=self.refresh_all)
            self.reports_tab = ReportsTab(self.service)
            self.users_tab = UsersTab(self.service, on_data_changed=self.refresh_all)
            self.backup_tab = BackupTab(self.service, on_data_changed=self.refresh_all)

            if self.inventory_tab:
                self._add_page("stock", self.inventory_tab, "Agregar stock", self._icon("stock"))
            self._add_page("panel", self.dashboard_tab, "Panel", self._icon("panel"), group="utilidades")
            self._add_page("productos", self.products_tab, "Productos", self._icon("products"), group="utilidades")
            self._add_page("categorias", self.categories_tab, "Categorias", self._icon("categories"), group="utilidades")
            self._add_page("clientes", self.customers_tab, "Clientes y deudas", self._icon("customers"), group="utilidades")
            self._add_page("reportes", self.reports_tab, "Reportes", self._icon("reports"), group="utilidades")
            self._add_page("usuarios", self.users_tab, "Usuarios", self._icon("users"), group="utilidades")
            self._add_page("backup", self.backup_tab, "Respaldo", self._icon("backup"), group="utilidades")
        else:
            self._add_page("venta", self.pos_tab, "Venta rapida", self._icon("play"))

        self.setCentralWidget(container)
        apply_button_effects(self)

        default_key = "venta"
        self.select_page(default_key)
        self.refresh_all()

    def _build_navigation(self, show_stock: bool, show_utilities: bool) -> None:
        self.nav.clear()
        self.item_map.clear()

        self.item_map["venta"] = QTreeWidgetItem(self.nav, ["Venta rapida"])
        self.item_map["venta"].setIcon(0, self._icon("play"))

        if show_stock:
            self.item_map["stock"] = QTreeWidgetItem(self.nav, ["Agregar stock"])
            self.item_map["stock"].setIcon(0, self._icon("stock"))

        if show_utilities:
            util = QTreeWidgetItem(self.nav, ["Utilidades"])
            util.setIcon(0, self._icon("tools"))
            util.setData(0, Qt.ItemDataRole.UserRole + 1, "Utilidades")
            util.setExpanded(False)
            self._update_group_label(util)
            self.item_map["utilidades"] = util

    def _icon(self, name: str) -> QIcon:
        style = self.style()
        icons = {
            "play": QStyle.StandardPixmap.SP_MediaPlay,
            "stock": QStyle.StandardPixmap.SP_ArrowUp,
            "tools": QStyle.StandardPixmap.SP_FileDialogDetailedView,
            "panel": QStyle.StandardPixmap.SP_DesktopIcon,
            "products": QStyle.StandardPixmap.SP_DirIcon,
            "categories": QStyle.StandardPixmap.SP_DirOpenIcon,
            "customers": QStyle.StandardPixmap.SP_FileDialogContentsView,
            "reports": QStyle.StandardPixmap.SP_FileDialogListView,
            "users": QStyle.StandardPixmap.SP_DialogYesButton,
            "backup": QStyle.StandardPixmap.SP_DialogSaveButton,
        }
        return style.standardIcon(icons.get(name, QStyle.StandardPixmap.SP_FileIcon))

    def _add_page(
        self,
        key: str,
        widget: QWidget,
        label: str,
        icon: QIcon,
        group: str | None = None,
    ) -> None:
        if group:
            parent_item = self.item_map[group]
            item = QTreeWidgetItem(parent_item, [label])
        else:
            item = self.item_map[key]
            item.setText(0, label)
        item.setIcon(0, icon)
        item.setData(0, Qt.ItemDataRole.UserRole, key)
        self.item_map[key] = item
        page = QFrame()
        page.setObjectName("stackPage")
        page.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(8, 8, 8, 8)
        page_layout.setSpacing(0)
        page_layout.addWidget(widget)
        self.page_map[key] = page
        self.stack.addWidget(page)

    def select_page(self, key: str) -> None:
        item = self.item_map.get(key)
        widget = self.page_map.get(key)
        if not item or not widget:
            return
        self.current_page_key = key
        self.nav.setCurrentItem(item)
        self.stack.setCurrentWidget(widget)
        if key == "venta":
            self.pos_tab.focus_scan()

    def _update_group_label(self, item: QTreeWidgetItem) -> None:
        base = str(item.data(0, Qt.ItemDataRole.UserRole + 1) or "Utilidades")
        prefix = "▾" if item.isExpanded() else "▸"
        item.setText(0, f"{prefix} {base}")

    def on_nav_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        key = item.data(0, Qt.ItemDataRole.UserRole)
        if not key:
            item.setExpanded(not item.isExpanded())
            self._update_group_label(item)
            current_item = self.item_map.get(self.current_page_key)
            if current_item:
                self.nav.setCurrentItem(current_item)
            return
        self.select_page(str(key))

    def refresh_all(self) -> None:
        if self.is_admin:
            self.dashboard_tab.refresh()
        self.pos_tab.refresh()

        if self.products_tab:
            self.products_tab.refresh()
        if self.categories_tab:
            self.categories_tab.refresh()
        if self.inventory_tab:
            self.inventory_tab.refresh()
        if self.customers_tab:
            self.customers_tab.refresh()
        if self.reports_tab:
            self.reports_tab.refresh()
        if self.users_tab:
            self.users_tab.refresh()
        if self.backup_tab:
            self.backup_tab.refresh()
        apply_button_effects(self)
