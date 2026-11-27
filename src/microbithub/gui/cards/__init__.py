"""Card widgets, one per card type, and the factory that picks the right one."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from ...core.model import Card, CardType
from .analog import AnalogInCard, GaugeCard
from .base import CardWidget
from .digital import ButtonCard, DigitalInCard, DigitalOutCard
from .slider import AnalogOutCard, MotorCard, ServoCard
from .sound import SoundCard
from .text import GenericCard, TextInCard, TextOutCard

CARD_CLASSES: dict[CardType, type[CardWidget]] = {
    CardType.MOTOR: MotorCard,
    CardType.SERVO: ServoCard,
    CardType.ANALOG_IN: AnalogInCard,
    CardType.ANALOG_OUT: AnalogOutCard,
    CardType.GAUGE: GaugeCard,
    CardType.SENSOR_BUILTIN: AnalogInCard,
    CardType.DIGITAL_IN: DigitalInCard,
    CardType.DIGITAL_OUT: DigitalOutCard,
    CardType.BUTTON: ButtonCard,
    CardType.TEXT_IN: TextInCard,
    CardType.TEXT_OUT: TextOutCard,
    CardType.SOUND: SoundCard,
    # JOYSTICK gets its drag pad in phase 6 (keyboard / gamepad drive).
}


def create_card_widget(card: Card, parent: QWidget | None = None) -> CardWidget:
    return CARD_CLASSES.get(card.type, GenericCard)(card, parent)


__all__ = ["CARD_CLASSES", "CardWidget", "create_card_widget"]
