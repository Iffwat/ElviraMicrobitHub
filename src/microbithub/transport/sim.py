"""Simulated micro:bit robot.

Behaves like the phase-3 firmware (protocol v2, watchdog, E-stop, limits) so
the core and the GUI can be developed and tested without hardware.
"""

from __future__ import annotations

import asyncio
import math

from ..core.model import Card, CardType
from ..core.protocol import (
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
from .base import Transport

#: Card types the simulated firmware streams to the PC when they change.
_STREAMED = frozenset(
    {
        CardType.ANALOG_IN,
        CardType.DIGITAL_IN,
        CardType.GAUGE,
        CardType.SENSOR_BUILTIN,
        CardType.TEXT_IN,
    }
)
_DEADBAND_TYPES = frozenset({CardType.ANALOG_IN, CardType.GAUGE})


def demo_cards() -> list[Card]:
    """A typical Motion:bit robot setup."""
    return [
        Card("M1", CardType.MOTOR, 0, label="Left wheel"),
        Card("M2", CardType.MOTOR, 0, label="Right wheel"),
        Card("S1", CardType.SERVO, 90, min=20, max=160, label="Gripper"),
        Card("A1", CardType.ANALOG_IN, 0, label="Light sensor"),
        Card("D1", CardType.DIGITAL_IN, 0, label="Bumper"),
        Card("D2", CardType.DIGITAL_OUT, 0, label="Headlight"),
        Card("T1", CardType.TEXT_IN, "", label="Status"),
        Card("T2", CardType.TEXT_OUT, "", label="Message"),
        Card("B1", CardType.SOUND, "", label="Alarm"),
    ]


class SimTransport(Transport):
    """A fake micro:bit that speaks protocol v2.

    Args:
        cards: cards the robot declares (default: :func:`demo_cards`).
        latency: one-way delay in seconds applied to every line.
        watchdog_timeout: stop motors if no heartbeat for this long (None = off).
        stream_rate: sensor update rate in Hz.
        analog_deadband: analog changes smaller than this are not sent.
        animate: generate moving sensor values. Set False in tests and use
            :meth:`set_sensor` instead.
    """

    def __init__(
        self,
        cards: list[Card] | None = None,
        *,
        latency: float = 0.0,
        watchdog_timeout: float | None = 1.0,
        stream_rate: float = 20.0,
        analog_deadband: int = 5,
        animate: bool = True,
        name: str = "MicrobitHub-Sim",
        firmware: str = "sim-0.1.0",
    ) -> None:
        super().__init__()
        self.cards: dict[str, Card] = {
            c.id: c for c in (cards if cards is not None else demo_cards())
        }
        self.latency = latency
        self.watchdog_timeout = watchdog_timeout
        self.stream_rate = stream_rate
        self.analog_deadband = analog_deadband
        self.animate = animate
        self.name = name
        self.firmware = firmware

        #: Number of upcoming PC->micro:bit lines to drop (to test retries).
        self.drop_incoming = 0
        #: Every line received from the PC, for inspection in tests.
        self.received: list[str] = []
        self.estopped = False

        self._connected = False
        self._synced = False
        self._tasks: list[asyncio.Task] = []
        self._inbox: asyncio.Queue[tuple[float, str]] | None = None
        self._outbox: asyncio.Queue[tuple[float, str]] | None = None
        self._last_hb: float | None = None
        self._wd_tripped = False
        self._reported: dict[str, object] = {}
        self._prev_trigger = 0

    # ---------------------------------------------------------------- Transport

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        if self._connected:
            return
        self._inbox = asyncio.Queue()
        self._outbox = asyncio.Queue()
        self._synced = False
        self._last_hb = None
        self._wd_tripped = False
        self._reported.clear()
        self._tasks = [
            asyncio.create_task(self._rx_loop(), name="sim-rx"),
            asyncio.create_task(self._tx_loop(), name="sim-tx"),
            asyncio.create_task(self._stream_loop(), name="sim-stream"),
        ]
        self._connected = True

    async def disconnect(self) -> None:
        if not self._connected:
            return
        tasks = self._stop_tasks()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def send_line(self, line: str) -> None:
        if not self._connected or self._inbox is None:
            raise ConnectionError("simulator is not connected")
        self.received.append(line)
        if self.drop_incoming > 0:
            self.drop_incoming -= 1
            return
        self._inbox.put_nowait((self._now() + self.latency, line))

    # ------------------------------------------------------------ test helpers

    def set_sensor(self, card_id: str, value: object) -> None:
        """Change a sensor value; it is streamed to the PC on the next tick."""
        card = self.cards[card_id]
        card.value = card.clamp(card.coerce(value))

    def simulate_disconnect(self) -> None:
        """Pretend the radio link dropped (calls the disconnect handler)."""
        if self._connected:
            self._stop_tasks()
            self._emit_disconnect()

    # ---------------------------------------------------------------- internals

    def _stop_tasks(self) -> list[asyncio.Task]:
        tasks, self._tasks = self._tasks, []
        for t in tasks:
            t.cancel()
        self._connected = False
        return tasks

    @staticmethod
    def _now() -> float:
        return asyncio.get_running_loop().time()

    async def _sleep_until(self, due: float) -> None:
        delay = due - self._now()
        if delay > 0:
            await asyncio.sleep(delay)

    def _reply(self, msg: Message) -> None:
        if self._outbox is not None:
            self._outbox.put_nowait((self._now() + self.latency, encode(msg)))

    async def _rx_loop(self) -> None:
        assert self._inbox is not None
        while True:
            due, line = await self._inbox.get()
            await self._sleep_until(due)
            self._handle(line)

    async def _tx_loop(self) -> None:
        assert self._outbox is not None
        while True:
            due, line = await self._outbox.get()
            await self._sleep_until(due)
            self._emit_line(line)

    def _handle(self, line: str) -> None:
        try:
            msg = decode(line)
        except ProtocolError as exc:
            self._reply(Log(f"Rejected line: {exc}"))
            return

        match msg:
            case Hello():
                self._reply(Hello(PROTOCOL_VERSION, self.name, self.firmware))
            case Sync():
                for c in self.cards.values():
                    self._reply(CardDef(c.id, c.type, c.value, c.min, c.max, c.label))
                    self._reported[c.id] = c.value
                self._reply(Synced(len(self.cards)))
                self._synced = True
            case Heartbeat(seq=seq):
                self._last_hb = self._now()
                self._wd_tripped = False
                self._reply(Heartbeat(seq))
            case Set(card_id=cid, value=raw):
                self._apply_set(cid, raw)
            case EStop():
                self.estopped = True
                self._stop_motors()
                self._reply(Event("ESTOP"))
            case Resume():
                self.estopped = False
                self._reply(Event("RESUME"))
            case _:
                self._reply(Log(f"Ignored {type(msg).__name__}"))

    def _apply_set(self, cid: str, raw: object) -> None:
        card = self.cards.get(cid)
        if card is None:
            self._reply(Nak(cid, "UNKNOWN"))
            return
        if not card.is_writable:
            self._reply(Nak(cid, "READ_ONLY"))
            return
        if self.estopped and card.type is CardType.MOTOR:
            self._reply(Nak(cid, "ESTOP"))
            self._reply(Value(cid, card.value))  # correct the PC's optimistic value
            return
        try:
            requested = card.coerce(raw)
        except ValueError:
            self._reply(Nak(cid, "BAD_VALUE"))
            return
        value = card.clamp(requested)
        card.value = value
        self._reported[cid] = value
        self._reply(Ack(cid))
        if value != requested:
            self._reply(Value(cid, value))
        if card.type is CardType.TEXT_OUT:
            self._reply(Log(f"{cid} received text: {value}"))

    def _stop_motors(self) -> None:
        for c in self.cards.values():
            if c.type is CardType.MOTOR and c.value != 0:
                c.value = 0
                self._reported[c.id] = 0
                self._reply(Value(c.id, 0))

    async def _stream_loop(self) -> None:
        t0 = self._now()
        period = 1.0 / self.stream_rate
        while True:
            now = self._now()
            if (
                self.watchdog_timeout is not None
                and self._last_hb is not None
                and not self._wd_tripped
                and now - self._last_hb > self.watchdog_timeout
            ):
                self._wd_tripped = True
                self._stop_motors()
                self._reply(Event("WATCHDOG"))
            if self._synced:
                if self.animate:
                    self._animate(now - t0)
                self._report_changes()
            await asyncio.sleep(period)

    def _animate(self, t: float) -> None:
        first_digital: Card | None = None
        for i, c in enumerate(self.cards.values()):
            if c.type in _DEADBAND_TYPES:
                c.value = c.clamp(int(512 + 400 * math.sin(2 * math.pi * t / 4 + i)))
            elif c.type is CardType.DIGITAL_IN:
                c.value = int(t // 1.5) % 2
                first_digital = first_digital or c
            elif c.type is CardType.SENSOR_BUILTIN:
                c.value = int(round(24 + 3 * math.sin(t / 5)))
            elif c.type is CardType.TEXT_IN:
                c.value = f"uptime {int(t)}s"

        # A rising edge on the first digital input triggers the first sound card.
        if first_digital is not None:
            level = int(first_digital.value)
            if level and not self._prev_trigger:
                sound = next((c for c in self.cards.values() if c.type is CardType.SOUND), None)
                if sound is not None:
                    self._reply(Value(sound.id, "PLAY:CHIME:ONCE"))
            self._prev_trigger = level

    def _report_changes(self) -> None:
        for c in self.cards.values():
            if c.type not in _STREAMED:
                continue
            last = self._reported.get(c.id)
            if c.type in _DEADBAND_TYPES and isinstance(last, int) and isinstance(c.value, int):
                changed = abs(c.value - last) > self.analog_deadband
            else:
                changed = c.value != last
            if changed:
                self._reported[c.id] = c.value
                self._reply(Value(c.id, c.value))
