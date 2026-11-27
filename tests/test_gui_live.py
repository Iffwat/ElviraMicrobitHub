"""The whole window against SimTransport, on a real qasync (Qt + asyncio) loop.

These are plain (sync) tests: each one runs its scenario with
``loop.run_until_complete`` on a fresh ``qasync.QEventLoop``, separate from
pytest-asyncio's loop.
"""

import asyncio

import pytest
import qasync
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from microbithub.core.protocol import Value, encode
from microbithub.core.session import SessionState
from microbithub.gui.main_window import MainWindow
from microbithub.transport.sim import SimTransport


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def run(qapp):
    loop = qasync.QEventLoop(qapp)
    yield loop.run_until_complete
    # A failed scenario can leave transport tasks running: cancel them first.
    pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
    loop.close()


async def wait_until(cond, timeout=2.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def make_window(**sim_options):
    sims = []

    def factory():
        sim = SimTransport(animate=False, **sim_options)
        sims.append(sim)
        return sim

    window = MainWindow(
        transports={"Simulator": factory},
        session_options={"heartbeat_interval": 0.05, "ack_timeout": 0.15},
    )
    window.show()
    return window, sims


async def connected(**sim_options):
    window, sims = make_window(**sim_options)
    window.connection_bar.connect_button.click()
    await wait_until(lambda: window.session is not None and window.session.is_ready)
    return window, sims[-1]


def terminal_has(window, text):
    return any(text in line for line in window.terminal.lines())


def test_connect_builds_live_cards(run):
    async def scenario():
        window, sim = await connected()
        assert list(window.grid.widgets) == list(sim.cards)
        assert all(w.inputs[0].isEnabled() for w in window.grid.widgets.values() if w.inputs)
        assert window.connection_bar.connect_button.text() == "Disconnect"
        assert "9 cards" in window.status_label.text()
        assert terminal_has(window, "Connected to MicrobitHub-Sim")
        await wait_until(lambda: window.connection_bar.latency_label.text().endswith("ms"))

        window.connection_bar.connect_button.click()  # now "Disconnect"
        await wait_until(lambda: window.session.state is SessionState.DISCONNECTED)
        assert not window.card_widget("M1").slider.isEnabled()
        assert window.connection_bar.connect_button.text() == "Connect"
        window.close()

    run(scenario())


def test_controls_reach_the_robot(run):
    async def scenario():
        window, sim = await connected()

        window.card_widget("M1").set_from_user(180)
        window.card_widget("S1").set_from_user(170)  # limit is 160
        window.card_widget("D2").toggle.click()
        text_card = window.card_widget("T2")
        text_card.edit.setText("Hi, bot*")
        text_card.send_button.click()

        await wait_until(
            lambda: (
                sim.cards["M1"].value == 180
                and sim.cards["S1"].value == 160
                and sim.cards["D2"].value == 1
                and sim.cards["T2"].value == "Hi, bot*"
            )
        )
        assert window.card_widget("S1").slider.value() == 160
        await wait_until(lambda: terminal_has(window, "T2 received text: Hi, bot*"))
        await window.disconnect_device()
        window.close()

    run(scenario())


def test_sensor_values_reach_the_cards(run):
    async def scenario():
        window, sim = await connected()
        sim.set_sensor("A1", 700)
        sim.set_sensor("D1", 1)
        sim.set_sensor("T1", "all good")
        await wait_until(
            lambda: (
                window.card_widget("A1").value_label.text() == "700"
                and window.card_widget("D1").state_label.text() == "HIGH"
                and window.card_widget("T1").text_label.text() == "all good"
            )
        )
        assert window.card_widget("A1").samples[-1][1] == 700.0

        played = []
        window.card_widget("B1").player = played.append
        sim._emit_line(encode(Value("B1", "PLAY:SIREN:ONCE")))
        assert played == ["SIREN"]
        await window.disconnect_device()
        window.close()

    run(scenario())


def test_space_is_emergency_stop(run, qapp):
    async def scenario():
        window, sim = await connected()
        motor = window.card_widget("M1")
        motor.set_from_user(200)
        await wait_until(lambda: sim.cards["M1"].value == 200)

        # Space inside a text box types a space; it does not stop the robot.
        text_card = window.card_widget("T2")
        window.activateWindow()
        text_card.edit.setFocus()
        QTest.keyClick(text_card.edit, Qt.Key.Key_Space)
        await asyncio.sleep(0.1)
        assert text_card.edit.text() == " " and not sim.estopped

        motor.slider.setFocus()
        QTest.keyClick(motor.slider, Qt.Key.Key_Space)
        await wait_until(lambda: sim.estopped and window.connection_bar.estopped)
        await wait_until(lambda: motor.slider.value() == 0)
        assert "RESUME" in window.connection_bar.estop_button.text()

        # A motor command during E-stop is refused and the slider snaps back.
        motor.set_from_user(100)
        await wait_until(lambda: terminal_has(window, "M1 rejected: ESTOP"))
        await wait_until(lambda: motor.slider.value() == 0)

        window.connection_bar.estop_button.click()  # RESUME
        await wait_until(lambda: not sim.estopped and not window.connection_bar.estopped)
        motor.set_from_user(100)
        await wait_until(lambda: sim.cards["M1"].value == 100)
        await window.disconnect_device()
        window.close()

    run(scenario())


def test_disconnect_stops_motors(run):
    async def scenario():
        window, sim = await connected()
        window.card_widget("M2").set_from_user(-150)
        await wait_until(lambda: sim.cards["M2"].value == -150)
        await window.disconnect_device()
        assert "SET:M2:0" in [line.split("*")[0] for line in sim.received]
        assert terminal_has(window, "Disconnected")
        window.close()

    run(scenario())


def test_lost_connection_is_reported(run):
    async def scenario():
        window, sim = await connected()
        sim.simulate_disconnect()
        await wait_until(lambda: window.session.state is SessionState.DISCONNECTED)
        assert terminal_has(window, "Connection lost")
        assert not window.card_widget("M1").slider.isEnabled()
        assert window.connection_bar.connect_button.isEnabled()

        # Reconnecting builds a fresh card grid.
        window.connection_bar.connect_button.click()
        await wait_until(lambda: window.session.is_ready)
        assert window.card_widget("M1").slider.isEnabled()
        await window.disconnect_device()
        window.close()

    run(scenario())


def test_watchdog_event_is_shown(run):
    async def scenario():
        window, sim = await connected(watchdog_timeout=0.2)
        await wait_until(lambda: sim._last_hb is not None)  # watchdog armed by first HB
        window.session._hb_task.cancel()  # heartbeat stops -> watchdog trips
        await wait_until(lambda: terminal_has(window, "Watchdog"))
        await window.disconnect_device()
        window.close()

    run(scenario())


def test_failed_connect_is_reported(run):
    async def scenario():
        def broken():
            raise OSError("no such port")

        window = MainWindow(transports={"Broken": broken})
        window.request_connect("Broken")
        await wait_until(lambda: terminal_has(window, "Connect failed: no such port"))
        window.request_connect("Missing")
        assert terminal_has(window, "'Missing' is not available")
        window.close()

    run(scenario())


def test_close_while_connected_disconnects_first(run):
    async def scenario():
        window, sim = await connected()
        window.close()
        assert window.isVisible()  # waits for the disconnect
        await wait_until(lambda: not window.isVisible())
        assert not sim.is_connected

    run(scenario())
