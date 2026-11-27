/**
 * Runs firmware/conformance/scenarios.txt against the firmware logic
 * (protocol.ts + hub.ts) on a PC with Node, using a fake clock.
 *
 *   npm ci && npm test        (inside firmware/host)
 *
 * The Python half (tests/test_firmware_conformance.py) runs the same file
 * against SimTransport.
 */

declare const require: (name: string) => any
declare const process: { argv: string[]; exit(code: number): void }
declare const console: { log(text: string): void }

namespace microbithub.host {
    const fs = require("fs")

    /** Stream/tick period of the firmware sensor loop. */
    const TICK_MS = 50
    /** Time that passes for each line sent (the simulator waits 30 ms). */
    const REPLY_MS = 30

    class Step {
        expected: string[] = []
        constructor(public kind: string, public arg: string) { }
    }

    class Scenario {
        steps: Step[] = []
        constructor(public name: string) { }
    }

    export function parseScenarios(text: string): Scenario[] {
        const scenarios: Scenario[] = []
        const lines = text.split(/\r?\n/)
        for (let n = 0; n < lines.length; n++) {
            const line = lines[n].replace(/\s+$/, "")
            if (line == "" || line.charAt(0) == "#") continue
            if (line.indexOf("=== ") == 0) {
                scenarios.push(new Scenario(line.substr(4).trim()))
                continue
            }
            if (scenarios.length == 0) throw new Error(`line ${n + 1}: step before '==='`)
            const steps = scenarios[scenarios.length - 1].steps
            if (line.indexOf("< ") == 0) {
                if (steps.length == 0) throw new Error(`line ${n + 1}: reply before any action`)
                steps[steps.length - 1].expected.push(line.substr(2))
            } else if (line.indexOf(">> ") == 0) {
                const body = line.substr(3)
                steps.push(new Step(">", body + "*" + checksum(body)))
            } else if (line.indexOf("> ") == 0 || line.indexOf("! ") == 0 || line.indexOf("~ ") == 0) {
                steps.push(new Step(line.charAt(0), line.substr(2)))
            } else {
                throw new Error(`line ${n + 1}: cannot parse ${JSON.stringify(line)}`)
            }
        }
        return scenarios
    }

    function matches(pattern: string, line: string): boolean {
        const parts = pattern.split("{any}").map(p => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        return new RegExp("^" + parts.join("[\\s\\S]*") + "$").test(line)
    }

    /** The simulator's demo_cards(), declared the way a robot program would. */
    export function demoHub(): Hub {
        const hub = new Hub("MicrobitHub-Host")
        hub.addCard("M1", MOTOR, "Left wheel")
        hub.addCard("M2", MOTOR, "Right wheel")
        const s1 = hub.addCard("S1", SERVO, "Gripper")
        s1.setRange(20, 160)
        s1.num = 90
        hub.addCard("A1", ANALOG_IN, "Light sensor")
        hub.addCard("D1", DIGITAL_IN, "Bumper")
        hub.addCard("D2", DIGITAL_OUT, "Headlight")
        hub.addCard("T1", TEXT_IN, "Status")
        hub.addCard("T2", TEXT_OUT, "Message")
        hub.addCard("B1", SOUND, "Alarm")
        return hub
    }

    function runScenario(s: Scenario): string[] {
        const errors: string[] = []
        const hub = demoHub()
        let replies: string[] = []
        hub.send = (line: string) => { replies.push(line) }
        let now = 0
        let nextTick = TICK_MS

        const advance = (ms: number) => {
            const end = now + ms
            while (nextTick <= end) {
                now = nextTick
                hub.tick(now)
                nextTick += TICK_MS
            }
            now = end
        }

        for (let i = 0; i < s.steps.length; i++) {
            const step = s.steps[i]
            if (step.kind == ">") {
                hub.handle(step.arg, now)
                advance(REPLY_MS)
            } else if (step.kind == "!") {
                const space = step.arg.indexOf(" ")
                const card = hub.find(step.arg.substr(0, space))
                const value = step.arg.substr(space + 1)
                if (!card) {
                    errors.push(`step ${i + 1}: no card ${step.arg}`)
                } else if (card.isText()) {
                    hub.setText(card, value)
                } else {
                    hub.setNumber(card, parseNumber(value)[1])
                }
            } else {
                advance(parseInt(step.arg, 10))
            }
            const got = replies
            replies = []
            const where = `step ${i + 1} (${step.kind} ${step.arg})`
            const ok = got.length == step.expected.length &&
                got.every((line, k) => matches(step.expected[k], line))
            if (!ok) {
                errors.push(`${where}: got ${JSON.stringify(got)}, want ${JSON.stringify(step.expected)}`)
            }
        }
        return errors
    }

    export function main(argv: string[]): number {
        const file = argv[2] || "../conformance/scenarios.txt"
        const scenarios = parseScenarios(fs.readFileSync(file, "utf8"))
        let failed = 0
        for (const s of scenarios) {
            const errors = runScenario(s)
            if (errors.length == 0) {
                console.log(`PASS  ${s.name}`)
            } else {
                failed++
                console.log(`FAIL  ${s.name}`)
                for (const e of errors) console.log(`      ${e}`)
            }
        }
        console.log(`\n${scenarios.length - failed} passed, ${failed} failed`)
        return failed == 0 && scenarios.length > 0 ? 0 : 1
    }
}

process.exit(microbithub.host.main(process.argv))
