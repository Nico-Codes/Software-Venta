from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from ..services import ValidationError, WarehouseService
from ..version import APP_VERSION
from .effects import apply_button_effects


LOGIN_STYLE = """
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #e9f2ff, stop:0.6 #f4f9ff, stop:1 #ffffff);
}

QFrame#loginCard {
    background: #fafdff;
    border: 1px solid #d3e5f8;
    border-radius: 20px;
}

QLabel#loginTitle {
    font-size: 25px;
    font-weight: 800;
    color: #0f2f4c;
    letter-spacing: 0.4px;
}

QLabel#loginSubtitle {
    color: #5f7489;
    font-size: 12px;
}

QLabel#loginHint {
    color: #5b7590;
    font-size: 12px;
}

QLabel#loginError {
    color: #c84e43;
    font-size: 12px;
    font-weight: 700;
}

QLineEdit {
    background: #ffffff;
    border: 1px solid #c6dcef;
    border-radius: 11px;
    padding: 10px;
    color: #13314d;
    selection-background-color: #d8ebff;
    selection-color: #133551;
}

QLineEdit:focus {
    border: 1px solid #2486df;
}

QPushButton {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #2e7de9, stop:1 #2571dd);
    color: #ffffff;
    border: 1px solid #1f67cf;
    border-radius: 11px;
    padding: 9px 16px;
    font-weight: 700;
}

QPushButton:hover {
    background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #3d8bf2, stop:1 #317ce7);
}

QPushButton:pressed {
    background: #2365c5;
}

QPushButton#loginGhost {
    background: #eaf3ff;
    color: #174e7c;
    border: 1px solid #c7dcf2;
}

QPushButton#loginGhost:hover {
    background: #deedff;
}

QCheckBox {
    color: #4b6d89;
}
"""


class LoginDialog(QDialog):
    def __init__(self, service: WarehouseService, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self.user: dict | None = None

        self.setWindowTitle(f"Ingreso al sistema - v{APP_VERSION}")
        self.setModal(True)
        self.setMinimumSize(500, 360)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.setStyleSheet(LOGIN_STYLE)

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)

        card = QFrame()
        card.setObjectName("loginCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(22, 20, 22, 20)
        card_layout.setSpacing(11)

        title = QLabel("Venta Local")
        title.setObjectName("loginTitle")
        subtitle = QLabel(f"Acceso para administrador o vendedor | Version {APP_VERSION}")
        subtitle.setObjectName("loginSubtitle")

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Usuario")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Clave")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form.addRow("Usuario", self.username_input)
        form.addRow("Clave", self.password_input)
        card_layout.addLayout(form)

        self.show_password_check = QCheckBox("Mostrar clave")
        self.show_password_check.toggled.connect(self.on_toggle_password)
        card_layout.addWidget(self.show_password_check)

        self.error_label = QLabel("")
        self.error_label.setObjectName("loginError")
        self.error_label.setVisible(False)
        self.error_label.setWordWrap(True)
        card_layout.addWidget(self.error_label)

        hint = QLabel("Acceso solo para usuarios habilitados.")
        hint.setObjectName("loginHint")
        card_layout.addWidget(hint)

        actions = QHBoxLayout()
        self.cancel_btn = QPushButton("Salir")
        self.cancel_btn.setObjectName("loginGhost")
        self.cancel_btn.clicked.connect(self.reject)

        self.login_btn = QPushButton("Ingresar")
        self.login_btn.clicked.connect(self.on_login)
        self.login_btn.setDefault(True)

        actions.addStretch(1)
        actions.addWidget(self.cancel_btn)
        actions.addWidget(self.login_btn)
        card_layout.addLayout(actions)

        root.addWidget(card)

        self.username_input.returnPressed.connect(self.password_input.setFocus)
        self.password_input.returnPressed.connect(self.on_login)
        self.username_input.setFocus(Qt.FocusReason.OtherFocusReason)

        apply_button_effects(self)

        self._open_animation = QPropertyAnimation(self, b"windowOpacity", self)
        self._open_animation.setDuration(220)
        self._open_animation.setStartValue(0.0)
        self._open_animation.setEndValue(1.0)
        self._open_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, event) -> None:  # type: ignore[override]
        super().showEvent(event)
        self.setWindowOpacity(0.0)
        self._open_animation.stop()
        self._open_animation.start()

    def on_toggle_password(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.password_input.setEchoMode(mode)

    def set_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def on_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text()
        self.error_label.setVisible(False)

        if not username or not password:
            self.set_error("Ingresa usuario y clave")
            return

        try:
            self.user = self.service.authenticate_user(username, password)
        except ValidationError as exc:
            self.set_error(str(exc))
            self.password_input.selectAll()
            self.password_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return

        self.accept()
