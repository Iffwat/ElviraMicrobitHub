import pytest

from microbithub.core.model import CardType
from microbithub.core.protocol import (
    Ack,
    CardDef,
    EStop,
    Event,
    Heartbeat,
    Hello,
    Log,
    Nak,
    ProtocolError,
    Resume,
    Set,
    Sync,
    Synced,
    Value,
    checksum,
    decode,
    encode,
    escape,
    unescape,
)

ROUNDTRIP = [
    Hello(),
    Hello(2, "MicrobitHub", "1.0.0"),
    Sync(),
    Synced(9),
    Heartbeat(42),
    Set("M1", -200),
    Set("S1", 90),
    Set("T2", "hello world"),
    EStop(),
    Resume(),
    CardDef("M1", CardType.MOTOR, 0, -255, 255, "Left wheel"),
    CardDef("T1", CardType.TEXT_IN, None, None, None, "Status"),
    Value("A1", 512),
    Value("B1", "PLAY:CHIME:ONCE"),
    Ack("M1"),
    Nak("M1", "ESTOP"),
    Log("Robot ready"),
    Event("WATCHDOG"),
]


@pytest.mark.parametrize("msg", ROUNDTRIP, ids=lambda m: type(m).__name__)
def test_roundtrip(msg):
    assert decode(encode(msg)) == msg


def test_checksum_values():
    assert checksum("A") == "41"
    assert checksum("AB") == "03"


def test_actuator_commands_have_checksum_by_default():
    for msg in (Set("M1", 10), EStop(), Resume()):
        line = encode(msg)
        body, star, cs = line.rpartition("*")
        assert star and cs == checksum(body)
    assert "*" not in encode(Heartbeat(1))


def test_bad_checksum_rejected():
    line = encode(Set("M1", 100))
    tampered = line.replace("100", "200")
    with pytest.raises(ProtocolError, match="checksum"):
        decode(tampered)


def test_checksum_is_optional_and_case_insensitive():
    assert decode("VAL:A1:5") == Value("A1", 5)
    body = "VAL:A1:5"
    assert decode(f"{body}*{checksum(body).lower()}") == Value("A1", 5)


@pytest.mark.parametrize("text", ["a*b", "x,y", "100%", "two\nlines", "%2A literal", "a:b:c", ""])
def test_text_escaping_roundtrip(text):
    line = encode(Set("T1", text))
    assert "\n" not in line
    assert line.count("*") == 1  # only the checksum separator
    msg = decode(line)
    assert msg.value == text or (text == "" and msg.value == "")


def test_escape_helpers():
    assert escape("a*b,c%") == "a%2Ab%2Cc%25"
    assert unescape("a%2Ab%2Cc%25") == "a*b,c%"
    assert unescape("50% done") == "50% done"  # unknown sequences left alone


def test_card_quoted_label_with_comma():
    msg = decode('CARD:M1,MOTOR,0,-255,255,"Left, wheel"')
    assert msg == CardDef("M1", CardType.MOTOR, 0, -255, 255, "Left, wheel")


def test_card_minimal_and_lowercase_type():
    assert decode("CARD:D1,digital_in") == CardDef("D1", CardType.DIGITAL_IN)


def test_crlf_and_lowercase_tag():
    assert decode("val:A1:7\r\n") == Value("A1", 7)


@pytest.mark.parametrize(
    "line",
    ["", "FOO:1", "HB:abc", "SET:M1", "CARD:M1", "CARD:M1,LASER", "VAL:1A:5", "SYNCED:x"],
)
def test_invalid_lines(line):
    with pytest.raises(ProtocolError):
        decode(line)


def test_invalid_id_on_encode():
    with pytest.raises(ProtocolError):
        encode(Set("M:1", 5))
