"""Card grid: builds one widget per card the device declares."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..core.model import Card
from .cards import CardWidget, create_card_widget
from .flow_layout import FlowLayout


class CardGrid(QScrollArea):
    """Scrollable, wrapping grid of card widgets in declaration order."""

    #: card_id, value, wait_ack (forwarded from the cards)
    valueRequested = QtSignal(str, object, bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.widgets: dict[str, CardWidget] = {}
        self._live = False

        body = QWidget()
        outer = QVBoxLayout(body)
        self.placeholder = QLabel("No device connected.\n\nPick a transport and press Connect.")
        self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.placeholder.setStyleSheet("color: palette(mid); font-size: 16px;")
        outer.addWidget(self.placeholder, 1)

        self._cards_area = QWidget()
        self.flow = FlowLayout(self._cards_area)
        outer.addWidget(self._cards_area)
        outer.addStretch()
        self.setWidget(body)
        self._update_placeholder()

    def clear(self) -> None:
        for widget in self.widgets.values():
            self.flow.removeWidget(widget)
            widget.deleteLater()
        self.widgets.clear()
        self._update_placeholder()

    def add_card(self, card: Card) -> CardWidget:
        """Add a card, or replace the widget if the card ID is declared again."""
        old = self.widgets.get(card.id)
        widget = create_card_widget(card)
        widget.valueRequested.connect(self.valueRequested)
        widget.set_live(self._live)
        if old is not None:
            index = self.flow.indexOf(old)
            self.flow.removeWidget(old)
            old.deleteLater()
            self.flow.insert_widget(index, widget)
        else:
            self.flow.addWidget(widget)
        self.widgets[card.id] = widget
        self._update_placeholder()
        return widget

    def update_value(self, card: Card) -> None:
        widget = self.widgets.get(card.id)
        if widget is not None:
            widget.update_card(card)

    def set_live(self, live: bool) -> None:
        self._live = live
        for widget in self.widgets.values():
            widget.set_live(live)

    def _update_placeholder(self) -> None:
        self.placeholder.setVisible(not self.widgets)
