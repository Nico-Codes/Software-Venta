from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..pricing import calculate_auto_price
from ..services import ValidationError, WarehouseService
from .common import format_currency, format_number


class ProductsTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.current_product_id: int | None = None

        root = QVBoxLayout(self)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar por nombre o codigo")
        self.search_input.returnPressed.connect(self.refresh)

        self.search_btn = QPushButton("Buscar")
        self.search_btn.clicked.connect(self.refresh)
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.clicked.connect(self.new_product)

        toolbar.addWidget(self.search_input, stretch=1)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.new_btn)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        body.setSpacing(14)

        self.table = QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Nombre",
                "Codigo",
                "Categoria",
                "Costo",
                "Precio",
                "Auto",
                "Stock",
                "Min",
                "Activo",
            ]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_table_selection)
        self.table.horizontalHeader().setStretchLastSection(True)

        body.addWidget(self.table, stretch=3)

        form_frame = QFrame()
        form_frame.setObjectName("panel")
        form_layout = QVBoxLayout(form_frame)

        form_title = QLabel("Ficha de producto")
        form_title.setObjectName("sectionTitle")

        self.id_info = QLabel("ID: nuevo")
        self.id_info.setObjectName("mutedText")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.name_input = QLineEdit()
        self.barcode_input = QLineEdit()

        self.category_combo = QComboBox()
        self.category_combo.currentIndexChanged.connect(self.on_auto_fields_changed)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 9_999_999)
        self.cost_input.setDecimals(2)
        self.cost_input.valueChanged.connect(self.on_auto_fields_changed)

        self.sale_price_input = QDoubleSpinBox()
        self.sale_price_input.setRange(0, 9_999_999)
        self.sale_price_input.setDecimals(2)

        self.auto_price_check = QCheckBox("Precio automatico")
        self.auto_price_check.setChecked(True)
        self.auto_price_check.toggled.connect(self.on_auto_fields_changed)

        self.stock_input = QDoubleSpinBox()
        self.stock_input.setRange(0, 9_999_999)
        self.stock_input.setDecimals(2)

        self.min_stock_input = QDoubleSpinBox()
        self.min_stock_input.setRange(0, 9_999_999)
        self.min_stock_input.setDecimals(2)

        self.active_check = QCheckBox("Producto activo")
        self.active_check.setChecked(True)

        self.auto_preview = QLabel("Precio calculado por margen")
        self.auto_preview.setObjectName("mutedText")

        form.addRow("Nombre", self.name_input)
        form.addRow("Codigo de barras", self.barcode_input)
        form.addRow("Categoria", self.category_combo)
        form.addRow("Costo", self.cost_input)
        form.addRow("Precio venta", self.sale_price_input)
        form.addRow("", self.auto_price_check)
        form.addRow("Stock actual", self.stock_input)
        form.addRow("Stock minimo", self.min_stock_input)
        form.addRow("", self.active_check)

        form_layout.addWidget(form_title)
        form_layout.addWidget(self.id_info)
        form_layout.addLayout(form)
        form_layout.addWidget(self.auto_preview)

        actions = QHBoxLayout()
        self.save_btn = QPushButton("Guardar")
        self.save_btn.clicked.connect(self.save_product)
        actions.addWidget(self.save_btn)
        actions.addStretch(1)

        form_layout.addLayout(actions)
        form_layout.addStretch(1)

        body.addWidget(form_frame, stretch=2)
        root.addLayout(body, stretch=1)

        self.load_categories()
        self.new_product()

    def load_categories(self) -> None:
        categories = self.service.list_categories()

        self.category_combo.blockSignals(True)
        self.category_combo.clear()

        for category in categories:
            payload = {
                "id": int(category["id"]),
                "margin": float(category["margin_percent"]),
                "name": category["name"],
            }
            self.category_combo.addItem(category["name"], payload)

        self.category_combo.blockSignals(False)
        self.on_auto_fields_changed()

    def refresh(self) -> None:
        self.load_categories()
        term = self.search_input.text().strip()
        products = self.service.list_products(search=term)
        self.table.setRowCount(len(products))

        for row_idx, product in enumerate(products):
            id_item = QTableWidgetItem(str(product["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, int(product["id"]))
            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(product["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(product.get("barcode") or "-"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(product["category_name"]))
            self.table.setItem(row_idx, 4, QTableWidgetItem(format_currency(float(product["cost"]))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(format_currency(float(product["sale_price"]))))
            self.table.setItem(row_idx, 6, QTableWidgetItem("Si" if product["auto_price"] else "No"))
            self.table.setItem(row_idx, 7, QTableWidgetItem(format_number(float(product["stock"]))))
            self.table.setItem(row_idx, 8, QTableWidgetItem(format_number(float(product["min_stock"]))))
            self.table.setItem(row_idx, 9, QTableWidgetItem("Si" if product["active"] else "No"))

        self.table.resizeColumnsToContents()

    def new_product(self) -> None:
        self.current_product_id = None
        self.id_info.setText("ID: nuevo")
        self.name_input.clear()
        self.barcode_input.clear()
        self.cost_input.setValue(0)
        self.sale_price_input.setValue(0)
        self.auto_price_check.setChecked(True)
        self.stock_input.setValue(0)
        self.min_stock_input.setValue(0)
        self.active_check.setChecked(True)
        self.on_auto_fields_changed()

    def selected_category_payload(self) -> dict[str, Any] | None:
        payload = self.category_combo.currentData()
        return payload if isinstance(payload, dict) else None

    def on_auto_fields_changed(self) -> None:
        auto_enabled = self.auto_price_check.isChecked()
        self.sale_price_input.setEnabled(not auto_enabled)

        if not auto_enabled:
            self.auto_preview.setText("Precio manual")
            return

        category = self.selected_category_payload()
        if not category:
            self.auto_preview.setText("Crea una categoria para calcular")
            return

        cost = float(self.cost_input.value())
        margin = float(category["margin"])
        suggested = calculate_auto_price(cost, margin, self.service.get_rounding_base())
        self.sale_price_input.setValue(suggested)
        self.auto_preview.setText(
            f"{category['name']} ({margin:.2f}%) -> {format_currency(suggested)}"
        )

    def on_table_selection(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return

        product_id = int(id_item.data(Qt.ItemDataRole.UserRole))
        product = self.service.get_product(product_id)

        self.current_product_id = product_id
        self.id_info.setText(f"ID: {product_id}")
        self.name_input.setText(product["name"])
        self.barcode_input.setText(product.get("barcode") or "")

        idx = self.find_category_index(int(product["category_id"]))
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)

        self.cost_input.setValue(float(product["cost"]))
        self.sale_price_input.setValue(float(product["sale_price"]))
        self.auto_price_check.setChecked(bool(product["auto_price"]))
        self.stock_input.setValue(float(product["stock"]))
        self.min_stock_input.setValue(float(product["min_stock"]))
        self.active_check.setChecked(bool(product["active"]))
        self.on_auto_fields_changed()

    def save_product(self) -> None:
        payload = self.selected_category_payload()
        if not payload:
            QMessageBox.warning(self, "Sin categorias", "Debes crear al menos una categoria")
            return

        kwargs = {
            "name": self.name_input.text(),
            "barcode": self.barcode_input.text(),
            "category_id": int(payload["id"]),
            "cost": float(self.cost_input.value()),
            "sale_price": float(self.sale_price_input.value()),
            "stock": float(self.stock_input.value()),
            "min_stock": float(self.min_stock_input.value()),
            "auto_price": bool(self.auto_price_check.isChecked()),
        }

        try:
            if self.current_product_id is None:
                product_id = self.service.create_product(**kwargs)
                self.current_product_id = product_id
            else:
                self.service.update_product(
                    self.current_product_id,
                    **kwargs,
                    active=bool(self.active_check.isChecked()),
                )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()

        QMessageBox.information(self, "Guardado", "Producto guardado correctamente")

    def find_category_index(self, category_id: int) -> int:
        for i in range(self.category_combo.count()):
            payload = self.category_combo.itemData(i)
            if isinstance(payload, dict) and int(payload.get("id")) == category_id:
                return i
        return -1
