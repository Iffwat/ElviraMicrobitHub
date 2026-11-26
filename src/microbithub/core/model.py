"""State model: card types and cards."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

Scalar = int | str


class CardType(StrEnum):
    MOTOR = "MOTOR"
    SERVO = "SERVO"
    ANALOG_IN = "ANALOG_IN"
    ANALOG_OUT = "ANALOG_OUT"
    DIGITAL_IN = "DIGITAL_IN"
    DIGITAL_OUT = "DIGITAL_OUT"
    BUTTON = "BUTTON"  # momentary digital output (held = 1, released = 0)
    TEXT_IN = "TEXT_IN"  # micro:bit -> PC text
    TEXT_OUT = "TEXT_OUT"  # PC -> micro:bit text
    SOUND = "SOUND"  # micro:bit asks the PC to play a sound, e.g. "PLAY:SIREN:LOOP"
    GAUGE = "GAUGE"  # numeric reading shown as a gauge
    JOYSTICK = "JOYSTICK"  # 2-axis drive, text value "x,y" (each -100..100)
    SENSOR_BUILTIN = "SENSOR_BUILTIN"  # accelerometer, compass, temperature, light


#: Cards whose value is text rather than an integer.
TEXT_TYPES = frozenset({CardType.TEXT_IN, CardType.TEXT_OUT, CardType.SOUND, CardType.JOYSTICK})

#: Cards the PC is allowed to write to.
WRITABLE_TYPES = frozenset(
    {
        CardType.MOTOR,
        CardType.SERVO,
        CardType.ANALOG_OUT,
        CardType.DIGITAL_OUT,
        CardType.BUTTON,
        CardType.TEXT_OUT,
        CardType.JOYSTICK,
    }
)

#: Default (min, max) used when the micro:bit does not send limits.
DEFAULT_RANGES: dict[CardType, tuple[int, int]] = {
    CardType.MOTOR: (-255, 255),
    CardType.SERVO: (0, 180),
    CardType.ANALOG_IN: (0, 1023),
    CardType.ANALOG_OUT: (0, 1023),
    CardType.DIGITAL_IN: (0, 1),
    CardType.DIGITAL_OUT: (0, 1),
    CardType.BUTTON: (0, 1),
    CardType.GAUGE: (0, 1023),
}


@dataclass
class Card:
    """One dashboard item declared by the micro:bit."""

    id: str
    type: CardType
    value: Scalar | None = None
    min: int | None = None
    max: int | None = None
    label: str = ""

    def __post_init__(self) -> None:
        self.type = CardType(self.type)
        if not self.is_text:
            lo, hi = DEFAULT_RANGES.get(self.type, (None, None))
            if self.min is None:
                self.min = lo
            if self.max is None:
                self.max = hi
            if self.min is not None and self.max is not None and self.min > self.max:
                self.min, self.max = self.max, self.min
        if self.value is None:
            self.value = "" if self.is_text else 0
        self.value = self.clamp(self.coerce(self.value))

    @property
    def is_text(self) -> bool:
        return self.type in TEXT_TYPES

    @property
    def is_writable(self) -> bool:
        return self.type in WRITABLE_TYPES

    def coerce(self, raw: object) -> Scalar:
        """Convert a raw value to this card's value type.

        Raises ``ValueError`` if a numeric card gets a non-numeric value.
        """
        if self.is_text:
            return "" if raw is None else str(raw)
        if isinstance(raw, bool):
            return int(raw)
        if isinstance(raw, int):
            return raw
        try:
            return int(round(float(str(raw).strip())))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"{self.id}: {raw!r} is not a number") from exc

    def clamp(self, value: Scalar) -> Scalar:
        """Limit a numeric value to [min, max]. Text values are returned unchanged."""
        if self.is_text or not isinstance(value, int):
            return value
        if self.min is not None:
            value = max(self.min, value)
        if self.max is not None:
            value = min(self.max, value)
        return value
