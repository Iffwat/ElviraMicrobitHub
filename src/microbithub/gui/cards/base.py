"""Base class shared by all card widgets."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtWidgets import QGroupBox, QSizePolicy, QWidget

from ...core.model import Card, Scalar

#: Default card size in pixels. Wide cards (charts) use two columns.
CARD_WIDTH = 230
CARD_HEIGHT = 150
WIDE_CARD_WIDTH = CARD_WIDTH * 2 + 10

#: Minimum time between two streamed values while a slider is dragged.
STREAM_INTERVAL_MS = 50


class CardWidget(QGroupBox):
    """One dashboard card.

    Subclasses build their controls in ``__init__`` and implement
    :meth:`show_value`. Controls that send values to the micro:bit go in
    :attr:`inputs`, so they can be disabled while disconnected.

    Sending:
        * :meth:`commit` sends a final value and waits for the device's ACK.
        * :meth:`stream` sends quickly without an ACK (slider drags). It is
          throttled to one line per ``STREAM_INTERVAL_MS``, and the most recent
          value is always sent.

    While the user is interacting (:attr:`user_active`), values coming back
    from the device are not shown, so a slider does not jump under the mouse.
    The latest one is applied when the interaction ends.
    """

    #: card_id, value, wait_ack
    valueRequested = QtSignal(str, object, bool)

    wide = False

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card = card
        self.card_id = card.id
        self.inputs: list[QWidget] = []
        self.user_active = False
        self._deferred: Card | None = None
        self._pending: Scalar | None = None

        self._throttle = QTimer(self)
        self._throttle.setSingleShot(True)
        self._throttle.setInterval(STREAM_INTERVAL_MS)
        self._throttle.timeout.connect(self._on_throttle)

        self.setObjectName(f"card_{card.id}")
        self.setTitle(self.title_text(card))
        self.setToolTip(f"{card.id} · {card.type.value}")
        self.setFixedSize(WIDE_CARD_WIDTH if self.wide else CARD_WIDTH, CARD_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    # ---------------------------------------------------------------- display

    @staticmethod
    def title_text(card: Card) -> str:
        return f"{card.label} ({card.id})" if card.label else card.id

    def update_card(self, card: Card) -> None:
        """Called by the grid when the device reports a new value."""
        self.card = card
        if self.user_active:
            self._deferred = card
        else:
            self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        raise NotImplementedError

    def set_live(self, live: bool) -> None:
        """Enable or disable the controls (disabled while disconnected)."""
        for widget in self.inputs:
            widget.setEnabled(live)
        if not live:
            self._throttle.stop()
            self._pending = None
            self.end_interaction()

    # ---------------------------------------------------------------- sending

    def begin_interaction(self) -> None:
        self.user_active = True

    def end_interaction(self) -> None:
        self.user_active = False
        if self._deferred is not None:
            card, self._deferred = self._deferred, None
            self.show_value(card.value)

    def commit(self, value: Scalar) -> None:
        self._pending = None
        self._throttle.stop()
        self.valueRequested.emit(self.card_id, value, True)

    def stream(self, value: Scalar) -> None:
        self._pending = value
        if not self._throttle.isActive():
            self._flush()

    def _flush(self) -> None:
        value, self._pending = self._pending, None
        if value is not None:
            self.valueRequested.emit(self.card_id, value, False)
            self._throttle.start()

    def _on_throttle(self) -> None:
        self._flush()
