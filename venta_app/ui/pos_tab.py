from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGraphicsOpacityEffect,
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
from .customer_account_dialog import CustomerAccountDialog
from .ticket_dialog import TicketDialog


class POSTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.cart: dict[int, dict[str, Any]] = {}
        self.customers_cache: list[dict[str, Any]] = []
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(140)
        self.search_timer.timeout.connect(self.search_manual)

        self.scan_focus_timer = QTimer(self)
        self.scan_focus_timer.setInterval(350)
        self.scan_focus_timer.timeout.connect(self.ensure_scan_focus)

        root = QVBoxLayout(self)
        root.setSpacing(10)
        root.setContentsMargins(2, 2, 2, 2)

        top_panel = QFrame()
        top_panel.setObjectName("panel")
        top_layout = QVBoxLayout(top_panel)
        top_layout.setContentsMargins(12, 10, 12, 10)
        top_layout.setSpacing(8)

        scan_row = QHBoxLayout()
        scan_row.setSpacing(8)
        scan_label = QLabel("Escaneo rapido")
        scan_label.setObjectName("sectionTitle")
        self.scan_input = QLineEdit()
        self.scan_input.setObjectName("scanInput")
        self.scan_input.setMinimumHeight(42)
        self.scan_input.setPlaceholderText("Escanea codigo de barras y Enter")
        self.scan_input.returnPressed.connect(self.on_scan)
        self.scan_only_check = QCheckBox("Modo solo scanner")
        self.scan_only_check.toggled.connect(self.on_scan_only_toggled)
        self.shortcuts_hint = QLabel("Atajos: F2 escanear | F3 buscar | F4 agregar | F5 cobrar | F6 vaciar | F7 pago | F8 parcial")
        self.shortcuts_hint.setObjectName("mutedText")
        scan_row.addWidget(scan_label)
        scan_row.addWidget(self.scan_input, stretch=1)
        scan_row.addWidget(self.scan_only_check)
        scan_row.addWidget(self.shortcuts_hint, stretch=1)
        top_layout.addLayout(scan_row)

        customer_row = QHBoxLayout()
        customer_row.setSpacing(8)
        customer_title = QLabel("Cliente")
        customer_title.setObjectName("sectionTitle")

        self.customer_combo = QComboBox()
        self.customer_combo.setObjectName("customerCombo")
        self.customer_combo.setEditable(True)
        self.customer_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.customer_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.customer_combo.setMinimumWidth(360)
        self.customer_combo.setMinimumHeight(36)
        self.customer_combo.lineEdit().setPlaceholderText("Consumidor final o buscar cliente")
        self.customer_combo.currentIndexChanged.connect(self.on_customer_changed)

        self.customer_refresh_btn = QPushButton("Actualizar")
        self.customer_refresh_btn.clicked.connect(self.reload_customers)

        self.customer_new_btn = QPushButton("Nuevo cliente")
        self.customer_new_btn.clicked.connect(self.create_customer_quick)
        self.customer_detail_btn = QPushButton("Detalle deuda")
        self.customer_detail_btn.clicked.connect(self.open_customer_detail)

        self.customer_debt_label = QLabel("Sin cliente | Deuda: $ 0,00")
        self.customer_debt_label.setObjectName("mutedText")

        customer_row.addWidget(customer_title)
        customer_row.addWidget(self.customer_combo, stretch=1)
        customer_row.addWidget(self.customer_refresh_btn)
        customer_row.addWidget(self.customer_new_btn)
        customer_row.addWidget(self.customer_detail_btn)
        customer_row.addWidget(self.customer_debt_label, stretch=1)
        top_layout.addLayout(customer_row)

        self.feedback_label = QLabel("Listo para escanear")
        self.feedback_label.setObjectName("mutedText")
        self.feedback_label.setWordWrap(True)
        top_layout.addWidget(self.feedback_label)
        root.addWidget(top_panel)

        body = QHBoxLayout()
        body.setSpacing(12)

        cart_frame = QFrame()
        cart_frame.setObjectName("panel")
        cart_panel = QVBoxLayout(cart_frame)
        cart_panel.setContentsMargins(12, 12, 12, 12)
        cart_panel.setSpacing(10)

        cart_header = QHBoxLayout()
        cart_header.setSpacing(8)

        cart_title = QLabel("Venta rapida")
        cart_title.setObjectName("sectionTitle")
        self.cart_meta_label = QLabel("0 productos en carrito")
        self.cart_meta_label.setObjectName("mutedText")
        cart_header.addWidget(cart_title)
        cart_header.addStretch(1)
        cart_header.addWidget(self.cart_meta_label)
        cart_panel.addLayout(cart_header)

        self.cart_table = QTableWidget(0, 4)
        self.cart_table.setHorizontalHeaderLabels(["Producto", "Cantidad", "Unitario", "Subtotal"])
        self.cart_table.verticalHeader().setVisible(False)
        self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.cart_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cart_table.setAlternatingRowColors(True)
        self.cart_table.horizontalHeader().setStretchLastSection(True)
        self.cart_table.itemDoubleClicked.connect(self.on_cart_item_double_clicked)

        cart_panel.addWidget(self.cart_table)

        self.cart_empty_label = QLabel("Carrito vacio. Escanea un codigo o busca por nombre.")
        self.cart_empty_label.setObjectName("mutedText")
        self.cart_empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cart_panel.addWidget(self.cart_empty_label)

        cart_actions = QHBoxLayout()
        self.plus_btn = QPushButton("+")
        self.plus_btn.setObjectName("stepPlusButton")
        self.plus_btn.setToolTip("Sumar 1 unidad")
        self.plus_btn.clicked.connect(self.increase_selected)
        self.minus_btn = QPushButton("-")
        self.minus_btn.setObjectName("stepMinusButton")
        self.minus_btn.setToolTip("Restar 1 unidad")
        self.minus_btn.clicked.connect(self.decrease_selected)
        self.remove_btn = QPushButton("Quitar")
        self.remove_btn.setMinimumHeight(34)
        self.remove_btn.clicked.connect(self.remove_selected)
        self.clear_btn = QPushButton("Vaciar carrito")
        self.clear_btn.setMinimumHeight(34)
        self.clear_btn.clicked.connect(self.clear_cart)
        cart_actions.addWidget(self.plus_btn)
        cart_actions.addWidget(self.minus_btn)
        cart_actions.addWidget(self.remove_btn)
        cart_actions.addWidget(self.clear_btn)
        cart_actions.addStretch(1)
        cart_panel.addLayout(cart_actions)

        footer = QFrame()
        footer.setObjectName("totalPanel")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(10, 8, 10, 8)
        footer_layout.setSpacing(8)

        footer_top_row = QHBoxLayout()
        footer_top_row.setSpacing(10)
        footer_bottom_row = QHBoxLayout()
        footer_bottom_row.setSpacing(8)

        total_title = QLabel("TOTAL")
        total_title.setObjectName("totalTitle")
        self.total_label = QLabel("$ 0,00")
        self.total_label.setObjectName("totalValue")

        self.payment_combo = QComboBox()
        self.payment_combo.setObjectName("paymentCombo")
        self.payment_combo.addItems(self.service.PAYMENT_METHODS)
        self.payment_combo.view().setFrameShape(QFrame.Shape.NoFrame)
        self.payment_combo.setMinimumHeight(36)
        self.payment_combo.currentIndexChanged.connect(self.on_payment_method_changed)

        self.partial_toggle_btn = QPushButton("Pago parcial")
        self.partial_toggle_btn.setObjectName("partialToggleButton")
        self.partial_toggle_btn.setMinimumHeight(36)
        self.partial_toggle_btn.setCheckable(True)
        self.partial_toggle_btn.toggled.connect(self.on_partial_toggle)

        self.paid_amount_input = QDoubleSpinBox()
        self.paid_amount_input.setRange(0, 9_999_999)
        self.paid_amount_input.setDecimals(2)
        self.paid_amount_input.setPrefix("Abona ahora ")
        self.paid_amount_input.setMinimumWidth(170)
        self.paid_amount_input.valueChanged.connect(self.on_partial_amount_changed)

        self.debt_preview_label = QLabel("A deuda: $ 0,00")
        self.debt_preview_label.setObjectName("mutedText")

        self.partial_panel = QWidget()
        self.partial_panel_layout = QHBoxLayout(self.partial_panel)
        self.partial_panel_layout.setContentsMargins(0, 0, 0, 0)
        self.partial_panel_layout.setSpacing(8)
        self.partial_panel_layout.addWidget(QLabel("Monto pagado"))
        self.partial_panel_layout.addWidget(self.paid_amount_input)
        self.partial_panel_layout.addWidget(self.debt_preview_label)
        self.partial_panel_layout.addStretch(1)
        self.partial_panel.setVisible(False)

        self.charge_btn = QPushButton("Cobrar")
        self.charge_btn.setObjectName("chargeButton")
        self.charge_btn.setMinimumWidth(164)
        self.charge_btn.clicked.connect(self.on_charge)

        total_block = QVBoxLayout()
        total_block.setSpacing(2)
        total_block.addWidget(total_title)
        total_block.addWidget(self.total_label)

        checkout_block = QVBoxLayout()
        checkout_block.setSpacing(7)
        payment_row = QHBoxLayout()
        payment_row.setSpacing(8)
        payment_label = QLabel("Metodo de pago")
        payment_label.setObjectName("totalTitle")
        payment_row.addWidget(payment_label)
        payment_row.addWidget(self.payment_combo)
        payment_row.addWidget(self.partial_toggle_btn)
        payment_row.addStretch(1)
        checkout_block.addLayout(payment_row)
        checkout_block.addWidget(self.charge_btn, alignment=Qt.AlignmentFlag.AlignRight)

        footer_top_row.addLayout(total_block, stretch=1)
        footer_top_row.addLayout(checkout_block, stretch=2)
        footer_bottom_row.addWidget(self.partial_panel, stretch=1)

        footer_layout.addLayout(footer_top_row)
        footer_layout.addLayout(footer_bottom_row)

        cart_panel.addWidget(footer)

        self.total_opacity = QGraphicsOpacityEffect(self.total_label)
        self.total_label.setGraphicsEffect(self.total_opacity)
        self.total_opacity.setOpacity(1.0)
        self.total_animation = QPropertyAnimation(self.total_opacity, b"opacity")
        self.total_animation.setDuration(220)
        self.total_animation.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.total_animation.setStartValue(0.35)
        self.total_animation.setEndValue(1.0)

        manual_frame = QFrame()
        manual_frame.setObjectName("panel")
        manual_panel = QVBoxLayout(manual_frame)
        manual_panel.setContentsMargins(12, 12, 12, 12)
        manual_panel.setSpacing(8)
        self.manual_panel_container = manual_frame

        manual_title = QLabel("Busqueda manual")
        manual_title.setObjectName("sectionTitle")
        manual_panel.addWidget(manual_title)

        search_row = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar producto por nombre")
        self.search_input.returnPressed.connect(self.on_search_enter)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        self.search_btn = QPushButton("Buscar")
        self.search_btn.setMinimumHeight(34)
        self.search_btn.clicked.connect(self.search_manual)
        search_row.addWidget(self.search_input)
        search_row.addWidget(self.search_btn)
        manual_panel.addLayout(search_row)

        self.results_list = QListWidget()
        self.results_list.setAlternatingRowColors(True)
        self.results_list.itemDoubleClicked.connect(self.add_from_search)
        manual_panel.addWidget(self.results_list, stretch=1)

        self.search_state_label = QLabel("Ingresa un nombre o escanea para buscar")
        self.search_state_label.setObjectName("mutedText")
        manual_panel.addWidget(self.search_state_label)

        manual_hint = QLabel("Doble clic para agregar al carrito")
        manual_hint.setObjectName("mutedText")
        manual_panel.addWidget(manual_hint)

        body.addWidget(cart_frame, stretch=3)
        body.addWidget(self.manual_panel_container, stretch=2)
        root.addLayout(body, stretch=1)

        self.register_shortcuts()
        self.on_payment_method_changed()

    def focus_scan(self) -> None:
        self.scan_input.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_feedback(self, message: str, ok: bool | None = None) -> None:
        self.feedback_label.setText(message)
        if ok is None:
            self.feedback_label.setObjectName("mutedText")
        elif ok:
            self.feedback_label.setObjectName("successText")
        else:
            self.feedback_label.setObjectName("dangerText")
        self.feedback_label.style().unpolish(self.feedback_label)
        self.feedback_label.style().polish(self.feedback_label)

    def register_shortcuts(self) -> None:
        QShortcut(QKeySequence("F2"), self, activated=self.focus_scan)
        QShortcut(QKeySequence("F3"), self, activated=self.focus_search)
        QShortcut(QKeySequence("F4"), self, activated=self.add_first_search_result)
        QShortcut(QKeySequence("F5"), self, activated=self.on_charge)
        QShortcut(QKeySequence("F6"), self, activated=self.clear_cart)
        QShortcut(QKeySequence("F7"), self, activated=self.toggle_payment_method)
        QShortcut(QKeySequence("F8"), self, activated=lambda: self.partial_toggle_btn.toggle())
        QShortcut(QKeySequence("Delete"), self, activated=self.remove_selected)
        QShortcut(QKeySequence("+"), self, activated=self.increase_selected)
        QShortcut(QKeySequence("-"), self, activated=self.decrease_selected)

    def focus_search(self) -> None:
        if self.scan_only_check.isChecked():
            return
        self.search_input.setFocus(Qt.FocusReason.OtherFocusReason)
        self.search_input.selectAll()

    def add_first_search_result(self) -> None:
        if self.results_list.count() <= 0:
            return
        item = self.results_list.item(0)
        if item:
            self.add_from_search(item)

    def toggle_payment_method(self) -> None:
        idx = self.payment_combo.currentIndex()
        self.payment_combo.setCurrentIndex((idx + 1) % self.payment_combo.count())

    def on_search_text_changed(self) -> None:
        if self.scan_only_check.isChecked():
            return
        self.search_timer.start()

    def on_search_enter(self) -> None:
        if self.results_list.count() > 0:
            item = self.results_list.item(0)
            if item:
                self.add_from_search(item)
                return
        self.search_manual()

    def on_scan_only_toggled(self, enabled: bool) -> None:
        self.manual_panel_container.setVisible(not enabled)
        if enabled:
            self.scan_focus_timer.start()
            self.focus_scan()
            self.set_feedback("Modo solo scanner activo", ok=True)
        else:
            self.scan_focus_timer.stop()
            self.set_feedback("Modo manual habilitado", ok=None)

    def ensure_scan_focus(self) -> None:
        if not self.scan_only_check.isChecked():
            return
        if not self.isVisible():
            return
        if QApplication.activeModalWidget() is not None:
            return
        if not self.scan_input.hasFocus():
            self.focus_scan()

    def refresh(self) -> None:
        self.search_manual(clear_if_empty=True)
        self.reload_customers()
        self.on_payment_method_changed()
        self.render_cart()
        self.set_feedback("Listo para escanear", ok=None)
        if self.scan_only_check.isChecked():
            self.focus_scan()

    def reload_customers(self) -> None:
        current_id = self.selected_customer_id()
        self.customers_cache = self.service.list_customers()

        self.customer_combo.blockSignals(True)
        self.customer_combo.clear()
        self.customer_combo.addItem("Consumidor final", None)
        for customer in self.customers_cache:
            label = f"{customer['name']} | deuda {format_currency(float(customer['debt_total']))}"
            self.customer_combo.addItem(label, int(customer["id"]))
        self.customer_combo.blockSignals(False)

        if current_id is not None:
            idx = self.customer_combo.findData(current_id)
            if idx >= 0:
                self.customer_combo.setCurrentIndex(idx)
            else:
                self.customer_combo.setCurrentIndex(0)
        else:
            self.customer_combo.setCurrentIndex(0)

        self.on_customer_changed()

    def selected_customer_id(self) -> int | None:
        data = self.customer_combo.currentData()
        if data is None:
            return None
        return int(data)

    def on_customer_changed(self) -> None:
        customer_id = self.selected_customer_id()
        if customer_id is None:
            self.customer_debt_label.setText("Sin cliente | Deuda: $ 0,00")
            self.customer_debt_label.setObjectName("mutedText")
            self.customer_debt_label.style().unpolish(self.customer_debt_label)
            self.customer_debt_label.style().polish(self.customer_debt_label)
            return

        customer = self.service.get_customer(customer_id)
        debt = float(customer["debt_total"])
        limit = float(customer["alert_limit"])
        global_limit = float(self.service.get_debt_global_alert_limit())
        over_limit = debt >= limit or debt >= global_limit

        text = (
            f"{customer['name']} | Deuda: {format_currency(debt)} | "
            f"Limite: {format_currency(limit)} | Global: {format_currency(global_limit)} | "
            f"{'ALERTA' if over_limit else 'OK'}"
        )
        self.customer_debt_label.setText(text)
        self.customer_debt_label.setObjectName("dangerText" if over_limit else "mutedText")
        self.customer_debt_label.style().unpolish(self.customer_debt_label)
        self.customer_debt_label.style().polish(self.customer_debt_label)

    def create_customer_quick(self) -> None:
        name, ok = QInputDialog.getText(self, "Nuevo cliente", "Nombre")
        if not ok:
            return
        if not name.strip():
            QMessageBox.warning(self, "Dato invalido", "Ingresa un nombre")
            return

        phone, _ = QInputDialog.getText(self, "Telefono", "Telefono (opcional)")
        try:
            customer = self.service.get_or_create_customer(name, phone=phone)
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo crear", str(exc))
            return

        self.reload_customers()
        idx = self.customer_combo.findData(int(customer["id"]))
        if idx >= 0:
            self.customer_combo.setCurrentIndex(idx)
        self.focus_scan()

    def open_customer_detail(self) -> None:
        customer_id = self.selected_customer_id()
        if customer_id is None:
            self.set_feedback("Selecciona un cliente para ver detalle de deuda", ok=False)
            return
        dialog = CustomerAccountDialog(self.service, customer_id, parent=self)
        dialog.exec()
        self.reload_customers()
        self.focus_scan()

    def on_payment_method_changed(self) -> None:
        if not self.partial_toggle_btn.isChecked():
            self.paid_amount_input.blockSignals(True)
            self.paid_amount_input.setValue(self.current_total())
            self.paid_amount_input.blockSignals(False)
        self.update_partial_debt_label()

    def on_partial_toggle(self, enabled: bool) -> None:
        self.partial_panel.setVisible(enabled)
        if enabled:
            self.paid_amount_input.blockSignals(True)
            self.paid_amount_input.setValue(self.current_total())
            self.paid_amount_input.blockSignals(False)
            self.paid_amount_input.setFocus(Qt.FocusReason.OtherFocusReason)
            self.paid_amount_input.selectAll()
        else:
            self.paid_amount_input.blockSignals(True)
            self.paid_amount_input.setValue(self.current_total())
            self.paid_amount_input.blockSignals(False)
            self.focus_scan()
        self.update_partial_debt_label()

    def on_partial_amount_changed(self) -> None:
        self.update_partial_debt_label()

    def update_partial_debt_label(self) -> None:
        if not self.partial_toggle_btn.isChecked():
            self.debt_preview_label.setText("A deuda: $ 0,00")
            self.debt_preview_label.setObjectName("mutedText")
            self.debt_preview_label.style().unpolish(self.debt_preview_label)
            self.debt_preview_label.style().polish(self.debt_preview_label)
            return

        total = self.current_total()
        paid = float(self.paid_amount_input.value())
        if paid > total:
            self.paid_amount_input.blockSignals(True)
            self.paid_amount_input.setValue(total)
            self.paid_amount_input.blockSignals(False)
            paid = total

        debt = max(total - paid, 0.0)
        self.debt_preview_label.setText(f"A deuda: {format_currency(debt)}")
        self.debt_preview_label.setObjectName("dangerText" if debt > 0 else "successText")
        self.debt_preview_label.style().unpolish(self.debt_preview_label)
        self.debt_preview_label.style().polish(self.debt_preview_label)

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
                self.set_feedback("Producto no encontrado por codigo o nombre", ok=False)

        self.scan_input.clear()
        self.focus_scan()

    def search_manual(self, clear_if_empty: bool = False) -> None:
        term = self.search_input.text().strip()
        self.results_list.clear()
        if clear_if_empty and not term:
            self.search_state_label.setText("Ingresa un nombre o escanea para buscar")
            return

        products = self.service.list_products()[:30] if not term else self.service.search_products_by_name(term)
        for product in products:
            item = QListWidgetItem(
                f"{product['name']} | Stock: {format_number(float(product['stock']))} | "
                f"{format_currency(float(product['sale_price']))}"
            )
            item.setData(Qt.ItemDataRole.UserRole, int(product["id"]))
            self.results_list.addItem(item)

        if not products:
            self.search_state_label.setText("Sin resultados para la busqueda")
        elif not term:
            self.search_state_label.setText("Lista rapida cargada")
        else:
            self.search_state_label.setText(f"{len(products)} resultado(s)")

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
            self.set_feedback(
                f"Stock insuficiente para {product['name']} (disponible: {format_number(stock)})",
                ok=False,
            )
            return

        self.cart[product_id] = {
            "product_id": product_id,
            "name": product["name"],
            "quantity": desired_qty,
            "unit_price": float(product["sale_price"]),
        }
        self.render_cart()
        self.set_feedback(f"{product['name']} agregado al carrito", ok=True)

    def current_total(self) -> float:
        return sum(float(item["quantity"]) * float(item["unit_price"]) for item in self.cart.values())

    def render_cart(self) -> None:
        items = list(self.cart.values())
        self.cart_table.setRowCount(len(items))
        total = 0.0

        for row_idx, item in enumerate(items):
            subtotal = float(item["quantity"]) * float(item["unit_price"])
            total += subtotal

            product_item = QTableWidgetItem(item["name"])
            product_item.setData(Qt.ItemDataRole.UserRole, item["product_id"])

            self.cart_table.setItem(row_idx, 0, product_item)
            self.cart_table.setItem(row_idx, 1, QTableWidgetItem(format_number(float(item["quantity"]))))
            self.cart_table.setItem(row_idx, 2, QTableWidgetItem(format_currency(float(item["unit_price"]))))
            self.cart_table.setItem(row_idx, 3, QTableWidgetItem(format_currency(float(subtotal))))

        self.total_label.setText(format_currency(total))
        self.cart_meta_label.setText(f"{len(items)} producto(s) en carrito")
        self.cart_empty_label.setVisible(len(items) == 0)
        self.total_animation.stop()
        self.total_animation.start()

        if self.partial_toggle_btn.isChecked():
            if self.paid_amount_input.value() > total:
                self.paid_amount_input.blockSignals(True)
                self.paid_amount_input.setValue(total)
                self.paid_amount_input.blockSignals(False)
        else:
            self.paid_amount_input.blockSignals(True)
            self.paid_amount_input.setValue(total)
            self.paid_amount_input.blockSignals(False)

        self.update_partial_debt_label()

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
        self.set_feedback("Cantidad actualizada", ok=True)
        self.focus_scan()

    def remove_selected(self) -> None:
        product_id = self.selected_product_id()
        if product_id is None:
            return
        self.cart.pop(product_id, None)
        self.render_cart()
        self.set_feedback("Producto quitado del carrito", ok=True)
        self.focus_scan()

    def clear_cart(self, announce: bool = True) -> None:
        had_items = bool(self.cart)
        self.cart.clear()
        self.render_cart()
        if had_items and announce:
            self.set_feedback("Carrito vaciado", ok=True)
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
            self.set_feedback("Agrega al menos un producto para cobrar", ok=False)
            return

        selected_payment = self.payment_combo.currentText().strip()
        customer_id = self.selected_customer_id()
        total = self.current_total()
        partial_enabled = self.partial_toggle_btn.isChecked()
        paid_amount = float(self.paid_amount_input.value()) if partial_enabled else None
        balance_due = max(total - (paid_amount or 0.0), 0.0) if partial_enabled else 0.0
        mode = "credit" if balance_due > 0 else "cash"

        if partial_enabled:
            if paid_amount is None:
                paid_amount = 0.0
            if paid_amount < 0:
                self.set_feedback("El monto pagado no puede ser negativo", ok=False)
                return
            if paid_amount - total > 1e-9:
                self.set_feedback("El monto pagado no puede superar el total", ok=False)
                return

        if mode == "credit" and customer_id is None:
            self.set_feedback("Para pago parcial debes seleccionar un cliente", ok=False)
            return

        items = [{"product_id": item["product_id"], "quantity": item["quantity"]} for item in self.cart.values()]

        try:
            result = self.service.create_sale(
                items=items,
                payment_method=selected_payment,
                customer_id=customer_id,
                sale_type=mode,
                paid_amount=paid_amount,
            )
            ticket = self.service.create_sale_ticket(int(result["sale_id"]))
        except ValidationError as exc:
            self.set_feedback(str(exc), ok=False)
            self.focus_scan()
            return
        except OSError as exc:
            self.clear_cart(announce=False)
            self.set_feedback(f"Venta guardada sin ticket: {exc}", ok=False)
            if self.on_data_changed:
                self.on_data_changed()
            self.focus_scan()
            return
        self.clear_cart(announce=False)
        self.set_feedback(
            f"Venta #{result['sale_id']} registrada | Pagado {format_currency(float(result['paid_amount']))} | "
            f"Saldo {format_currency(float(result['balance_due']))}",
            ok=True,
        )
        if self.on_data_changed:
            self.on_data_changed()
        self.reload_customers()

        dialog = TicketDialog(
            service=self.service,
            sale_id=int(result["sale_id"]),
            ticket_text=str(ticket["text"]),
            ticket_path=str(ticket["path"]),
            parent=self,
        )
        dialog.exec()
        self.focus_scan()
