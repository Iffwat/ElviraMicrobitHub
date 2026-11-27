"""Digital cards: input LED, output toggle and momentary button."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ...core.model import Card, Scalar
from .base import CardWidget

_LED_STYLE = "border-radius: 18px; border: 2px solid palette(mid); background: {};"
_ON_COLOR = "#27ae60"
_OFF_COLOR = "palette(window)"


class Led(QLabel):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(36, 36)
        self.set_on(False)

    def set_on(self, on: bool) -> None:
        self.on = on
        self.setStyleSheet(_LED_STYLE.format(_ON_COLOR if on else _OFF_COLOR))


class DigitalInCard(CardWidget):
    """Read-only HIGH/LOW indicator."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.led = Led()
        self.state_label = QLabel()
        self.state_label.setStyleSheet("font-size: 22px; font-weight: 600;")

        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(self.led)
        row.addSpacing(12)
        row.addWidget(self.state_label)
        row.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        on = bool(value)
        self.led.set_on(on)
        self.state_label.setText("HIGH" if on else "LOW")


class DigitalOutCard(CardWidget):
    """ON/OFF toggle button."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.led = Led()
        self.toggle = QPushButton()
        self.toggle.setCheckable(True)
        self.toggle.setMinimumHeight(40)
        self.toggle.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.toggle.toggled.connect(self._on_toggled)

        row = QHBoxLayout()
        row.addWidget(self.led)
        row.addWidget(self.toggle, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(row)

        self.inputs.append(self.toggle)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        on = bool(value)
        self.toggle.blockSignals(True)
        self.toggle.setChecked(on)
        self.toggle.blockSignals(False)
        self._paint(on)

    def _paint(self, on: bool) -> None:
        self.led.set_on(on)
        self.toggle.setText("ON" if on else "OFF")

    def _on_toggled(self, on: bool) -> None:
        self._paint(on)
        self.commit(1 if on else 0)


class ButtonCard(CardWidget):
    """Momentary button: sends 1 while held down and 0 when released."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.button = QPushButton("Hold")
        self.button.setMinimumHeight(56)
        self.button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.button.setStyleSheet("font-size: 16px; font-weight: 600;")
        self.button.pressed.connect(self._on_pressed)
        self.button.released.connect(self._on_released)
        self.state_label = QLabel()
        self.state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.addWidget(self.button)
        layout.addWidget(self.state_label)

        self.inputs.append(self.button)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        self.state_label.setText("pressed (1)" if value else "released (0)")

    def _on_pressed(self) -> None:
        self.begin_interaction()
        self.show_value(1)
        self.commit(1)

    def _on_released(self) -> None:
        self.show_value(0)
        self.commit(0)
        self.end_interaction()

    def set_live(self, live: bool) -> None:
        if not live and self.button.isDown():
            self.button.setDown(False)
        super().set_live(live)
