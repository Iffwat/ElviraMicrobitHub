import pytest

from microbithub.core.model import Card, CardType


def test_default_ranges_and_value():
    m = Card("M1", CardType.MOTOR)
    assert (m.min, m.max, m.value) == (-255, 255, 0)
    t = Card("T1", CardType.TEXT_IN)
    assert (t.min, t.max, t.value) == (None, None, "")


def test_start_value_is_clamped():
    s = Card("S1", CardType.SERVO, 0, min=20, max=160)
    assert s.value == 20


def test_swapped_limits_are_fixed():
    s = Card("S1", CardType.SERVO, 90, min=160, max=20)
    assert (s.min, s.max) == (20, 160)


def test_coerce():
    m = Card("M1", CardType.MOTOR)
    assert m.coerce("12") == 12
    assert m.coerce("12.6") == 13
    assert m.coerce(True) == 1
    with pytest.raises(ValueError):
        m.coerce("fast")
    assert Card("T1", CardType.TEXT_OUT).coerce(5) == "5"


def test_clamp():
    m = Card("M1", CardType.MOTOR)
    assert m.clamp(999) == 255
    assert m.clamp(-999) == -255
    assert Card("T1", CardType.TEXT_OUT).clamp("x") == "x"


def test_writable():
    assert Card("M1", CardType.MOTOR).is_writable
    assert not Card("A1", CardType.ANALOG_IN).is_writable
