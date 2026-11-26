"""Minimal pure-Python signal/slot mechanism.

The core layer must not depend on Qt, so it uses this small ``Signal`` class.
The GUI (phase 2) bridges these signals to Qt signals.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

log = logging.getLogger(__name__)

Slot = Callable[..., Any]


class Signal:
    """A list of callbacks that are called when the signal is emitted.

    An exception raised by a slot is logged and does not stop the other slots
    (or the transport task that emitted the signal).
    """

    def __init__(self) -> None:
        self._slots: list[Slot] = []

    def connect(self, slot: Slot) -> Slot:
        if slot not in self._slots:
            self._slots.append(slot)
        return slot

    def disconnect(self, slot: Slot) -> None:
        try:
            self._slots.remove(slot)
        except ValueError:
            pass

    def emit(self, *args: Any) -> None:
        for slot in list(self._slots):
            try:
                slot(*args)
            except Exception:  # noqa: BLE001 - a broken slot must not kill the emitter
                log.exception("Error in slot %r", slot)

    def __len__(self) -> int:
        return len(self._slots)
