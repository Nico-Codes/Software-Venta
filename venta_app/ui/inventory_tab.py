from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
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


class QuickCreateProductDialog(QDialog):
    def __init__(self, service: WarehouseService, barcode: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.created_product_id: int | None = None

        self.setWindowTitle("Crear producto")
        self.setModal(True)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setSpacing(10)

        title = QLabel("Producto no encontrado")
        title.setObjectName("sectionTitle")
        subtitle = QLabel("Completa los datos para crearlo y continuar")
        subtitle.setObjectName("mutedText")
        root.addWidget(title)
        root.addWidget(subtitle)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nombre")

        self.barcode_input = QLineEdit()
        self.barcode_input.setPlaceholderText("Codigo de barras")
        self.barcode_input.setText(barcode.strip())

        self.price_input = QDoubleSpinBox()
        self.price_input.setRange(0, 9_999_999)
        self.price_input.setDecimals(2)
        self.price_input.setValue(0)

        self.stock_input = QDoubleSpinBox()
        self.stock_input.setRange(0, 9_999_999)
        self.stock_input.setDecimals(2)
        self.stock_input.setValue(1)

        self.category_combo = QComboBox()
        for category in self.service.list_categories():
            self.category_combo.addItem(str(category["name"]), int(category["id"]))

        form.addRow("Nombre", self.name_input)
        form.addRow("Codigo", self.barcode_input)
        form.addRow("Precio", self.price_input)
        form.addRow("Stock", self.stock_input)
        form.addRow("Categoria", self.category_combo)
        root.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setObjectName("dangerText")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        actions = QHBoxLayout()
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        save_btn = QPushButton("Crear producto")
        save_btn.clicked.connect(self.on_save)
        actions.addStretch(1)
        actions.addWidget(cancel_btn)
        actions.addWidget(save_btn)
        root.addLayout(actions)

        self.name_input.setFocus()

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def on_save(self) -> None:
        self.error_label.setVisible(False)
        name = self.name_input.text().strip()
        barcode = self.barcode_input.text().strip()
        price = float(self.price_input.value())
        stock = float(self.stock_input.value())
        category_id = self.category_combo.currentData()

        if not name:
            self.show_error("El nombre es obligatorio")
            return
        if not barcode:
            self.show_error("El codigo de barras es obligatorio")
            return
        if price <= 0:
            self.show_error("El precio debe ser mayor a cero")
            return
        if stock <= 0:
            self.show_error("El stock debe ser mayor a cero")
            return
        if category_id is None:
            self.show_error("Debes seleccionar una categoria")
            return

        try:
            self.created_product_id = self.service.create_product(
                name=name,
                barcode=barcode,
                category_id=int(category_id),
                cost=price,
                sale_price=price,
                stock=stock,
                min_stock=1,
                auto_price=False,
            )
        except ValidationError as exc:
            self.show_error(str(exc))
            return

        self.accept()


class InventoryTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(2, 2, 2, 2)

        quick_frame = QFrame()
        quick_frame.setObjectName("panel")
        quick_layout = QVBoxLayout(quick_frame)
        quick_layout.setContentsMargins(12, 12, 12, 12)
        quick_layout.setSpacing(8)

        title = QLabel("Agregar stock rapido")
        title.setObjectName("sectionTitle")
        quick_layout.addWidget(title)

        scan_row = QHBoxLayout()
        self.scan_input = QLineEdit()
        self.scan_input.setObjectName("stockScanInput")
        self.scan_input.setMinimumHeight(42)
        self.scan_input.setPlaceholderText("Escanea codigo de barras y Enter")
        self.scan_input.returnPressed.connect(self.on_scan_product)
        self.scan_auto_add_check = QCheckBox("Auto +1 por escaneo")
        self.scan_auto_add_check.setChecked(True)
        self.quick_hint = QLabel("Escanear -> Enter -> sumar stock")
        self.quick_hint.setObjectName("mutedText")
        scan_row.addWidget(QLabel("Scanner"))
        scan_row.addWidget(self.scan_input, stretch=1)
        scan_row.addWidget(self.scan_auto_add_check)
        scan_row.addWidget(self.quick_hint, stretch=1)
        quick_layout.addLayout(scan_row)

        quick_row = QHBoxLayout()
        self.product_combo = QComboBox()
        self.product_combo.setEditable(True)
        self.product_combo.lineEdit().setPlaceholderText("Selecciona producto")

        self.quantity_caption = QLabel("Cantidad")
        self.qty_minus_btn = QPushButton("-")
        self.qty_minus_btn.setObjectName("stepMinusButton")
        self.qty_minus_btn.clicked.connect(self.decrease_quantity)

        self.quantity_input = QDoubleSpinBox()
        self.quantity_input.setRange(0, 9_999_999)
        self.quantity_input.setDecimals(2)
        self.quantity_input.setValue(1)

        self.qty_plus_btn = QPushButton("+")
        self.qty_plus_btn.setObjectName("stepPlusButton")
        self.qty_plus_btn.clicked.connect(self.increase_quantity)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("Nota opcional")

        self.quick_add_btn = QPushButton("Agregar stock")
        self.quick_add_btn.clicked.connect(self.add_stock_fast)

        quick_row.addWidget(QLabel("Producto"))
        quick_row.addWidget(self.product_combo, stretch=2)
        quick_row.addWidget(self.quantity_caption)
        quick_row.addWidget(self.qty_minus_btn)
        quick_row.addWidget(self.quantity_input)
        quick_row.addWidget(self.qty_plus_btn)
        quick_row.addWidget(self.note_input, stretch=1)
        quick_row.addWidget(self.quick_add_btn)
        quick_layout.addLayout(quick_row)

        self.quick_status_label = QLabel("Listo para escanear")
        self.quick_status_label.setObjectName("mutedText")
        quick_layout.addWidget(self.quick_status_label)

        self.advanced_check = QCheckBox("Modo avanzado (compra, salida y ajuste)")
        self.advanced_check.toggled.connect(self.on_advanced_toggled)
        quick_layout.addWidget(self.advanced_check)

        self.advanced_panel = QWidget()
        advanced_row = QHBoxLayout(self.advanced_panel)
        advanced_row.setContentsMargins(0, 0, 0, 0)

        self.movement_combo = QComboBox()
        self.movement_combo.addItem("Entrada manual", "manual_in")
        self.movement_combo.addItem("Compra (entrada)", "purchase")
        self.movement_combo.addItem("Salida manual", "manual_out")
        self.movement_combo.addItem("Ajuste por conteo fisico", "adjustment")
        self.movement_combo.currentIndexChanged.connect(self.on_movement_type_change)

        self.cost_input = QDoubleSpinBox()
        self.cost_input.setRange(0, 9_999_999)
        self.cost_input.setDecimals(2)

        self.advanced_save_btn = QPushButton("Registrar movimiento")
        self.advanced_save_btn.clicked.connect(self.save_advanced_movement)

        advanced_row.addWidget(QLabel("Tipo"))
        advanced_row.addWidget(self.movement_combo)
        advanced_row.addWidget(QLabel("Costo unitario"))
        advanced_row.addWidget(self.cost_input)
        advanced_row.addWidget(self.advanced_save_btn)

        quick_layout.addWidget(self.advanced_panel)

        root.addWidget(quick_frame)

        history_frame = QFrame()
        history_frame.setObjectName("panel")
        history_layout = QVBoxLayout(history_frame)
        history_layout.setContentsMargins(12, 12, 12, 12)
        history_layout.setSpacing(8)

        movements_title = QLabel("Historial de movimientos")
        movements_title.setObjectName("sectionTitle")
        history_layout.addWidget(movements_title)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["Fecha", "Producto", "Tipo", "Cantidad", "Antes", "Despues", "Referencia", "Nota"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)

        history_layout.addWidget(self.table, stretch=1)
        root.addWidget(history_frame, stretch=1)

        self.on_advanced_toggled(False)

    def refresh(self) -> None:
        self.load_products()
        self.load_movements()
        self.scan_input.setFocus()

    def load_products(self) -> None:
        products = self.service.list_products()
        current_id = self.current_product_id()

        self.product_combo.blockSignals(True)
        self.product_combo.clear()

        for product in products:
            label = (
                f"{product['name']} | Stock: {format_number(float(product['stock']))} | "
                f"{format_currency(float(product['sale_price']))}"
            )
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

    def increase_quantity(self) -> None:
        self.quantity_input.setValue(self.quantity_input.value() + 1)

    def decrease_quantity(self) -> None:
        self.quantity_input.setValue(max(0, self.quantity_input.value() - 1))

    def set_status(self, message: str, *, ok: bool = True) -> None:
        self.quick_status_label.setText(message)
        self.quick_status_label.setObjectName("successText" if ok else "dangerText")
        self.quick_status_label.style().unpolish(self.quick_status_label)
        self.quick_status_label.style().polish(self.quick_status_label)

    def on_scan_product(self) -> None:
        code = self.scan_input.text().strip()
        if not code:
            self.scan_input.setFocus()
            return

        product = self.service.get_product_by_barcode(code)
        if not product:
            self.set_status("Codigo no encontrado", ok=False)
            create_now = QMessageBox.question(
                self,
                "Producto no encontrado",
                "No existe producto con ese codigo.\n¿Deseas crearlo ahora?",
            )
            if create_now == QMessageBox.StandardButton.Yes:
                created = self.create_product_from_scan(code)
                if created:
                    return
            self.scan_input.selectAll()
            self.scan_input.setFocus()
            return

        idx = self.product_combo.findData(int(product["id"]))
        if idx >= 0:
            self.product_combo.setCurrentIndex(idx)

        if self.scan_auto_add_check.isChecked():
            try:
                self.service.add_stock_manual(int(product["id"]), 1, self.note_input.text().strip() or "Ingreso por escaneo")
            except ValidationError as exc:
                self.set_status(str(exc), ok=False)
                QMessageBox.warning(self, "No se pudo registrar", str(exc))
                self.scan_input.selectAll()
                self.scan_input.setFocus()
                return

            self.set_status(f"Sumado +1 a {product['name']}", ok=True)
            self.refresh()
            if self.on_data_changed:
                self.on_data_changed()
            self.scan_input.clear()
            self.scan_input.setFocus()
            return

        self.quantity_input.setFocus()
        self.scan_input.clear()

    def create_product_from_scan(self, barcode: str) -> bool:
        if not self.service.list_categories():
            QMessageBox.warning(self, "Sin categorias", "Primero crea una categoria en Utilidades > Categorias")
            self.scan_input.selectAll()
            self.scan_input.setFocus()
            return False

        dialog = QuickCreateProductDialog(self.service, barcode, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.created_product_id is None:
            self.scan_input.selectAll()
            self.scan_input.setFocus()
            return False

        self.refresh()
        idx = self.product_combo.findData(int(dialog.created_product_id))
        if idx >= 0:
            self.product_combo.setCurrentIndex(idx)

        created_product = self.service.get_product(int(dialog.created_product_id))
        self.set_status(f"Producto creado: {created_product['name']}", ok=True)
        if self.on_data_changed:
            self.on_data_changed()
        self.scan_input.clear()
        self.scan_input.setFocus()
        return True

    def on_advanced_toggled(self, enabled: bool) -> None:
        self.advanced_panel.setVisible(enabled)
        if not enabled:
            self.quick_add_btn.setText("Agregar stock")
            idx = self.movement_combo.findData("manual_in")
            if idx >= 0:
                self.movement_combo.setCurrentIndex(idx)
            self.quantity_caption.setText("Cantidad")
        else:
            self.quick_add_btn.setText("Agregar rapido")
        self.on_movement_type_change()

    def on_movement_type_change(self) -> None:
        movement_type = self.movement_combo.currentData()
        is_purchase = movement_type == "purchase"
        is_adjustment = movement_type == "adjustment"

        self.cost_input.setEnabled(is_purchase)
        self.quantity_caption.setText("Stock final" if (self.advanced_check.isChecked() and is_adjustment) else "Cantidad")

    def add_stock_fast(self) -> None:
        product_id = self.current_product_id()
        if product_id is None:
            QMessageBox.warning(self, "Sin producto", "Selecciona un producto")
            return

        quantity = float(self.quantity_input.value())
        if quantity <= 0:
            QMessageBox.warning(self, "Cantidad invalida", "Ingresa una cantidad mayor a cero")
            return

        try:
            self.service.add_stock_manual(product_id, quantity, self.note_input.text().strip())
        except ValidationError as exc:
            self.set_status(str(exc), ok=False)
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return

        product = self.service.get_product(product_id)
        self.set_status(f"Stock sumado: +{format_number(quantity)} en {product['name']}", ok=True)

        self.quantity_input.setValue(1)
        self.note_input.clear()
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        self.scan_input.setFocus()

    def save_advanced_movement(self) -> None:
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
            self.set_status(str(exc), ok=False)
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return

        self.set_status("Movimiento avanzado registrado", ok=True)

        self.quantity_input.setValue(1)
        self.note_input.clear()
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        self.scan_input.setFocus()

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
