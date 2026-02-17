from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
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


class UsersTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed
        self.current_user_id: int | None = None

        root = QVBoxLayout(self)
        root.setSpacing(10)

        body = QHBoxLayout()
        body.setSpacing(12)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ID", "Usuario", "Rol", "Activo", "Ultimo acceso"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self.on_user_selected)
        self.table.horizontalHeader().setStretchLastSection(True)

        body.addWidget(self.table, stretch=3)

        form_frame = QFrame()
        form_frame.setObjectName("panel")
        form_layout = QVBoxLayout(form_frame)

        title = QLabel("Usuarios")
        title.setObjectName("sectionTitle")
        self.info = QLabel("ID: nuevo")
        self.info.setObjectName("mutedText")
        form_layout.addWidget(title)
        form_layout.addWidget(self.info)

        form = QFormLayout()

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")

        self.role_combo = QComboBox()
        self.role_combo.addItem("Administrador", "admin")
        self.role_combo.addItem("Vendedor", "seller")

        self.active_check = QCheckBox("Usuario activo")
        self.active_check.setChecked(True)

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Clave (obligatoria para crear)")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Usuario", self.username_input)
        form.addRow("Rol", self.role_combo)
        form.addRow("", self.active_check)
        form.addRow("Nueva clave", self.password_input)

        form_layout.addLayout(form)

        actions = QHBoxLayout()
        self.new_btn = QPushButton("Nuevo")
        self.new_btn.clicked.connect(self.new_user)
        self.save_btn = QPushButton("Guardar")
        self.save_btn.clicked.connect(self.save_user)

        actions.addWidget(self.new_btn)
        actions.addWidget(self.save_btn)
        actions.addStretch(1)

        form_layout.addLayout(actions)
        form_layout.addStretch(1)

        body.addWidget(form_frame, stretch=2)
        root.addLayout(body, stretch=1)

        note = QLabel("Si editas un usuario y dejas la clave vacia, conserva la actual.")
        note.setObjectName("mutedText")
        root.addWidget(note)

        self.new_user()

    def refresh(self) -> None:
        users = self.service.list_users()
        self.table.setRowCount(len(users))

        for row_idx, user in enumerate(users):
            id_item = QTableWidgetItem(str(user["id"]))
            id_item.setData(Qt.ItemDataRole.UserRole, int(user["id"]))
            self.table.setItem(row_idx, 0, id_item)
            self.table.setItem(row_idx, 1, QTableWidgetItem(user["username"]))
            self.table.setItem(row_idx, 2, QTableWidgetItem(user["role"]))
            self.table.setItem(row_idx, 3, QTableWidgetItem("Si" if user["active"] else "No"))
            self.table.setItem(row_idx, 4, QTableWidgetItem(str(user.get("last_login") or "-")))

        self.table.resizeColumnsToContents()

        if self.current_user_id is not None:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and int(item.data(Qt.ItemDataRole.UserRole)) == self.current_user_id:
                    self.table.selectRow(row)
                    break

    def new_user(self) -> None:
        self.current_user_id = None
        self.info.setText("ID: nuevo")
        self.username_input.setText("")
        self.username_input.setEnabled(True)
        self.role_combo.setCurrentIndex(1)
        self.active_check.setChecked(True)
        self.password_input.setText("")

    def on_user_selected(self) -> None:
        selected = self.table.selectedItems()
        if not selected:
            return

        row = selected[0].row()
        id_item = self.table.item(row, 0)
        if not id_item:
            return

        self.current_user_id = int(id_item.data(Qt.ItemDataRole.UserRole))
        self.info.setText(f"ID: {self.current_user_id}")

        username = self.table.item(row, 1).text()
        role = self.table.item(row, 2).text()
        active = self.table.item(row, 3).text() == "Si"

        self.username_input.setText(username)
        self.username_input.setEnabled(False)
        idx = self.role_combo.findData(role)
        self.role_combo.setCurrentIndex(idx if idx >= 0 else 1)
        self.active_check.setChecked(active)
        self.password_input.setText("")

    def save_user(self) -> None:
        role = str(self.role_combo.currentData())
        active = bool(self.active_check.isChecked())
        password = self.password_input.text()

        try:
            if self.current_user_id is None:
                username = self.username_input.text().strip()
                if not password:
                    QMessageBox.warning(self, "Falta clave", "La clave es obligatoria al crear")
                    return
                self.current_user_id = self.service.create_user(username, password, role=role)
            else:
                self.service.update_user(
                    self.current_user_id,
                    role=role,
                    active=active,
                    password=password if password.strip() else None,
                )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        self.refresh()
        if self.on_data_changed:
            self.on_data_changed()
        QMessageBox.information(self, "Guardado", "Usuario actualizado")
