from __future__ import annotations

from typing import Callable

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
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ..services import ValidationError, WarehouseService
from .common import format_currency, format_number


class CustomersTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.current_customer_id: int | None = None

        root = QVBoxLayout(self)
        root.setSpacing(10)

        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar cliente por nombre o telefono")
        self.search_input.returnPressed.connect(self.refresh)

        self.search_btn = QPushButton("Buscar")
        self.search_btn.clicked.connect(self.refresh)
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.clicked.connect(self.new_customer)

        toolbar.addWidget(self.search_input, stretch=1)
        toolbar.addWidget(self.search_btn)
        toolbar.addWidget(self.new_btn)
        root.addLayout(toolbar)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["ID", "Cliente", "Telefono", "Deuda", "Limite", "Alerta"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_customer_selected)
        self.table.horizontalHeader().setStretchLastSection(True)

        body.addWidget(self.table, stretch=3)

        right = QVBoxLayout()

        form_frame = QFrame()
        form_frame.setObjectName("panel")
        form_box = QVBoxLayout(form_frame)

        title = QLabel("Ficha del cliente")
        title.setObjectName("sectionTitle")
        self.customer_info_label = QLabel("Sin seleccionar")
        self.customer_info_label.setObjectName("mutedText")

        form_box.addWidget(title)
        form_box.addWidget(self.customer_info_label)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.phone_input = QLineEdit()
        self.email_input = QLineEdit()

        self.alert_limit_input = QDoubleSpinBox()
        self.alert_limit_input.setRange(0, 9_999_999)
        self.alert_limit_input.setDecimals(2)
        self.alert_limit_input.setValue(50000)

        self.active_check = QCheckBox("Cliente activo")
        self.active_check.setChecked(True)

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(72)

        form.addRow("Nombre", self.name_input)
        form.addRow("Telefono", self.phone_input)
        form.addRow("Email", self.email_input)
        form.addRow("Limite alerta", self.alert_limit_input)
        form.addRow("", self.active_check)
        form.addRow("Notas", self.notes_input)

        form_box.addLayout(form)

        actions = QHBoxLayout()
        self.save_btn = QPushButton("Guardar")
        self.save_btn.clicked.connect(self.save_customer)
        actions.addWidget(self.save_btn)
        actions.addStretch(1)

        form_box.addLayout(actions)

        summary_row = QHBoxLayout()
        self.total_purchases_label = QLabel("Compras: $ 0,00")
        self.total_paid_label = QLabel("Pagado: $ 0,00")
        self.total_debt_label = QLabel("Deuda: $ 0,00")
        summary_row.addWidget(self.total_purchases_label)
        summary_row.addWidget(self.total_paid_label)
        summary_row.addWidget(self.total_debt_label)
        form_box.addLayout(summary_row)

        right.addWidget(form_frame)

        payment_frame = QFrame()
        payment_frame.setObjectName("panel")
        payment_layout = QVBoxLayout(payment_frame)

        payment_title = QLabel("Registrar pago")
        payment_title.setObjectName("sectionTitle")
        payment_layout.addWidget(payment_title)

        pay_form = QFormLayout()
        self.payment_sale_combo = QComboBox()
        self.payment_sale_combo.addItem("Aplicar a deudas mas antiguas", None)

        self.payment_amount_input = QDoubleSpinBox()
        self.payment_amount_input.setRange(0, 9_999_999)
        self.payment_amount_input.setDecimals(2)

        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems(self.service.PAYMENT_METHODS)

        self.payment_note_input = QLineEdit()
        self.payment_note_input.setPlaceholderText("Nota opcional")

        pay_form.addRow("Venta", self.payment_sale_combo)
        pay_form.addRow("Monto", self.payment_amount_input)
        pay_form.addRow("Metodo", self.payment_method_combo)
        pay_form.addRow("Nota", self.payment_note_input)
        payment_layout.addLayout(pay_form)

        self.pay_btn = QPushButton("Aplicar pago")
        self.pay_btn.clicked.connect(self.register_payment)
        payment_layout.addWidget(self.pay_btn)

        right.addWidget(payment_frame)

        details_frame = QFrame()
        details_frame.setObjectName("panel")
        details_layout = QVBoxLayout(details_frame)

        open_title = QLabel("Ventas con saldo")
        open_title.setObjectName("sectionTitle")
        details_layout.addWidget(open_title)

        self.open_sales_table = QTableWidget(0, 6)
        self.open_sales_table.setHorizontalHeaderLabels(["Venta", "Fecha", "Total", "Pagado", "Saldo", "Estado"])
        self.open_sales_table.verticalHeader().setVisible(False)
        self.open_sales_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.open_sales_table.horizontalHeader().setStretchLastSection(True)
        details_layout.addWidget(self.open_sales_table)

        payments_title = QLabel("Pagos registrados")
        payments_title.setObjectName("sectionTitle")
        details_layout.addWidget(payments_title)

        self.payments_table = QTableWidget(0, 5)
        self.payments_table.setHorizontalHeaderLabels(["Fecha", "Monto", "Metodo", "Venta", "Nota"])
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.payments_table.horizontalHeader().setStretchLastSection(True)
        details_layout.addWidget(self.payments_table)

        right.addWidget(details_frame, stretch=1)

        body.addLayout(right, stretch=4)
        root.addLayout(body, stretch=1)

        self.new_customer()

    def refresh(self) -> None:
        customers = self.service.list_customers(search=self.search_input.text().strip())
        self.table.setRowCount(len(customers))

        for row_idx, customer in enumerate(customers):
            id_item = QTableWidgetItem(str(customer["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, int(customer["id"]))
            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(customer["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(customer.get("phone") or "-"))
            self.table.setItem(row_idx, 3, QTableWidgetItem(format_currency(float(customer["debt_total"]))))
            self.table.setItem(row_idx, 4, QTableWidgetItem(format_currency(float(customer["alert_limit"]))))
            self.table.setItem(row_idx, 5, QTableWidgetItem("Si" if customer["over_limit"] else "No"))

        self.table.resizeColumnsToContents()

        if self.current_customer_id is not None:
            self._select_customer_in_table(self.current_customer_id)

    def _select_customer_in_table(self, customer_id: int) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and int(item.data(Qt.ItemDataRole.UserRole)) == customer_id:
                self.table.selectRow(row)
                return

    def new_customer(self) -> None:
        self.current_customer_id = None
        self.customer_info_label.setText("ID: nuevo")
        self.name_input.clear()
        self.phone_input.clear()
        self.email_input.clear()
        self.alert_limit_input.setValue(50000)
        self.active_check.setChecked(True)
        self.notes_input.clear()
        self.total_purchases_label.setText("Compras: $ 0,00")
        self.total_paid_label.setText("Pagado: $ 0,00")
        self.total_debt_label.setText("Deuda: $ 0,00")
        self.open_sales_table.setRowCount(0)
        self.payments_table.setRowCount(0)
        self.payment_sale_combo.clear()
        self.payment_sale_combo.addItem("Aplicar a deudas mas antiguas", None)

    def on_customer_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return

        customer_id = int(id_item.data(Qt.ItemDataRole.UserRole))
        self.current_customer_id = customer_id

        account = self.service.get_customer_account(customer_id)
        customer = account["customer"]
        summary = account["summary"]

        self.customer_info_label.setText(f"ID: {customer_id}")
        self.name_input.setText(customer["name"])
        self.phone_input.setText(customer.get("phone") or "")
        self.email_input.setText(customer.get("email") or "")
        self.alert_limit_input.setValue(float(customer.get("alert_limit") or 0))
        self.active_check.setChecked(bool(customer.get("active")))
        self.notes_input.setPlainText(customer.get("notes") or "")

        self.total_purchases_label.setText(f"Compras: {format_currency(float(summary['total_purchases']))}")
        self.total_paid_label.setText(f"Pagado: {format_currency(float(summary['total_paid']))}")
        self.total_debt_label.setText(f"Deuda: {format_currency(float(summary['total_debt']))}")

        self.load_open_sales(account["open_sales"])
        self.load_payments(account["payments"])

    def load_open_sales(self, open_sales: list[dict]) -> None:
        self.open_sales_table.setRowCount(len(open_sales))
        self.payment_sale_combo.clear()
        self.payment_sale_combo.addItem("Aplicar a deudas mas antiguas", None)

        for idx, sale in enumerate(open_sales):
            self.open_sales_table.setItem(idx, 0, QTableWidgetItem(str(sale["id"])))
            self.open_sales_table.setItem(idx, 1, QTableWidgetItem(str(sale["sold_at"])))
            self.open_sales_table.setItem(idx, 2, QTableWidgetItem(format_currency(float(sale["total"]))))
            self.open_sales_table.setItem(idx, 3, QTableWidgetItem(format_currency(float(sale["paid_amount"]))))
            self.open_sales_table.setItem(idx, 4, QTableWidgetItem(format_currency(float(sale["balance_due"]))))
            self.open_sales_table.setItem(idx, 5, QTableWidgetItem(str(sale["status"])))

            label = f"Venta #{sale['id']} | saldo {format_currency(float(sale['balance_due']))}"
            self.payment_sale_combo.addItem(label, int(sale["id"]))

        self.open_sales_table.resizeColumnsToContents()

    def load_payments(self, payments: list[dict]) -> None:
        self.payments_table.setRowCount(len(payments))
        for idx, payment in enumerate(payments):
            sale_ref = f"#{payment['sale_id']}" if payment.get("sale_id") else "-"
            self.payments_table.setItem(idx, 0, QTableWidgetItem(str(payment["paid_at"])))
            self.payments_table.setItem(idx, 1, QTableWidgetItem(format_currency(float(payment["amount"]))))
            self.payments_table.setItem(idx, 2, QTableWidgetItem(str(payment["payment_method"])))
            self.payments_table.setItem(idx, 3, QTableWidgetItem(sale_ref))
            self.payments_table.setItem(idx, 4, QTableWidgetItem(str(payment.get("note") or "-")))

        self.payments_table.resizeColumnsToContents()

    def save_customer(self) -> None:
        kwargs = {
            "name": self.name_input.text(),
            "phone": self.phone_input.text(),
            "email": self.email_input.text(),
            "alert_limit": float(self.alert_limit_input.value()),
            "notes": self.notes_input.toPlainText(),
        }

        try:
            if self.current_customer_id is None:
                self.current_customer_id = self.service.create_customer(**kwargs)
            else:
                self.service.update_customer(
                    self.current_customer_id,
                    **kwargs,
                    active=bool(self.active_check.isChecked()),
                )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.refresh()
        if self.current_customer_id is not None:
            self._select_customer_in_table(self.current_customer_id)

        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Guardado", "Cliente guardado correctamente")

    def register_payment(self) -> None:
        if self.current_customer_id is None:
            QMessageBox.warning(self, "Sin cliente", "Selecciona un cliente")
            return

        amount = float(self.payment_amount_input.value())
        if amount <= 0:
            QMessageBox.warning(self, "Monto invalido", "Ingresa un monto mayor a cero")
            return

        selected_sale = self.payment_sale_combo.currentData()

        try:
            result = self.service.register_customer_payment(
                customer_id=self.current_customer_id,
                amount=amount,
                payment_method=self.payment_method_combo.currentText(),
                note=self.payment_note_input.text(),
                sale_id=int(selected_sale) if selected_sale else None,
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo registrar", str(exc))
            return

        self.payment_amount_input.setValue(0)
        self.payment_note_input.clear()

        self.refresh()
        self._select_customer_in_table(self.current_customer_id)

        if self.on_data_changed:
            self.on_data_changed()

        QMessageBox.information(
            self,
            "Pago aplicado",
            f"Aplicado: {format_currency(float(result['applied_amount']))}\n"
            f"Sin aplicar: {format_currency(float(result['remaining_unapplied']))}",
        )
