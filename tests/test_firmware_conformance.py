"""Conformance scenarios (firmware/conformance/scenarios.txt) against SimTransport.

The same file is run against the MakeCode firmware logic by firmware/host
(Node). Both passing means the firmware answers like the simulator.
"""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from microbithub.core.protocol import checksum
from microbithub.transport.sim import SimTransport

SCENARIOS = Path(__file__).resolve().parents[1] / "firmware" / "conformance" / "scenarios.txt"

#: Time the simulator gets to answer one line.
REPLY_WAIT = 0.03


@dataclass
class Step:
    kind: str  # ">", "!", "~"
    arg: str
    expected: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    steps: list[Step] = field(default_factory=list)


def parse_scenarios(text: str) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.rstrip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("=== "):
            scenarios.append(Scenario(line[4:].strip()))
            continue
        if not scenarios:
            raise ValueError(f"line {number}: step before the first '==='")
        steps = scenarios[-1].steps
        if line.startswith("< "):
            if not steps:
                raise ValueError(f"line {number}: expected reply before any action")
            steps[-1].expected.append(line[2:])
        elif line.startswith(">> "):
            body = line[3:]
            steps.append(Step(">", f"{body}*{checksum(body)}"))
        elif line.startswith(("> ", "! ", "~ ")):
            steps.append(Step(line[0], line[2:]))
        else:
            raise ValueError(f"line {number}: cannot parse {line!r}")
    return scenarios


def matches(pattern: str, line: str) -> bool:
    regex = ".*".join(re.escape(part) for part in pattern.split("{any}"))
    return re.fullmatch(regex, line, re.DOTALL) is not None


async def run_scenario(scenario: Scenario) -> None:
    sim = SimTransport(animate=False)
    replies: list[str] = []
    sim.set_handlers(replies.append)
    await sim.connect()
    try:
        for i, step in enumerate(scenario.steps):
            if step.kind == ">":
                await sim.send_line(step.arg)
                await asyncio.sleep(REPLY_WAIT)
            elif step.kind == "!":
                card_id, _, value = step.arg.partition(" ")
                sim.set_sensor(card_id, value)
            elif step.kind == "~":
                await asyncio.sleep(int(step.arg) / 1000)
            got, replies[:] = list(replies), []
            where = f"{scenario.name!r} step {i + 1} ({step.kind} {step.arg})"
            assert len(got) == len(step.expected), f"{where}: got {got}, want {step.expected}"
            for want, line in zip(step.expected, got, strict=True):
                assert matches(want, line), f"{where}: got {line!r}, want {want!r}"
    finally:
        await sim.disconnect()


ALL = parse_scenarios(SCENARIOS.read_text(encoding="utf-8"))


def test_scenario_file_is_not_empty():
    assert len(ALL) >= 10


@pytest.mark.parametrize("scenario", ALL, ids=[s.name for s in ALL])
async def test_simulator_conforms(scenario):
    await run_scenario(scenario)


def test_matching():
    assert matches("HELLO:2,{any}", "HELLO:2,MicrobitHub-Sim,sim-0.1.0")
    assert not matches("ACK:M1", "ACK:M10")
    assert matches("LOG:Rejected line: {any}", "LOG:Rejected line: x")


def test_parser_appends_checksum():
    (scenario,) = parse_scenarios("=== x\n>> SET:M1:5\n< ACK:M1\n")
    assert scenario.steps[0].arg == f"SET:M1:5*{checksum('SET:M1:5')}"
    assert scenario.steps[0].expected == ["ACK:M1"]
