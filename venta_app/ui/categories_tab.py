from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import ValidationError, WarehouseService


class CategoriesTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.current_category_id: int | None = None

        root = QVBoxLayout(self)
        root.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(14)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Categoria", "Margen %"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        self.table.horizontalHeader().setStretchLastSection(True)

        body.addWidget(self.table, stretch=3)

        form_frame = QFrame()
        form_frame.setObjectName("panel")
        form_layout = QVBoxLayout(form_frame)

        title = QLabel("Categorias y margenes")
        title.setObjectName("sectionTitle")
        form_layout.addWidget(title)

        self.id_label = QLabel("ID: nueva")
        self.id_label.setObjectName("mutedText")
        form_layout.addWidget(self.id_label)

        form = QFormLayout()

        self.name_input = QLineEdit()
        self.margin_input = QDoubleSpinBox()
        self.margin_input.setRange(0, 500)
        self.margin_input.setDecimals(2)
        self.margin_input.setSuffix(" %")

        form.addRow("Nombre", self.name_input)
        form.addRow("Margen", self.margin_input)

        form_layout.addLayout(form)

        actions = QHBoxLayout()
        self.new_btn = QPushButton("Nueva")
        self.new_btn.clicked.connect(self.new_category)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.clicked.connect(self.save_category)
        self.delete_btn = QPushButton("Eliminar")
        self.delete_btn.clicked.connect(self.delete_category)

        actions.addWidget(self.new_btn)
        actions.addWidget(self.save_btn)
        actions.addWidget(self.delete_btn)
        form_layout.addLayout(actions)

        form_layout.addSpacing(14)

        rounding_title = QLabel("Redondeo de precios")
        rounding_title.setObjectName("sectionTitle")
        form_layout.addWidget(rounding_title)

        rounding_form = QFormLayout()
        self.rounding_base_input = QSpinBox()
        self.rounding_base_input.setRange(100, 100000)
        self.rounding_base_input.setSingleStep(100)
        rounding_form.addRow("Base", self.rounding_base_input)
        form_layout.addLayout(rounding_form)

        self.save_rounding_btn = QPushButton("Aplicar redondeo")
        self.save_rounding_btn.clicked.connect(self.save_rounding)
        form_layout.addWidget(self.save_rounding_btn)

        note = QLabel(
            "Al cambiar margen o redondeo, los productos con precio automatico se recalculan solos."
        )
        note.setWordWrap(True)
        note.setObjectName("mutedText")
        form_layout.addWidget(note)

        form_layout.addSpacing(14)

        ticket_title = QLabel("Datos del ticket")
        ticket_title.setObjectName("sectionTitle")
        form_layout.addWidget(ticket_title)

        ticket_form = QFormLayout()
        self.store_name_input = QLineEdit()
        self.store_address_input = QLineEdit()
        self.store_phone_input = QLineEdit()
        self.ticket_footer_input = QLineEdit()
        ticket_form.addRow("Comercio", self.store_name_input)
        ticket_form.addRow("Direccion", self.store_address_input)
        ticket_form.addRow("Telefono", self.store_phone_input)
        ticket_form.addRow("Pie ticket", self.ticket_footer_input)
        form_layout.addLayout(ticket_form)

        self.save_ticket_btn = QPushButton("Guardar ticket")
        self.save_ticket_btn.clicked.connect(self.save_ticket_config)
        form_layout.addWidget(self.save_ticket_btn)

        form_layout.addStretch(1)

        body.addWidget(form_frame, stretch=2)
        root.addLayout(body, stretch=1)

    def refresh(self) -> None:
        categories = self.service.list_categories()
        self.table.setRowCount(len(categories))

        for row_idx, category in enumerate(categories):
            id_item = QTableWidgetItem(str(category["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, int(category["id"]))
            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(category["name"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(f"{float(category['margin_percent']):.2f}"))

        self.table.resizeColumnsToContents()
        self.rounding_base_input.setValue(self.service.get_rounding_base())
        ticket_config = self.service.get_ticket_config()
        self.store_name_input.setText(ticket_config["store_name"])
        self.store_address_input.setText(ticket_config["store_address"])
        self.store_phone_input.setText(ticket_config["store_phone"])
        self.ticket_footer_input.setText(ticket_config["ticket_footer"])

    def new_category(self) -> None:
        self.current_category_id = None
        self.id_label.setText("ID: nueva")
        self.name_input.clear()
        self.margin_input.setValue(30)

    def on_selection_changed(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return

        self.current_category_id = int(id_item.data(Qt.ItemDataRole.UserRole))
        self.id_label.setText(f"ID: {self.current_category_id}")
        self.name_input.setText(self.table.item(row, 1).text())
        self.margin_input.setValue(float(self.table.item(row, 2).text()))

    def save_category(self) -> None:
        name = self.name_input.text()
        margin = float(self.margin_input.value())

        try:
            if self.current_category_id is None:
                self.current_category_id = self.service.create_category(name, margin)
            else:
                self.service.update_category(self.current_category_id, name, margin)
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Guardado", "Categoria guardada")

    def delete_category(self) -> None:
        if self.current_category_id is None:
            return

        confirm = QMessageBox.question(
            self,
            "Eliminar categoria",
            "Esta accion no se puede deshacer. Continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            self.service.delete_category(self.current_category_id)
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo eliminar", str(exc))
            return

        self.new_category()
        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()

    def save_rounding(self) -> None:
        base = int(self.rounding_base_input.value())
        try:
            self.service.set_rounding_base(base)
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo aplicar", str(exc))
            return

        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Aplicado", "Redondeo actualizado")

    def save_ticket_config(self) -> None:
        try:
            self.service.set_ticket_config(
                store_name=self.store_name_input.text(),
                store_address=self.store_address_input.text(),
                store_phone=self.store_phone_input.text(),
                ticket_footer=self.ticket_footer_input.text(),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Guardado", "Configuracion de ticket actualizada")
