"""Slider cards: Motor, Servo and Analog output."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget

from ...core.model import Card, Scalar
from .base import CardWidget


class SliderCard(CardWidget):
    """A slider plus a big value label.

    Dragging streams values without ACK; releasing the slider (or using the
    keyboard / mouse wheel / buttons) sends the final value with ACK.
    """

    unit = ""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        lo = card.min if card.min is not None else 0
        hi = card.max if card.max is not None else 1023

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("font-size: 22px; font-weight: 600;")

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setRange(lo, hi)
        self.slider.setPageStep(max(1, (hi - lo) // 10))
        self.slider.sliderPressed.connect(self.begin_interaction)
        self.slider.sliderReleased.connect(self._on_released)
        self.slider.valueChanged.connect(self._on_slider)

        self.range_label = QLabel(f"{lo}{self.unit} … {hi}{self.unit}")
        self.range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.range_label.setStyleSheet("color: palette(mid); font-size: 11px;")

        self.buttons = QHBoxLayout()
        self._presets: dict[QPushButton, int] = {}
        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self.slider)
        layout.addWidget(self.range_label)
        layout.addLayout(self.buttons)

        self.inputs.append(self.slider)
        self.show_value(card.value)

    def add_button(self, text: str, value: int, tooltip: str = "") -> QPushButton:
        button = QPushButton(text)
        button.setToolTip(tooltip)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        # A bound method, not a lambda capturing self: PySide holds bound
        # methods weakly, so the card can be freed (a lambda keeps it alive
        # until interpreter exit, where Qt then crashes).
        self._presets[button] = value
        button.clicked.connect(self._on_preset)
        self.buttons.addWidget(button)
        self.inputs.append(button)
        return button

    def _on_preset(self) -> None:
        value = self._presets.get(self.sender())
        if value is not None:
            self.set_from_user(value)

    def set_from_user(self, value: int) -> None:
        """Move the slider as if the user did it, and send the value with ACK."""
        value = max(self.slider.minimum(), min(self.slider.maximum(), value))
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._set_label(value)
        self.commit(value)

    def show_value(self, value: Scalar) -> None:
        if not isinstance(value, int):
            return
        self.slider.blockSignals(True)
        self.slider.setValue(value)
        self.slider.blockSignals(False)
        self._set_label(value)

    def _set_label(self, value: int) -> None:
        self.value_label.setText(f"{value}{self.unit}")

    def _on_slider(self, value: int) -> None:
        self._set_label(value)
        if self.slider.isSliderDown():
            self.stream(value)
        else:  # keyboard, mouse wheel, click on the groove
            self.commit(value)

    def _on_released(self) -> None:
        self.commit(self.slider.value())
        self.end_interaction()


class MotorCard(SliderCard):
    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        lo, hi = self.slider.minimum(), self.slider.maximum()
        self.add_button("◀ Rev", lo, "Full speed backwards")
        self.stop_button = self.add_button("■ Stop", 0, "Stop this motor")
        self.add_button("Fwd ▶", hi, "Full speed forwards")

    def _set_label(self, value: int) -> None:
        arrow = "▶" if value > 0 else "◀" if value < 0 else "■"
        self.value_label.setText(f"{arrow} {value}")


class ServoCard(SliderCard):
    unit = "°"

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        lo, hi = self.slider.minimum(), self.slider.maximum()
        self.add_button("Min", lo)
        self.add_button("Center", (lo + hi) // 2)
        self.add_button("Max", hi)


class AnalogOutCard(SliderCard):
    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.add_button("Off", self.slider.minimum())
        self.add_button("Max", self.slider.maximum())
