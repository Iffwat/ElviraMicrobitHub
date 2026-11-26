import asyncio

import pytest

from microbithub.core.protocol import Heartbeat, encode
from microbithub.core.session import DeviceSession, SessionError, SessionState
from microbithub.transport.sim import SimTransport


async def wait_until(cond, timeout=1.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not cond():
        if loop.time() > end:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


def collect(signal):
    items = []
    signal.connect(lambda *a: items.append(a[0] if len(a) == 1 else a))
    return items


@pytest.fixture
async def pair():
    sim = SimTransport(animate=False, watchdog_timeout=0.3)
    session = DeviceSession(sim, heartbeat_interval=0.05, ack_timeout=0.15)
    await session.connect()
    yield session, sim
    await session.disconnect()


async def test_connect_discovers_cards(pair):
    session, sim = pair
    assert session.state is SessionState.READY
    assert set(session.cards) == set(sim.cards)
    assert session.device_info.name == "MicrobitHub-Sim"
    assert session.cards["S1"].min == 20


async def test_set_value_is_acked(pair):
    session, sim = pair
    assert await session.set_value("M1", 200) is True
    assert sim.cards["M1"].value == 200
    assert session.cards["M1"].value == 200


async def test_value_is_clamped_before_sending(pair):
    session, sim = pair
    assert await session.set_value("S1", 0) is True
    assert session.cards["S1"].value == 20
    assert sim.cards["S1"].value == 20


async def test_local_validation(pair):
    session, _ = pair
    with pytest.raises(ValueError):
        await session.set_value("A1", 5)  # read-only
    with pytest.raises(KeyError):
        await session.set_value("Z9", 5)
    with pytest.raises(ValueError):
        await session.set_value("M1", "fast")


async def test_estop_blocks_motors_until_resume(pair):
    session, sim = pair
    await session.set_value("M1", 150)
    events = collect(session.event_received)
    errors = collect(session.error)

    await session.estop()
    await wait_until(lambda: session.estopped)
    assert "ESTOP" in events
    await wait_until(lambda: session.cards["M1"].value == 0)

    assert await session.set_value("M1", 100) is False
    assert any("ESTOP" in e for e in errors)
    await wait_until(lambda: session.cards["M1"].value == 0)  # corrected by the device

    await session.resume()
    await wait_until(lambda: not session.estopped)
    assert await session.set_value("M1", 100) is True


async def test_watchdog_stops_motors_without_heartbeat():
    sim = SimTransport(animate=False, watchdog_timeout=0.1)
    session = DeviceSession(sim, heartbeat_interval=None)
    await session.connect()
    events = collect(session.event_received)
    try:
        await session.set_value("M1", 200)
        await sim.send_line(encode(Heartbeat(1)))  # arm the watchdog, then go silent
        await wait_until(lambda: "WATCHDOG" in events)
        await wait_until(lambda: session.cards["M1"].value == 0)
    finally:
        await session.disconnect()


async def test_heartbeat_keeps_motors_running(pair):
    session, sim = pair
    events = collect(session.event_received)
    await session.set_value("M1", 200)
    await asyncio.sleep(0.5)  # > watchdog timeout (0.3 s)
    assert "WATCHDOG" not in events
    assert sim.cards["M1"].value == 200


async def test_latency_measured(pair):
    session, _ = pair
    await wait_until(lambda: session.latency_ms is not None)
    assert session.latency_ms >= 0


async def test_retry_after_lost_line(pair):
    session, sim = pair
    sim.drop_incoming = 1
    assert await session.set_value("M2", -100) is True
    sets = [ln for ln in sim.received if ln.startswith("SET:M2")]
    assert len(sets) == 2
    assert sim.cards["M2"].value == -100


async def test_gives_up_after_retries(pair):
    session, sim = pair
    errors = collect(session.error)
    sim.drop_incoming = 100
    assert await session.set_value("M2", 50) is False
    assert any("No ACK" in e for e in errors)
    sim.drop_incoming = 0


async def test_sensor_streaming_with_deadband(pair):
    session, sim = pair
    sim.set_sensor("A1", 700)
    await wait_until(lambda: session.cards["A1"].value == 700)
    sim.set_sensor("A1", 703)  # within deadband (5)
    await asyncio.sleep(0.2)
    assert session.cards["A1"].value == 700
    sim.set_sensor("D1", 1)  # digital: every change is sent
    await wait_until(lambda: session.cards["D1"].value == 1)


async def test_text_out_reaches_device(pair):
    session, sim = pair
    logs = collect(session.log_received)
    assert await session.set_value("T2", "hi, there*") is True
    assert sim.cards["T2"].value == "hi, there*"
    await wait_until(lambda: any("hi, there*" in t for t in logs))


async def test_unexpected_disconnect(pair):
    session, sim = pair
    errors = collect(session.error)
    sim.simulate_disconnect()
    assert session.state is SessionState.DISCONNECTED
    assert "Connection lost" in errors


async def test_handshake_timeout():
    sim = SimTransport(animate=False)
    sim.drop_incoming = 100
    session = DeviceSession(sim, handshake_timeout=0.2)
    with pytest.raises(SessionError, match="HELLO"):
        await session.connect()
    assert session.state is SessionState.DISCONNECTED
    assert not sim.is_connected


async def test_reconnect_after_disconnect(pair):
    session, _ = pair
    await session.disconnect()
    assert session.state is SessionState.DISCONNECTED
    await session.connect()
    assert session.state is SessionState.READY
    assert await session.set_value("M1", 10) is True


async def test_animated_simulator_streams_data():
    sim = SimTransport(animate=True)
    session = DeviceSession(sim)
    values = collect(session.value_changed)
    await session.connect()
    try:
        await wait_until(lambda: any(c.id == "A1" for c in values))
        await wait_until(lambda: any(c.id == "T1" for c in values))
    finally:
        await session.disconnect()
