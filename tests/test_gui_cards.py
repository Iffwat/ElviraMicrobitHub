"""Card widgets, grid, connection bar and bridge, tested without an event loop."""

import pytest
from PySide6.QtWidgets import QApplication

from microbithub.core.model import Card, CardType
from microbithub.core.session import DeviceSession, SessionState
from microbithub.gui.bridge import SessionBridge
from microbithub.gui.card_grid import CardGrid
from microbithub.gui.cards import create_card_widget
from microbithub.gui.cards.analog import AnalogInCard, GaugeCard
from microbithub.gui.cards.digital import ButtonCard, DigitalInCard, DigitalOutCard
from microbithub.gui.cards.slider import MotorCard, ServoCard
from microbithub.gui.cards.sound import SoundCard, SoundCommand, parse_sound
from microbithub.gui.cards.text import GenericCard, TextInCard, TextOutCard
from microbithub.gui.connection_bar import ConnectionBar
from microbithub.transport.sim import SimTransport


@pytest.fixture(scope="module", autouse=True)
def qapp():
    return QApplication.instance() or QApplication([])


def requests(widget):
    sent = []
    widget.valueRequested.connect(lambda cid, v, ack: sent.append((cid, v, ack)))
    return sent


@pytest.mark.parametrize("card_type", list(CardType))
def test_every_card_type_gets_a_widget(card_type):
    widget = create_card_widget(Card("X1", card_type))
    assert widget.card_id == "X1"
    widget.set_live(True)
    widget.set_live(False)


def test_widget_classes():
    expected = {
        CardType.MOTOR: MotorCard,
        CardType.SERVO: ServoCard,
        CardType.ANALOG_IN: AnalogInCard,
        CardType.GAUGE: GaugeCard,
        CardType.DIGITAL_IN: DigitalInCard,
        CardType.DIGITAL_OUT: DigitalOutCard,
        CardType.BUTTON: ButtonCard,
        CardType.TEXT_IN: TextInCard,
        CardType.TEXT_OUT: TextOutCard,
        CardType.SOUND: SoundCard,
        CardType.JOYSTICK: GenericCard,
    }
    for card_type, cls in expected.items():
        assert type(create_card_widget(Card("X1", card_type))) is cls


def test_title_uses_label_and_id():
    widget = create_card_widget(Card("M1", CardType.MOTOR, label="Left wheel"))
    assert widget.title() == "Left wheel (M1)"
    assert create_card_widget(Card("M1", CardType.MOTOR)).title() == "M1"


def test_slider_uses_card_limits():
    servo = ServoCard(Card("S1", CardType.SERVO, 90, min=20, max=160))
    assert (servo.slider.minimum(), servo.slider.maximum()) == (20, 160)
    assert servo.value_label.text() == "90°"


def test_motor_buttons_commit_with_ack():
    motor = MotorCard(Card("M1", CardType.MOTOR))
    sent = requests(motor)
    motor.set_from_user(999)  # clamped to the slider range
    motor.stop_button.click()
    assert sent == [("M1", 255, True), ("M1", 0, True)]
    assert motor.slider.value() == 0


def test_slider_drag_streams_and_is_throttled():
    motor = MotorCard(Card("M1", CardType.MOTOR))
    sent = requests(motor)
    motor.slider.setSliderDown(True)  # emits sliderPressed
    for v in (10, 20, 30, 40):
        motor.slider.setValue(v)
    # First value goes out at once; the rest wait for the throttle timer.
    assert sent == [("M1", 10, False)]
    motor._on_throttle()  # timer fires: only the latest value is sent
    assert sent[-1] == ("M1", 40, False)
    motor.slider.setSliderDown(False)  # emits sliderReleased -> final value with ACK
    assert sent[-1] == ("M1", 40, True)
    assert len(sent) == 3


