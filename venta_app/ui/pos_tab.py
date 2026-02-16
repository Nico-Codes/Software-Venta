from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QInputDialog,
)

from ..services import ValidationError, WarehouseService
from .common import format_currency, format_number
from .ticket_dialog import TicketDialog


class POSTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.cart: dict[int, dict[str, Any]] = {}

        root = QVBoxLayout(self)
        root.setSpacing(12)

        scan_row = QHBoxLayout()
        scan_label = QLabel("Escaneo rapido")
        scan_label.setObjectName("sectionTitle")
        self.scan_input = QLineEdit()
        self.scan_input.setPlaceholderText("Escanea codigo de barras y presiona Enter")
        self.scan_input.returnPressed.connect(self.on_scan)
        scan_row.addWidget(scan_label)
        scan_row.addWidget(self.scan_input, stretch=1)

        root.addLayout(scan_row)

        body = QHBoxLayout()
        body.setSpacing(16)

        cart_panel = QVBoxLayout()
        cart_panel.setSpacing(10)

        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["Producto", "Cantidad", "Unitario", "Subtotal"])
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.horizontalHeader().setStretchLastSection(True)
        self.cart_table.itemDoubleClicked.connect(self.on_cart_item_double_clicked)

        cart_panel.addWidget(self.cart_table)

        cart_actions = QHBoxLayout()
        self.plus_btn = QPushButton("+1")
        self.plus_btn.clicked.connect(self.increase_selected)
        self.minus_btn = QPushButton("-1")
        self.minus_btn.clicked.connect(self.decrease_selected)
        self.remove_btn = QPushButton("Quitar")
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("Vaciar carrito")
        self.clear_btn.clicked.connect(self.clear_cart)

        cart_actions.addWidget(self.plus_btn)
        cart_actions.addWidget(self.minus_btn)
        cart_actions.addWidget(self.remove_btn)
        cart_actions.addWidget(self.clear_btn)
        cart_actions.addStretch(1)

        cart_panel.addLayout(cart_actions)

        footer = QFrame()
        footer.setObjectName("totalPanel")
        footer_layout = QHBoxLayout(footer)

        total_title = QLabel("TOTAL")
        total_title.setObjectName("totalTitle")
        self.total_label = QLabel("$ 0,00")
        self.total_label.setObjectName("totalValue")

        self.payment_combo = QComboBox()
        self.payment_combo.addItems(self.service.PAYMENT_METHODS)

        self.charge_btn = QPushButton("Cobrar")
        self.charge_btn.setObjectName("chargeButton")
        self.charge_btn.clicked.connect(self.on_charge)

        footer_layout.addWidget(total_title)
        footer_layout.addWidget(self.total_label)
        footer_layout.addStretch(1)
        footer_layout.addWidget(QLabel("Pago"))
        footer_layout.addWidget(self.payment_combo)
        footer_layout.addWidget(self.charge_btn)

        cart_panel.addWidget(footer)

        manual_panel = QVBoxLayout()
        manual_panel.setSpacing(8)

        manual_title = QLabel("Busqueda manual")
        manual_title.setObjectName("sectionTitle")
        manual_panel.addWidget(manual_title)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto por nombre")
        self.search_input.returnPressed.connect(self.search_manual)
        self.search_btn = QPushButton("Buscar")
        self.search_btn.clicked.connect(self.search_manual)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)
        manual_panel.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.add_from_search)
        manual_panel.addWidget(self.results_list, stretch=1)

        manual_hint = QLabel("Doble clic para agregar al carrito")
        manual_hint.setObjectName("mutedText")
        manual_panel.addWidget(manual_hint)

        body.addLayout(cart_panel, stretch=3)
        body.addLayout(manual_panel, stretch=2)

        root.addLayout(body, stretch=1)

    def focus_scan(self) -> None:
        self.scan_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def refresh(self) -> None:
        self.search_manual(clear_if_empty=True)

    def on_scan(self) -> None:
        code = self.scan_input.text().strip()
        if not code:
            self.focus_scan()
            return

        product = self.service.get_product_by_barcode(code)
        if product:
            self.add_product_to_cart(int(product["id"]), 1)
        else:
            matches = self.service.search_products_by_name(code, limit=2)
            if len(matches) == 1:
                self.add_product_to_cart(int(matches[0]["id"]), 1)
            else:
                QMessageBox.warning(self, "No encontrado", "Producto no encontrado por codigo o nombre")

        self.scan_input.clear()
        self.focus_scan()

    def search_manual(self, clear_if_empty: bool = False) -> None:
        term = self.search_input.text().strip()
        self.results_list.clear()

        if clear_if_empty and not term:
            return

        if not term:
            products = self.service.list_products()
            products = products[:30]
        else:
            products = self.service.search_products_by_name(term)

        for product in products:
            item = QListWidgetItem(
                f"{product['name']} | Stock: {format_number(float(product['stock']))} | {format_currency(float(product['sale_price']))}"
            )
            item.setData(Qt.ItemDataRole.UserRole, int(product["id"]))
            self.results_list.addItem(item)

    def add_from_search(self, item: QListWidgetItem) -> None:
        product_id = item.data(Qt.ItemDataRole.UserRole)
        self.add_product_to_cart(int(product_id), 1)
        self.focus_scan()

    def add_product_to_cart(self, product_id: int, quantity: float) -> None:
        product = self.service.get_product(product_id)
        stock = float(product["stock"])

        existing_qty = float(self.cart.get(product_id, {}).get("quantity", 0))
        desired_qty = existing_qty + quantity

        if desired_qty > stock:
            QMessageBox.warning(
                self,
                "Stock insuficiente",
                f"No hay stock suficiente para {product['name']} (disponible: {format_number(stock)})",
            )
            return

        self.cart[product_id] = {
            "product_id": product_id,
            "name": product["name"],
            "quantity": desired_qty,
            "unit_price": float(product["sale_price"]),
        }

        self.render_cart()

    def render_cart(self) -> None:
        items = list(self.cart.values())
        self.cart_table.setRowCount(len(items))
        total = 0.0

        for row_idx, item in enumerate(items):
            subtotal = item["quantity"] * item["unit_price"]
            total += subtotal

            product_item = QTableWidgetItem(item["name"])
            product_item.setData(Qt.ItemDataRole.UserRole, item["product_id"])

            self.cart_table.setItem(row_idx, 0, product_item)
            self.cart_table.setItem(row_idx, 1, QTableWidgetItem(format_number(float(item["quantity"]))))
            self.cart_table.setItem(row_idx, 2, QTableWidgetItem(format_currency(float(item["unit_price"]))))
            self.cart_table.setItem(row_idx, 3, QTableWidgetItem(format_currency(float(subtotal))))

        self.total_label.setText(format_currency(total))

    def selected_product_id(self) -> int | None:
        selected = self.cart_table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.cart_table.item(row, 0)
        if not item:
            return None
        return int(item.data(Qt.ItemDataRole.UserRole))

    def increase_selected(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            return
        self.add_product_to_cart(product_id, 1)
        self.focus_scan()

    def decrease_selected(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None or product_id not in self.cart:
            return

        self.cart[product_id]["quantity"] -= 1
        if self.cart[product_id]["quantity"] <= 0:
            del self.cart[product_id]
        self.render_cart()
        self.focus_scan()

    def remove_selected(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            return
        self.cart.pop(product_id, None)
        self.render_cart()
        self.focus_scan()

    def clear_cart(self) -> None:
        self.cart.clear()
        self.render_cart()
        self.focus_scan()

    def on_cart_item_double_clicked(self, item: QTableWidgetItem) -> None:
        row = item.row()
        product_item = self.cart_table.item(row, 0)
        if not product_item:
            return

        product_id = int(product_item.data(Qt.ItemDataRole.UserRole))
        product = self.service.get_product(product_id)

        current_qty = float(self.cart[product_id]["quantity"])
        new_qty, ok = QInputDialog.getDouble(
            self,
            "Editar cantidad",
            f"Cantidad para {product['name']}",
            value=current_qty,
            minValue=0,
            maxValue=float(product["stock"]),
            decimals=2,
        )

        if not ok:
            return

        if new_qty <= 0:
            self.cart.pop(product_id, None)
        else:
            self.cart[product_id]["quantity"] = new_qty

        self.render_cart()
        self.focus_scan()

    def on_charge(self) -> None:
        if not self.cart:
            QMessageBox.warning(self, "Carrito vacio", "Agrega al menos un producto")
            return

        items = [
            {"product_id": item["product_id"], "quantity": item["quantity"]}
            for item in self.cart.values()
        ]

        try:
            result = self.service.create_sale(items, self.payment_combo.currentText())
            ticket = self.service.create_sale_ticket(int(result["sale_id"]))
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo cobrar", str(exc))
            self.focus_scan()
            return
        except OSError as exc:
            QMessageBox.warning(self, "Venta guardada sin ticket", str(exc))
            self.clear_cart()
            if self.on_data_changed:
                self.on_data_changed()
            self.focus_scan()
            return

        QMessageBox.information(
            self,
            "Venta registrada",
            f"Venta #{result['sale_id']} guardada\nTotal: {format_currency(float(result['total']))}",
        )

        self.clear_cart()
        if self.on_data_changed:
            self.on_data_changed()

        dialog = TicketDialog(
            service=self.service,
            sale_id=int(result["sale_id"]),
            ticket_text=str(ticket["text"]),
            ticket_path=str(ticket["path"]),
            parent=self,
        )
        dialog.exec()
        self.focus_scan()
