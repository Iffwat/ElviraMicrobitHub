"""Entry point.

python -m microbithub            open the GUI
python -m microbithub --demo     console demo against the simulator
"""

from __future__ import annotations

import argparse
import asyncio
import time

from .core.session import DeviceSession, SessionError
from .transport.sim import SimTransport


async def run_demo(seconds: float) -> None:
    sim = SimTransport(latency=0.02)
    session = DeviceSession(sim)

    last_print: dict[str, float] = {}

    def on_value(card) -> None:
        # Sensors stream at 20 Hz; print each card at most twice per second.
        now = time.monotonic()
        if now - last_print.get(card.id, 0.0) >= 0.5:
            last_print[card.id] = now
            print(f"[value] {card.id:<3} = {card.value!r}")

    session.state_changed.connect(lambda s: print(f"[state] {s.value}"))
    session.card_added.connect(
        lambda c: print(f"[card ] {c.id:<3} {c.type.value:<12} {c.label!r:<16} value={c.value!r}")
    )
    session.value_changed.connect(on_value)
    session.log_received.connect(lambda t: print(f"[log  ] {t}"))
    session.event_received.connect(lambda n: print(f"[event] {n}"))
    session.error.connect(lambda e: print(f"[error] {e}"))

    await session.connect()
    info = session.device_info
    print(f"Connected to {info.name} (firmware {info.firmware}), {len(session.cards)} cards\n")

    print("> set M1 = 200:", await session.set_value("M1", 200))
    print(
        "> set S1 = 0 (limit is 20..160):",
        await session.set_value("S1", 0),
        "->",
        session.cards["S1"].value,
    )
    print("> send text to T2:", await session.set_value("T2", "Hello micro:bit"))
    try:
        await session.set_value("A1", 5)
    except ValueError as exc:
        print(f"> set A1 refused locally: {exc}")

    await asyncio.sleep(seconds / 2)
    print("\n> EMERGENCY STOP")
    await session.estop()
    await asyncio.sleep(0.2)
    print("> set M1 = 100 while stopped:", await session.set_value("M1", 100))
    await session.resume()
    await asyncio.sleep(0.2)
    print("> set M1 = 100 after resume:", await session.set_value("M1", 100), "\n")

    await asyncio.sleep(seconds / 2)
    if session.latency_ms is not None:
        print(f"\nHeartbeat round-trip: {session.latency_ms:.1f} ms")
    await session.disconnect()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="microbithub",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--demo", action="store_true", help="run the console simulator demo")
    parser.add_argument("--seconds", type=float, default=6.0, help="demo length (default 6)")
    parser.add_argument("--quit-after", type=float, metavar="S", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args.demo:
        print("MicrobitHub - console demo with the simulated robot\n")
        try:
            asyncio.run(run_demo(args.seconds))
        except SessionError as exc:
            print(f"Session error: {exc}")
            return 1
        except KeyboardInterrupt:
            pass
        return 0

    from .app import run_gui  # imported here so --demo works without Qt

    return run_gui(quit_after=args.quit_after)


if __name__ == "__main__":
    raise SystemExit(main())