def test_device_values_are_deferred_while_dragging():
    card = Card("M1", CardType.MOTOR)
    motor = MotorCard(card)
    sent = requests(motor)
    motor.slider.setSliderDown(True)
    card.value = -100
    motor.update_card(card)
    assert motor.slider.value() == 0  # not moved under the mouse
    motor.slider.setSliderDown(False)
    assert motor.slider.value() == -100  # applied once released
    assert sent == [("M1", 0, True)]


def test_show_value_does_not_echo_back():
    motor = MotorCard(Card("M1", CardType.MOTOR))
    sent = requests(motor)
    motor.show_value(120)
    assert motor.slider.value() == 120
    assert sent == []


def test_digital_cards():
    din = DigitalInCard(Card("D1", CardType.DIGITAL_IN))
    din.show_value(1)
    assert din.led.on and din.state_label.text() == "HIGH"

    dout = DigitalOutCard(Card("D2", CardType.DIGITAL_OUT))
    sent = requests(dout)
    dout.toggle.click()
    dout.toggle.click()
    assert sent == [("D2", 1, True), ("D2", 0, True)]
    dout.show_value(1)
    assert dout.toggle.isChecked() and len(sent) == 2


def test_button_is_momentary():
    button = ButtonCard(Card("B1", CardType.BUTTON))
    sent = requests(button)
    button.button.pressed.emit()
    button.button.released.emit()
    assert sent == [("B1", 1, True), ("B1", 0, True)]


def test_text_cards():
    tin = TextInCard(Card("T1", CardType.TEXT_IN))
    assert tin.text_label.text() == "—"
    tin.show_value("<b>hi</b>")
    assert tin.text_label.text() == "<b>hi</b>"  # plain text, not HTML

    tout = TextOutCard(Card("T2", CardType.TEXT_OUT))
    sent = requests(tout)
    tout.send()  # empty: nothing sent
    tout.edit.setText("hello, robot")
    tout.edit.returnPressed.emit()
    assert sent == [("T2", "hello, robot", True)]
    assert tout.edit.text() == ""


def test_generic_card_validates_numbers():
    card = GenericCard(Card("J1", CardType.JOYSTICK))
    sent = requests(card)
    card.edit.setText("10,-20")
    card._send()
    assert sent == [("J1", "10,-20", True)]


def test_gauge_and_analog_show_values():
    gauge = GaugeCard(Card("G1", CardType.GAUGE, max=100))
    gauge.show_value(500)
    assert gauge.value_label.text() == "500" and gauge.bar.value() == 100

    analog = AnalogInCard(Card("A1", CardType.ANALOG_IN))
    for v in (100, 200, 300):
        analog.show_value(v)
    analog.redraw()
    xs, ys = analog.curve.getData()
    assert list(ys) == [0, 100, 200, 300, 300]
    assert xs[-1] == 0.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PLAY:SIREN:LOOP", SoundCommand("PLAY", "SIREN", True)),
        ("play:chime", SoundCommand("PLAY", "CHIME", False)),
        ("STOP", SoundCommand("STOP")),
        ("", SoundCommand("STOP")),
        ("PLAY:", None),
        ("PLAY:X:FOREVER", None),
        ("HONK", None),
    ],
)
def test_parse_sound(value, expected):
    assert parse_sound(value) == expected


def test_sound_card_plays_loops_and_mutes():
    sound = SoundCard(Card("B1", CardType.SOUND))
    played = []
    sound.player = played.append

    sound.show_value("PLAY:CHIME:ONCE")
    assert played == ["CHIME"] and sound.playing is None

    sound.show_value("PLAY:SIREN:LOOP")
    assert played[-1] == "SIREN" and sound._loop_timer.isActive()
    assert "looping" in sound.status_label.text()
    sound.show_value("STOP")
    assert not sound._loop_timer.isActive()
    assert sound.status_label.text() == "silent"

    sound.mute.setChecked(True)
    sound.show_value("PLAY:SIREN:LOOP")
    assert len(played) == 2 and "muted" in sound.status_label.text()


