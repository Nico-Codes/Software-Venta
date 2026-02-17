from __future__ import annotations

from typing import Any

from PySide6.QtCore import QEasingCurve, QEvent, QObject, QPropertyAnimation, Qt
from PySide6.QtWidgets import QComboBox, QFrame, QGraphicsOpacityEffect, QPushButton, QWidget


class ButtonEffects(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._installed_buttons: set[QPushButton] = set()
        self._installed_combos: set[QComboBox] = set()
        self._tracked_popups: set[QWidget] = set()
        self._popup_effects: dict[QWidget, QGraphicsOpacityEffect] = {}
        self._popup_animations: dict[QWidget, QPropertyAnimation] = {}

    def install_on(self, root: QWidget) -> None:
        for button in root.findChildren(QPushButton):
            self._install_button(button)
        for combo in root.findChildren(QComboBox):
            self._install_combo(combo)

    def _install_button(self, button: QPushButton) -> None:
        if button in self._installed_buttons:
            return
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._installed_buttons.add(button)
        button.destroyed.connect(lambda *_: self._cleanup_button(button))

    def _cleanup_button(self, button: QPushButton) -> None:
        self._installed_buttons.discard(button)

    def _install_combo(self, combo: QComboBox) -> None:
        if combo in self._installed_combos:
            return
        combo.setCursor(Qt.CursorShape.PointingHandCursor)
        combo.view().setFrameShape(QFrame.Shape.NoFrame)

        popup = combo.view().window()
        if popup not in self._tracked_popups:
            self._tracked_popups.add(popup)
            popup.installEventFilter(self)
            popup.destroyed.connect(lambda *_: self._cleanup_popup(popup))

        self._installed_combos.add(combo)
        combo.destroyed.connect(lambda *_: self._cleanup_combo(combo))

    def _cleanup_combo(self, combo: QComboBox) -> None:
        self._installed_combos.discard(combo)

    def _cleanup_popup(self, popup: QWidget) -> None:
        self._tracked_popups.discard(popup)
        self._popup_effects.pop(popup, None)
        animation = self._popup_animations.pop(popup, None)
        if animation is not None:
            animation.stop()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(watched, QWidget) and watched in self._tracked_popups:
            self._animate_combo_popup(watched)
        return super().eventFilter(watched, event)

    def _animate_combo_popup(self, popup: QWidget) -> None:
        effect = self._popup_effects.get(popup)
        if effect is None:
            effect = QGraphicsOpacityEffect(popup)
            popup.setGraphicsEffect(effect)
            self._popup_effects[popup] = effect

        animation = self._popup_animations.get(popup)
        if animation is None or animation.targetObject() is not effect:
            animation = QPropertyAnimation(effect, b"opacity", popup)
            animation.setDuration(140)
            animation.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._popup_animations[popup] = animation

        animation.stop()
        effect.setOpacity(0.0)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.start()


def apply_button_effects(root: QWidget) -> ButtonEffects:
    manager: Any = root.property("_button_fx_manager")
    if isinstance(manager, ButtonEffects):
        manager.install_on(root)
        return manager

    manager = ButtonEffects(root)
    manager.install_on(root)
    root.setProperty("_button_fx_manager", manager)
    return manager
