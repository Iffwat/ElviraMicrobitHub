"""DeviceSession: talks to one micro:bit over any Transport.

Responsibilities:
* handshake (``HELLO``) and card discovery (``SYNC`` ... ``SYNCED``)
* keeping the card state up to date from ``VAL`` messages
* sending values with optional ACK + retry
* heartbeat (keeps the micro:bit watchdog happy) and latency measurement
* detecting a silent link
"""

from __future__ import annotations

import asyncio
import logging
from enum import StrEnum

from ..transport.base import Transport
from .events import Signal
from .model import Card, Scalar
from .protocol import (
    PROTOCOL_VERSION,
    Ack,
    CardDef,
    EStop,
    Event,
    Heartbeat,
    Hello,
    Log,
    Message,
    Nak,
    ProtocolError,
    Resume,
    Set,
    Sync,
    Synced,
    Value,
    decode,
    encode,
)

log = logging.getLogger(__name__)


class SessionState(StrEnum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    HANDSHAKE = "handshake"
    SYNCING = "syncing"
    READY = "ready"


class SessionError(Exception):
    """Connection, handshake or state error."""


class DeviceSession:
    """High-level connection to one micro:bit.

    Signals (all plain-Python, see :mod:`microbithub.core.events`):

    ========================  ===========================================
    ``state_changed(state)``  :class:`SessionState` changed
    ``cards_cleared()``       card list is being rebuilt (new sync)
    ``card_added(card)``      a card was declared (or re-declared)
    ``value_changed(card)``   a card value changed
    ``log_received(text)``    ``LOG:`` line from the micro:bit
    ``event_received(name)``  ``EVT:`` line (ESTOP, RESUME, WATCHDOG ...)
    ``latency_updated(ms)``   heartbeat round-trip time
    ``link_lost()``           nothing received for ``link_timeout`` s
    ``link_restored()``       data arrives again after ``link_lost``
    ``error(text)``           protocol errors, NAKs, missing ACKs
    ========================  ===========================================
    """

    def __init__(
        self,
        transport: Transport,
        *,
        heartbeat_interval: float | None = 0.25,
        handshake_timeout: float = 3.0,
        sync_timeout: float = 5.0,
        ack_timeout: float = 0.3,
        ack_retries: int = 2,
        link_timeout: float = 1.5,
    ) -> None:
        self.transport = transport
        self.heartbeat_interval = heartbeat_interval
        self.handshake_timeout = handshake_timeout
        self.sync_timeout = sync_timeout
        self.ack_timeout = ack_timeout
        self.ack_retries = ack_retries
        self.link_timeout = link_timeout

        self.cards: dict[str, Card] = {}
        self.device_info: Hello | None = None
        self.state = SessionState.DISCONNECTED
        self.estopped = False
        self.latency_ms: float | None = None

        self.state_changed = Signal()
        self.cards_cleared = Signal()
        self.card_added = Signal()
        self.value_changed = Signal()
        self.log_received = Signal()
        self.event_received = Signal()
        self.latency_updated = Signal()
        self.link_lost = Signal()
        self.link_restored = Signal()
        self.error = Signal()

        self._hello_fut: asyncio.Future[Hello] | None = None
        self._synced_fut: asyncio.Future[int] | None = None
        self._pending: dict[str, asyncio.Future[bool]] = {}
        self._hb_task: asyncio.Task | None = None
        self._hb_seq = 0
        self._hb_sent: dict[int, float] = {}
        self._last_rx = 0.0
        self._link_ok = True

        transport.set_handlers(self._on_line, self._on_transport_disconnect)

    # ------------------------------------------------------------------ public

    @property
    def is_ready(self) -> bool:
        return self.state is SessionState.READY

    async def connect(self) -> None:
        """Connect, handshake and download the card list."""
        if self.state is not SessionState.DISCONNECTED:
            raise SessionError(f"cannot connect while {self.state.value}")
        loop = asyncio.get_running_loop()
        self._set_state(SessionState.CONNECTING)
        try:
            await self.transport.connect()

            self._set_state(SessionState.HANDSHAKE)
            self._hello_fut = loop.create_future()
            await self._send(Hello())
            try:
                hello = await asyncio.wait_for(self._hello_fut, self.handshake_timeout)
            except TimeoutError as exc:
                raise SessionError("no HELLO reply (is the MicrobitHub firmware running?)") from exc
            if hello.version != PROTOCOL_VERSION:
                raise SessionError(
                    f"protocol mismatch: device v{hello.version}, app v{PROTOCOL_VERSION}"
                )
            self.device_info = hello

            self._set_state(SessionState.SYNCING)
            self.cards.clear()
            self.cards_cleared.emit()
            self._synced_fut = loop.create_future()
            await self._send(Sync())
            try:
                await asyncio.wait_for(self._synced_fut, self.sync_timeout)
            except TimeoutError as exc:
                raise SessionError("card sync timed out") from exc
        except BaseException:
            await self._teardown()
            raise

        self._last_rx = loop.time()
        self._link_ok = True
        if self.heartbeat_interval:
            self._hb_task = asyncio.create_task(self._heartbeat_loop(), name="session-heartbeat")
        self._set_state(SessionState.READY)

    async def disconnect(self) -> None:
        if self.state is not SessionState.DISCONNECTED:
            await self._teardown()

    async def set_value(self, card_id: str, value: object, *, wait_ack: bool = True) -> bool:
        """Send a new value for a writable card.

        The local value is updated immediately (clamped to the card limits).
        With ``wait_ack`` the call waits for ``ACK`` and retries on timeout.

        Returns True when acknowledged (or sent, if ``wait_ack`` is False).
        Returns False on NAK, on timeout after all retries, or if a newer
        value for the same card replaced this one before it was acknowledged.

        Raises ``KeyError`` for an unknown card, ``ValueError`` for a
        read-only card or bad value, and ``SessionError`` if not connected.
        """
        card = self.cards[card_id]
        if not card.is_writable:
            raise ValueError(f"card {card_id} ({card.type.value}) is read-only")
        if not self.is_ready:
            raise SessionError("not connected")

        v = card.clamp(card.coerce(value))
        line = encode(Set(card_id, v))
        self._update_value(card, v, force=False)

        if not wait_ack:
            await self.transport.send_line(line)
            return True

        fut: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        old = self._pending.get(card_id)
        if old is not None and not old.done():
            old.set_result(False)  # superseded
        self._pending[card_id] = fut
        try:
            for _attempt in range(1 + self.ack_retries):
                await self.transport.send_line(line)
                try:
                    return await asyncio.wait_for(asyncio.shield(fut), self.ack_timeout)
                except TimeoutError:
                    if fut.done():
                        return fut.result()
            self.error.emit(f"No ACK for {card_id} after {1 + self.ack_retries} attempts")
            return False
        finally:
            if self._pending.get(card_id) is fut:
                del self._pending[card_id]

    async def estop(self) -> None:
        """Emergency stop: the micro:bit stops all motors until :meth:`resume`."""
        await self._send(EStop())

    async def resume(self) -> None:
        await self._send(Resume())

    # ---------------------------------------------------------------- internals

    def _set_state(self, state: SessionState) -> None:
        if state is not self.state:
            self.state = state
            self.state_changed.emit(state)

    async def _send(self, msg: Message) -> None:
        await self.transport.send_line(encode(msg))

    def _update_value(self, card: Card, value: Scalar, *, force: bool) -> None:
        if force or card.value != value:
            card.value = value
            self.value_changed.emit(card)

    def _cleanup(self) -> None:
        """Cancel tasks and resolve every pending future (synchronous)."""
        if self._hb_task is not None:
            self._hb_task.cancel()
            self._hb_task = None
        for fut in self._pending.values():
            if not fut.done():
                fut.set_result(False)
        self._pending.clear()
        for fut in (self._hello_fut, self._synced_fut):
            if fut is not None and not fut.done():
                fut.set_exception(SessionError("connection lost"))
                fut.exception()  # mark retrieved to avoid "never retrieved" warnings
        self._hello_fut = self._synced_fut = None
        self._hb_sent.clear()
        self.estopped = False
        self._set_state(SessionState.DISCONNECTED)

    async def _teardown(self) -> None:
        self._cleanup()
        if self.transport.is_connected:
            try:
                await self.transport.disconnect()
            except Exception:  # noqa: BLE001
                log.exception("transport disconnect failed")

    def _on_transport_disconnect(self) -> None:
        if self.state is not SessionState.DISCONNECTED:
            self._cleanup()
            self.error.emit("Connection lost")

    async def _heartbeat_loop(self) -> None:
        loop = asyncio.get_running_loop()
        assert self.heartbeat_interval
        while True:
            self._hb_seq = (self._hb_seq + 1) % 100_000
            now = loop.time()
            self._hb_sent[self._hb_seq] = now
            while len(self._hb_sent) > 32:
                self._hb_sent.pop(next(iter(self._hb_sent)))
            try:
                await self._send(Heartbeat(self._hb_seq))
            except Exception as exc:  # noqa: BLE001
                self.error.emit(f"Heartbeat send failed: {exc}")
            if self._link_ok and now - self._last_rx > self.link_timeout:
                self._link_ok = False
                self.link_lost.emit()
            await asyncio.sleep(self.heartbeat_interval)

    def _on_line(self, line: str) -> None:
        now = asyncio.get_running_loop().time()
        self._last_rx = now
        if not self._link_ok:
            self._link_ok = True
            self.link_restored.emit()

        try:
            msg = decode(line)
        except ProtocolError as exc:
            self.error.emit(f"Bad line {line!r}: {exc}")
            return

        match msg:
            case Hello():
                if self._hello_fut is not None and not self._hello_fut.done():
                    self._hello_fut.set_result(msg)
                else:
                    self.device_info = msg
            case CardDef():
                try:
                    card = Card(msg.card_id, msg.type, msg.start, msg.min, msg.max, msg.label)
                except ValueError as exc:
                    self.error.emit(f"Bad card definition {line!r}: {exc}")
                    return
                self.cards[card.id] = card
                self.card_added.emit(card)
            case Synced(count=count):
                if count != len(self.cards):
                    self.error.emit(f"Sync expected {count} cards, got {len(self.cards)}")
                if self._synced_fut is not None and not self._synced_fut.done():
                    self._synced_fut.set_result(count)
            case Value(card_id=cid, value=raw):
                card = self.cards.get(cid)
                if card is None:
                    log.debug("value for unknown card %s ignored", cid)
                    return
                try:
                    v = card.coerce(raw)
                except ValueError as exc:
                    self.error.emit(str(exc))
                    return
                self._update_value(card, v, force=True)
            case Ack(card_id=cid):
                fut = self._pending.get(cid)
                if fut is not None and not fut.done():
                    fut.set_result(True)
            case Nak(card_id=cid, reason=reason):
                fut = self._pending.get(cid)
                if fut is not None and not fut.done():
                    fut.set_result(False)
                self.error.emit(f"{cid} rejected: {reason or 'no reason'}")
            case Heartbeat(seq=seq):
                sent = self._hb_sent.pop(seq, None)
                if sent is not None:
                    self.latency_ms = (now - sent) * 1000.0
                    self.latency_updated.emit(self.latency_ms)
            case Log(text=text):
                self.log_received.emit(text)
            case Event(name=name):
                if name == "ESTOP":
                    self.estopped = True
                elif name == "RESUME":
                    self.estopped = False
                self.event_received.emit(name)
            case _:
                self.error.emit(f"Unexpected message from device: {line!r}")
