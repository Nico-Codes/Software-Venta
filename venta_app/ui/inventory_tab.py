from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
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

from ..services import ValidationError, WarehouseService
from .common import format_currency, format_number


MOVEMENT_LABELS = {
    "purchase": "Compra",
    "manual_in": "Entrada manual",
    "manual_out": "Salida manual",
    "adjustment": "Ajuste",
    "sale": "Venta",
}


class InventoryTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed

        root = QVBoxLayout(self)
        root.setSpacing(12)

        entry_frame = QFrame()
        entry_frame.setObjectName("panel")
        entry_layout = QVBoxLayout(entry_frame)

        title = QLabel("Registrar movimiento")
        title.setObjectName("sectionTitle")
        entry_layout.addWidget(title)

        form = QFormLayout()

        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.lineEdit().setPlaceholderText("Selecciona producto")

        self.movement_combo = QComboBox()
        self.movement_combo.addItem("Compra (entrada)", "purchase")
        self.movement_combo.addItem("Entrada manual", "manual_in")
        self.movement_combo.addItem("Salida manual", "manual_out")
        self.movement_combo.addItem("Ajuste por conteo fisico", "adjustment")
        self.movement_combo.currentIndexChanged.connect(self.on_movement_type_change)

        self.quantity_label = QLabel("Cantidad")
        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0, 9_999_999)
        self.quantity_input.setDecimals(2)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 9_999_999)
        self.cost_input.setDecimals(2)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Detalle opcional")

        form.addRow("Producto", self.product_combo)
        form.addRow("Tipo", self.movement_combo)
        form.addRow(self.quantity_label, self.quantity_input)
        form.addRow("Costo unitario", self.cost_input)
        form.addRow("Nota", self.note_input)

        entry_layout.addLayout(form)

        self.save_btn = QPushButton("Registrar movimiento")
        self.save_btn.clicked.connect(self.save_movement)
        entry_layout.addWidget(self.save_btn)

        root.addWidget(entry_frame)

        movements_title = QLabel("Historial de movimientos")
        movements_title.setObjectName("sectionTitle")
        root.addWidget(movements_title)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Fecha", "Producto", "Tipo", "Cantidad", "Antes", "Despues", "Referencia", "Nota"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(self.table, stretch=1)

        self.on_movement_type_change()

    def refresh(self) -> None:
        self.load_products()
        self.load_movements()

    def load_products(self) -> None:
        products = self.service.list_products()
        current_id = self.current_product_id()

        self.product_combo.blockSignals(True)
        self.product_combo.clear()

        for product in products:
            label = f"{product['name']} | Stock: {format_number(float(product['stock']))} | {format_currency(float(product['sale_price']))}"
            self.product_combo.addItem(label, int(product["id"]))

        if current_id is not None:
            idx = self.product_combo.findData(current_id)
            if idx >= 0:
                self.product_combo.setCurrentIndex(idx)

        self.product_combo.blockSignals(False)

    def current_product_id(self) -> int | None:
        data = self.product_combo.currentData()
        if data is None:
            return None
        return int(data)

    def on_movement_type_change(self) -> None:
        movement_type = self.movement_combo.currentData()
        is_purchase = movement_type == "purchase"
        is_adjustment = movement_type == "adjustment"

        self.cost_input.setEnabled(is_purchase)
        self.quantity_label.setText("Stock fisico final" if is_adjustment else "Cantidad")

    def save_movement(self) -> None:
        product_id = self.current_product_id()
        if product_id is None:
            QMessageBox.warning(self, "Sin producto", "Selecciona un producto")
            return

        movement_type = self.movement_combo.currentData()
        quantity = float(self.quantity_input.value())
        note = self.note_input.text().strip()

        try:
            if movement_type == "purchase":
                self.service.add_purchase(product_id, quantity, float(self.cost_input.value()), note)
            elif movement_type == "manual_in":
                self.service.add_stock_manual(product_id, quantity, note)
            elif movement_type == "manual_out":
                self.service.remove_stock_manual(product_id, quantity, note)
            elif movement_type == "adjustment":
                self.service.adjust_stock(product_id, quantity, note)
            else:
                raise ValidationError("Tipo de movimiento invalido")
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return

        self.quantity_input.setValue(0)
        self.note_input.clear()
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Movimiento guardado", "Stock actualizado")

    def load_movements(self) -> None:
        movements = self.service.list_stock_movements()
        self.table.setRowCount(len(movements))

        for row_idx, movement in enumerate(movements):
            movement_type = movement.get("movement_type", "")
            ref_type = movement.get("reference_type") or "-"
            ref_id = movement.get("reference_id")
            reference = f"{ref_type}#{ref_id}" if ref_id else ref_type

            self.table.setItem(row_idx, 0, QTableWidgetItem(str(movement.get("created_at", ""))))
            self.table.setItem(row_idx, 1, QTableWidgetItem(str(movement.get("product_name", ""))))
            self.table.setItem(row_idx, 2, QTableWidgetItem(MOVEMENT_LABELS.get(movement_type, movement_type)))
            self.table.setItem(row_idx, 3, QTableWidgetItem(format_number(float(movement.get("quantity", 0)))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(format_number(float(movement.get("stock_before", 0)))))
            self.table.setItem(row_idx, 5, QTableWidgetItem(format_number(float(movement.get("stock_after", 0)))))
            self.table.setItem(row_idx, 6, QTableWidgetItem(reference))
            self.table.setItem(row_idx, 7, QTableWidgetItem(str(movement.get("note") or "-")))

        self.table.resizeColumnsToContents()
