"""Bridge from the core's plain-Python ``Signal`` objects to Qt signals.

The core (``DeviceSession``) must not import Qt, so it uses
:class:`microbithub.core.events.Signal`. The GUI connects to this bridge
instead, which re-emits every core signal as a Qt signal.

With qasync the asyncio loop runs on the Qt main thread, so today the
connections are direct calls. If a transport ever emits from another thread,
Qt queues the signal to the receiver's thread automatically, so widgets are
still only touched from the GUI thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtCore import Signal as QtSignal

from ..core.session import DeviceSession

#: (core signal attribute, Qt signal attribute)
_PAIRS = (
    ("state_changed", "stateChanged"),
    ("cards_cleared", "cardsCleared"),
    ("card_added", "cardAdded"),
    ("value_changed", "valueChanged"),
    ("log_received", "logReceived"),
    ("event_received", "eventReceived"),
    ("latency_updated", "latencyUpdated"),
    ("link_lost", "linkLost"),
    ("link_restored", "linkRestored"),
    ("error", "error"),
)


class SessionBridge(QObject):
    """Re-emits the signals of one :class:`DeviceSession` as Qt signals."""

    stateChanged = QtSignal(object)  # SessionState
    cardsCleared = QtSignal()
    cardAdded = QtSignal(object)  # Card
    valueChanged = QtSignal(object)  # Card
    logReceived = QtSignal(str)
    eventReceived = QtSignal(str)
    latencyUpdated = QtSignal(float)
    linkLost = QtSignal()
    linkRestored = QtSignal()
    error = QtSignal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.session: DeviceSession | None = None
        self._links: list[tuple[object, object]] = []

    def attach(self, session: DeviceSession) -> None:
        """Forward ``session``'s signals (detaching any previous session)."""
        self.detach()
        self.session = session
        for core_name, qt_name in _PAIRS:
            core_signal = getattr(session, core_name)
            slot = getattr(self, qt_name).emit
            core_signal.connect(slot)
            self._links.append((core_signal, slot))

    def detach(self) -> None:
        for core_signal, slot in self._links:
            core_signal.disconnect(slot)
        self._links.clear()
        self.session = None
