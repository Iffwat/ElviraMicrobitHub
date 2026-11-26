"""Abstract transport and line framing shared by all transports."""

from __future__ import annotations

import codecs
from abc import ABC, abstractmethod
from typing import Callable

LineHandler = Callable[[str], None]
DisconnectHandler = Callable[[], None]


class LineBuffer:
    """Turns a stream of byte chunks into complete lines.

    BLE delivers ~20-byte packets and serial delivers arbitrary chunks, so a
    line (or even one UTF-8 character) can be split across chunks.
    """

    def __init__(self) -> None:
        self._decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        self._buf = ""

    def feed(self, data: bytes | str) -> list[str]:
        self._buf += data if isinstance(data, str) else self._decoder.decode(data)
        *lines, self._buf = self._buf.split("\n")
        return [ln.rstrip("\r") for ln in lines if ln.strip("\r")]

    def clear(self) -> None:
        self._buf = ""
        self._decoder.reset()


class Transport(ABC):
    """A bidirectional line link to a micro:bit.

    * ``send_line`` takes a line *without* the newline; the transport adds it.
    * Received lines are passed (without newline) to the line handler.
    * The disconnect handler is called only for an **unexpected** loss of the
      link, never for a deliberate ``disconnect()``.
    """

    def __init__(self) -> None:
        self._line_handler: LineHandler | None = None
        self._disconnect_handler: DisconnectHandler | None = None

    def set_handlers(
        self, on_line: LineHandler, on_disconnect: DisconnectHandler | None = None
    ) -> None:
        self._line_handler = on_line
        self._disconnect_handler = on_disconnect

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_line(self, line: str) -> None: ...

    def _emit_line(self, line: str) -> None:
        if self._line_handler is not None:
            self._line_handler(line)

    def _emit_disconnect(self) -> None:
        if self._disconnect_handler is not None:
            self._disconnect_handler()
