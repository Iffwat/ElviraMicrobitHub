"""MicrobitHub protocol v2.

Line format (``\\n`` is added/removed by the transport)::

    <TYPE>[:<payload>][*<checksum>]

* ``checksum`` is the XOR of all UTF-8 bytes before ``*``, as 2 hex digits.
  It is optional on receive; the PC always adds it to actuator commands.
* Free-text fields (text values, labels, log text, NAK reasons, event names)
  are escaped so they never contain ``*``, ``,`` or line breaks:
  ``%`` -> ``%25``, ``*`` -> ``%2A``, ``,`` -> ``%2C``, ``\\n`` -> ``%0A``, ``\\r`` -> ``%0D``.

See docs/phases/phase-1-core-simulator.md for the full message table.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Union

from .model import CardType, Scalar

PROTOCOL_VERSION = 2


class ProtocolError(ValueError):
    """Raised when a line cannot be encoded or decoded."""


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_ESCAPES = {"%": "%25", "*": "%2A", ",": "%2C", "\n": "%0A", "\r": "%0D"}
_UNESCAPE_RE = re.compile(r"%(25|2A|2C|0A|0D)", re.IGNORECASE)
_CHECKSUM_RE = re.compile(r"\*([0-9A-Fa-f]{2})$")
_INT_RE = re.compile(r"[+-]?\d+")
_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,15}")


def escape(text: str) -> str:
    return "".join(_ESCAPES.get(ch, ch) for ch in text)


def unescape(text: str) -> str:
    return _UNESCAPE_RE.sub(lambda m: chr(int(m.group(1), 16)), text)


def checksum(body: str) -> str:
    x = 0
    for b in body.encode("utf-8"):
        x ^= b
    return f"{x:02X}"


def _check_id(card_id: str) -> str:
    if not isinstance(card_id, str) or not _ID_RE.fullmatch(card_id):
        raise ProtocolError(f"invalid card id {card_id!r}")
    return card_id


def _fmt_scalar(value: Scalar | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(int(value))
    if isinstance(value, int):
        return str(value)
    return escape(str(value))


def _parse_scalar(raw: str) -> Scalar:
    """Integers become ``int``; everything else is unescaped text."""
    if _INT_RE.fullmatch(raw):
        return int(raw)
    return unescape(raw)


def _parse_int(raw: str, what: str) -> int:
    try:
        return int(raw)
    except ValueError as exc:
        raise ProtocolError(f"{what}: {raw!r} is not an integer") from exc


def _parse_int_opt(raw: str, what: str) -> int | None:
    return None if raw == "" else _parse_int(raw, what)


# --------------------------------------------------------------------------
# Messages
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Hello:
    """Handshake. PC sends ``HELLO:2``; micro:bit replies ``HELLO:2,<name>,<fw>``."""

    version: int = PROTOCOL_VERSION
    name: str | None = None
    firmware: str | None = None


@dataclass(frozen=True)
class Sync:
    """PC -> micro:bit: send all card definitions."""


@dataclass(frozen=True)
class Synced:
    """micro:bit -> PC: all ``count`` cards have been sent."""

    count: int


@dataclass(frozen=True)
class Heartbeat:
    """``HB:<seq>``. PC sends it periodically; micro:bit echoes it back."""

    seq: int


@dataclass(frozen=True)
class Set:
    """PC -> micro:bit: set a card value."""

    card_id: str
    value: Scalar


@dataclass(frozen=True)
class EStop:
    """PC -> micro:bit: stop all motors until ``RESUME``."""


@dataclass(frozen=True)
class Resume:
    """PC -> micro:bit: clear the emergency stop."""


@dataclass(frozen=True)
class CardDef:
    """micro:bit -> PC: ``CARD:<id>,<TYPE>,<start>,<min>,<max>,<label>``."""

    card_id: str
    type: CardType
    start: Scalar | None = None
    min: int | None = None
    max: int | None = None
    label: str = ""


@dataclass(frozen=True)
class Value:
    """micro:bit -> PC: ``VAL:<id>:<value>``."""

    card_id: str
    value: Scalar


@dataclass(frozen=True)
class Ack:
    card_id: str


@dataclass(frozen=True)
class Nak:
    card_id: str
    reason: str = ""


@dataclass(frozen=True)
class Log:
    text: str


@dataclass(frozen=True)
class Event:
    """micro:bit -> PC events, e.g. ``ESTOP``, ``RESUME``, ``WATCHDOG``."""

    name: str


Message = Union[
    Hello, Sync, Synced, Heartbeat, Set, EStop, Resume, CardDef, Value, Ack, Nak, Log, Event
]

#: Messages that get a checksum by default when encoded.
CHECKSUM_BY_DEFAULT = (Set, EStop, Resume)


# --------------------------------------------------------------------------
# Encode / decode
# --------------------------------------------------------------------------


def _body(msg: Message) -> str:
    match msg:
        case Hello(version=v, name=None, firmware=None):
            return f"HELLO:{v}"
        case Hello(version=v, name=n, firmware=f):
            return f"HELLO:{v},{escape(n or '')},{escape(f or '')}"
        case Sync():
            return "SYNC"
        case Synced(count=c):
            return f"SYNCED:{c}"
        case Heartbeat(seq=s):
            return f"HB:{s}"
        case Set(card_id=cid, value=v):
            return f"SET:{_check_id(cid)}:{_fmt_scalar(v)}"
        case EStop():
            return "ESTOP"
        case Resume():
            return "RESUME"
        case CardDef(card_id=cid, type=t, start=s, min=lo, max=hi, label=lbl):
            fields = [
                _check_id(cid),
                CardType(t).value,
                _fmt_scalar(s),
                "" if lo is None else str(lo),
                "" if hi is None else str(hi),
                escape(lbl),
            ]
            return "CARD:" + ",".join(fields)
        case Value(card_id=cid, value=v):
            return f"VAL:{_check_id(cid)}:{_fmt_scalar(v)}"
        case Ack(card_id=cid):
            return f"ACK:{_check_id(cid)}"
        case Nak(card_id=cid, reason=r):
            return f"NAK:{_check_id(cid)},{escape(r)}"
        case Log(text=t):
            return f"LOG:{escape(t)}"
        case Event(name=n):
            return f"EVT:{escape(n)}"
    raise ProtocolError(f"cannot encode {msg!r}")


def encode(msg: Message, with_checksum: bool | None = None) -> str:
    """Encode a message to a line (without the trailing newline)."""
    body = _body(msg)
    use = isinstance(msg, CHECKSUM_BY_DEFAULT) if with_checksum is None else with_checksum
    return f"{body}*{checksum(body)}" if use else body


def decode(line: str) -> Message:
    """Decode one line. Raises ``ProtocolError`` on bad input or a wrong checksum."""
    line = line.rstrip("\r\n")
    if not line:
        raise ProtocolError("empty line")

    m = _CHECKSUM_RE.search(line)
    if m:
        body = line[: m.start()]
        if checksum(body) != m.group(1).upper():
            raise ProtocolError(f"checksum mismatch in {line!r}")
    else:
        body = line

    tag, _, payload = body.partition(":")
    tag = tag.strip().upper()

    match tag:
        case "HELLO":
            parts = payload.split(",", 2)
            version = _parse_int(parts[0], "HELLO version")
            name = unescape(parts[1]) if len(parts) > 1 and parts[1] else None
            fw = unescape(parts[2]) if len(parts) > 2 and parts[2] else None
            return Hello(version, name, fw)
        case "SYNC":
            return Sync()
        case "SYNCED":
            return Synced(_parse_int(payload, "SYNCED count"))
        case "HB":
            return Heartbeat(_parse_int(payload, "HB seq"))
        case "SET" | "VAL":
            cid, sep, raw = payload.partition(":")
            if not sep:
                raise ProtocolError(f"{tag} needs '<id>:<value>', got {payload!r}")
            cls = Set if tag == "SET" else Value
            return cls(_check_id(cid), _parse_scalar(raw))
        case "ESTOP":
            return EStop()
        case "RESUME":
            return Resume()
        case "CARD":
            parts = payload.split(",", 5)
            if len(parts) < 2:
                raise ProtocolError(f"CARD needs at least '<id>,<TYPE>', got {payload!r}")
            parts += [""] * (6 - len(parts))
            try:
                ctype = CardType(parts[1].strip().upper())
            except ValueError as exc:
                raise ProtocolError(f"unknown card type {parts[1]!r}") from exc
            label = parts[5]
            if len(label) >= 2 and label[0] == label[-1] == '"':
                label = label[1:-1]
            return CardDef(
                card_id=_check_id(parts[0]),
                type=ctype,
                start=None if parts[2] == "" else _parse_scalar(parts[2]),
                min=_parse_int_opt(parts[3], "CARD min"),
                max=_parse_int_opt(parts[4], "CARD max"),
                label=unescape(label),
            )
        case "ACK":
            return Ack(_check_id(payload))
        case "NAK":
            cid, _, reason = payload.partition(",")
            return Nak(_check_id(cid), unescape(reason))
        case "LOG":
            return Log(unescape(payload))
        case "EVT":
            return Event(unescape(payload))
    raise ProtocolError(f"unknown message type {tag!r}")
