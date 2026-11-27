"""Text cards: text from the micro:bit, text to the micro:bit, and a generic fallback."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from ...core.model import Card, Scalar
from .base import CardWidget

#: Longest text the PC sends in one SET (keeps BLE packets reasonable).
MAX_TEXT_LENGTH = 64


class TextInCard(CardWidget):
    """Shows the latest text received from the micro:bit."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.text_label = QLabel()
        self.text_label.setWordWrap(True)
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.text_label.setTextFormat(Qt.TextFormat.PlainText)
        self.text_label.setStyleSheet("font-size: 18px;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.text_label)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        text = str(value)
        self.text_label.setText(text if text else "—")


class TextOutCard(CardWidget):
    """A text box and a Send button (Enter also sends)."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.edit = QLineEdit()
        self.edit.setMaxLength(MAX_TEXT_LENGTH)
        self.edit.setPlaceholderText("Type a message…")
        self.edit.returnPressed.connect(self.send)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send)
        self.last_label = QLabel()
        self.last_label.setTextFormat(Qt.TextFormat.PlainText)
        self.last_label.setStyleSheet("color: palette(mid);")

        row = QHBoxLayout()
        row.addWidget(self.edit, 1)
        row.addWidget(self.send_button)
        layout = QVBoxLayout(self)
        layout.addLayout(row)
        layout.addWidget(self.last_label)

        self.inputs += [self.edit, self.send_button]
        self.show_value(card.value)

    def send(self) -> None:
        text = self.edit.text()
        if not text:
            return
        self.commit(text)
        self.edit.clear()

    def show_value(self, value: Scalar) -> None:
        self.last_label.setText(f"Last sent: {value}" if value else "Nothing sent yet")


class GenericCard(CardWidget):
    """Fallback for card types without a dedicated widget yet (e.g. JOYSTICK).

    Shows the raw value; writable cards also get a box to type a value.
    """

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setTextFormat(Qt.TextFormat.PlainText)
        self.value_label.setStyleSheet("font-size: 20px; font-weight: 600;")
        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)

        self.edit: QLineEdit | None = None
        if card.is_writable:
            self.edit = QLineEdit()
            self.edit.setPlaceholderText("value, e.g. 0,0" if card.is_text else "value")
            self.edit.returnPressed.connect(self._send)
            button = QPushButton("Set")
            button.clicked.connect(self._send)
            row = QHBoxLayout()
            row.addWidget(self.edit, 1)
            row.addWidget(button)
            layout.addLayout(row)
            self.inputs += [self.edit, button]
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        self.value_label.setText(str(value) if value != "" else "—")

    def _send(self) -> None:
        if self.edit is None:
            return
        text = self.edit.text().strip()
        if not text:
            return
        try:
            value = self.card.coerce(text)
        except ValueError:
            self.edit.selectAll()
            return
        self.commit(value)
