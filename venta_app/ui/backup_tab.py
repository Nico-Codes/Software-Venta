from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services import ValidationError, WarehouseService
from .common import format_number


class BackupTab(QWidget):
    def __init__(self, service: WarehouseService, on_data_changed: Callable[[], None] | None = None) -> None:
        super().__init__()
        self.service = service
        self.on_data_changed = on_data_changed

        root = QVBoxLayout(self)
        root.setSpacing(12)

        settings_frame = QFrame()
        settings_frame.setObjectName("panel")
        settings_layout = QVBoxLayout(settings_frame)

        settings_title = QLabel("Backup automatico")
        settings_title.setObjectName("sectionTitle")
        settings_layout.addWidget(settings_title)

        form = QFormLayout()
        self.auto_enabled_check = QCheckBox("Habilitado")
        self.keep_days_input = QSpinBox()
        self.keep_days_input.setRange(1, 365)
        form.addRow("Estado", self.auto_enabled_check)
        form.addRow("Conservar dias", self.keep_days_input)
        settings_layout.addLayout(form)

        self.save_settings_btn = QPushButton("Guardar configuracion")
        self.save_settings_btn.clicked.connect(self.save_auto_settings)
        settings_layout.addWidget(self.save_settings_btn)

        root.addWidget(settings_frame)

        actions_frame = QFrame()
        actions_frame.setObjectName("panel")
        actions_layout = QVBoxLayout(actions_frame)

        action_title = QLabel("Acciones")
        action_title.setObjectName("sectionTitle")
        actions_layout.addWidget(action_title)

        buttons = QHBoxLayout()
        self.backup_now_btn = QPushButton("Crear backup ahora")
        self.backup_now_btn.clicked.connect(self.create_backup_now)

        self.restore_selected_btn = QPushButton("Restaurar seleccionado")
        self.restore_selected_btn.clicked.connect(self.restore_selected_backup)

        self.restore_file_btn = QPushButton("Restaurar desde archivo")
        self.restore_file_btn.clicked.connect(self.restore_from_file)

        self.export_csv_btn = QPushButton("Exportar CSV")
        self.export_csv_btn.clicked.connect(self.export_csv)

        buttons.addWidget(self.backup_now_btn)
        buttons.addWidget(self.restore_selected_btn)
        buttons.addWidget(self.restore_file_btn)
        buttons.addWidget(self.export_csv_btn)
        buttons.addStretch(1)

        actions_layout.addLayout(buttons)

        self.info_label = QLabel("-")
        self.info_label.setObjectName("mutedText")
        actions_layout.addWidget(self.info_label)

        root.addWidget(actions_frame)

        table_title = QLabel("Backups disponibles")
        table_title.setObjectName("sectionTitle")
        root.addWidget(table_title)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Archivo", "Tipo", "Fecha", "Tamano"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        root.addWidget(self.table, stretch=1)

    def refresh(self) -> None:
        settings = self.service.get_auto_backup_settings()
        self.auto_enabled_check.setChecked(bool(settings["enabled"]))
        self.keep_days_input.setValue(int(settings["keep_days"]))

        backups = self.service.list_backups()
        self.table.setRowCount(len(backups))
        for idx, backup in enumerate(backups):
            item = QTableWidgetItem(str(backup["name"]))
            item.setData(Qt.ItemDataRole.UserRole, str(backup["path"]))
            self.table.setItem(idx, 0, item)
            self.table.setItem(idx, 1, QTableWidgetItem(str(backup.get("type") or "manual")))
            self.table.setItem(idx, 2, QTableWidgetItem(str(backup.get("created_at") or "")))
            size_kb = float(backup.get("size_bytes", 0)) / 1024.0
            self.table.setItem(idx, 3, QTableWidgetItem(f"{format_number(size_kb)} KB"))
        self.table.resizeColumnsToContents()

        self.info_label.setText(f"Carpeta backups: {self.service.backup_dir()}")

    def save_auto_settings(self) -> None:
        try:
            self.service.set_auto_backup_settings(
                enabled=bool(self.auto_enabled_check.isChecked()),
                keep_days=int(self.keep_days_input.value()),
            )
        except ValidationError as exc:
            QMessageBox.warning(self, "No se pudo guardar", str(exc))
            return

        QMessageBox.information(self, "Configuracion", "Backup automatico actualizado")

    def create_backup_now(self) -> None:
        backup = self.service.create_backup(prefix="manual")
        self.refresh()
        self.info_label.setText(f"Backup creado: {backup['path']}")
        QMessageBox.information(self, "Backup", f"Respaldo creado\n{backup['path']}")

    def _selected_backup_path(self) -> str | None:
        selected = self.table.selectedItems()
        if not selected:
            return None
        row = selected[0].row()
        item = self.table.item(row, 0)
        if not item:
            return None
        return str(item.data(Qt.ItemDataRole.UserRole))

    def restore_selected_backup(self) -> None:
        path = self._selected_backup_path()
        if not path:
            QMessageBox.warning(self, "Sin seleccion", "Selecciona un backup")
            return
        self._restore(path)

    def restore_from_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar backup",
            str(self.service.backup_dir()),
            "Base de datos (*.db)",
        )
        if not path:
            return
        self._restore(path)

    def _restore(self, path: str) -> None:
        confirm = QMessageBox.question(
            self,
            "Restaurar backup",
            "Se reemplazara la base actual. Continuar?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        try:
            result = self.service.restore_database_from_backup(path)
        except (ValidationError, OSError) as exc:
            QMessageBox.warning(self, "No se pudo restaurar", str(exc))
            return

        if self.on_data_changed:
            self.on_data_changed()
        self.refresh()

        QMessageBox.information(
            self,
            "Restauracion completada",
            f"Base restaurada desde\n{result['source']}",
        )

    def export_csv(self) -> None:
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Carpeta destino",
            str(self.service.data_dir()),
        )
        if not target_dir:
            return

        result = self.service.export_all_tables_to_csv(target_dir)
        self.info_label.setText(f"CSV exportados en: {result['directory']}")
        QMessageBox.information(
            self,
            "Exportacion completada",
            f"Archivos generados: {len(result['files'])}\n{result['directory']}",
        )