def test_cards_disabled_when_not_live():
    motor = MotorCard(Card("M1", CardType.MOTOR))
    motor.set_live(False)
    assert not motor.slider.isEnabled()
    motor.set_live(True)
    assert all(w.isEnabled() for w in motor.inputs)


def test_grid_builds_replaces_and_clears():
    grid = CardGrid()
    assert not grid.placeholder.isHidden()
    for card in SimTransport().cards.values():
        grid.add_card(card)
    assert list(grid.widgets) == ["M1", "M2", "S1", "A1", "D1", "D2", "T1", "T2", "B1"]
    assert grid.placeholder.isHidden()

    old = grid.widgets["S1"]
    grid.add_card(Card("S1", CardType.MOTOR, label="Now a motor"))
    assert isinstance(grid.widgets["S1"], MotorCard)
    assert grid.flow.indexOf(grid.widgets["S1"]) == 2  # same position
    assert grid.flow.indexOf(old) == -1

    sent = []
    grid.valueRequested.connect(lambda *a: sent.append(a))
    grid.set_live(True)
    grid.widgets["M1"].set_from_user(10)
    assert sent == [("M1", 10, True)]

    grid.clear()
    assert grid.widgets == {} and not grid.placeholder.isHidden()


def test_connection_bar_states():
    bar = ConnectionBar(["Simulator"])
    model = bar.transport_box.model()
    assert model.item(0).isEnabled()
    assert not model.item(1).isEnabled()  # USB: planned
    assert not bar.estop_button.isEnabled()

    asked = []
    bar.connectRequested.connect(asked.append)
    bar.connect_button.click()
    assert asked == ["Simulator"]

    bar.set_state(SessionState.CONNECTING)
    assert not bar.connect_button.isEnabled()
    bar.set_state(SessionState.READY)
    assert bar.connect_button.text() == "Disconnect" and bar.estop_button.isEnabled()

    stops, resumes = [], []
    bar.estopRequested.connect(lambda: stops.append(1))
    bar.resumeRequested.connect(lambda: resumes.append(1))
    bar.estop_button.click()
    bar.set_estopped(True)
    assert "RESUME" in bar.estop_button.text()
    bar.estop_button.click()
    assert stops == [1] and resumes == [1]

    bar.set_latency(23.4)
    assert bar.latency_label.text() == "23 ms"
    bar.set_link_ok(False)
    assert "Link lost" in bar.status_label.text()
    bar.set_state(SessionState.DISCONNECTED)
    assert bar.latency_label.text() == "" and not bar.estopped


def test_bridge_forwards_and_detaches():
    session = DeviceSession(SimTransport())
    bridge = SessionBridge()
    logs = []
    bridge.logReceived.connect(logs.append)
    bridge.attach(session)
    session.log_received.emit("hello")
    assert logs == ["hello"]
    assert len(session.log_received) == 1

    bridge.detach()
    session.log_received.emit("ignored")
    assert logs == ["hello"] and len(session.log_received) == 0


def test_dropped_cards_do_not_crash_on_exit():
    # Qt connections to lambdas that capture ``self`` keep a card alive until
    # interpreter shutdown, where Qt then aborts (seen in CI as exit 127/139).
    import subprocess
    import sys

    code = (
        "from PySide6.QtWidgets import QApplication\n"
        "from microbithub.core.model import Card, CardType\n"
        "from microbithub.gui.cards import create_card_widget\n"
        "app = QApplication([])\n"
        "for _ in range(3):\n"
        "    for t in CardType:\n"
        "        w = create_card_widget(Card('X1', t))\n"
        "        w.set_live(True)\n"
        "        w.set_live(False)\n"
    )
    for _ in range(3):  # the crash was intermittent
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )
        assert result.returncode == 0, result.stderr[-2000:]
