/**
 * MicrobitHub device logic: cards, message handling, watchdog and streaming.
 *
 * No hardware calls here: main.ts connects cards to motors, servos and pins
 * through ``HubCard.apply`` and sends lines through ``Hub.send``. That keeps
 * this file testable on a PC (firmware/host) against the Python simulator
 * (src/microbithub/transport/sim.py), which is the reference behaviour.
 */
namespace microbithub {
    export const FIRMWARE_VERSION = "0.1.0"

    // Card types (same names as CardType in core/model.py).
    export const MOTOR = "MOTOR"
    export const SERVO = "SERVO"
    export const ANALOG_IN = "ANALOG_IN"
    export const ANALOG_OUT = "ANALOG_OUT"
    export const DIGITAL_IN = "DIGITAL_IN"
    export const DIGITAL_OUT = "DIGITAL_OUT"
    export const BUTTON = "BUTTON"
    export const TEXT_IN = "TEXT_IN"
    export const TEXT_OUT = "TEXT_OUT"
    export const SOUND = "SOUND"
    export const GAUGE = "GAUGE"
    export const JOYSTICK = "JOYSTICK"
    export const SENSOR_BUILTIN = "SENSOR_BUILTIN"

    function isTextType(t: string): boolean {
        return t == TEXT_IN || t == TEXT_OUT || t == SOUND || t == JOYSTICK
    }

    function isWritableType(t: string): boolean {
        return t == MOTOR || t == SERVO || t == ANALOG_OUT || t == DIGITAL_OUT ||
            t == BUTTON || t == TEXT_OUT || t == JOYSTICK
    }

    /** Types the device streams to the PC when they change. */
    function isStreamedType(t: string): boolean {
        return t == ANALOG_IN || t == DIGITAL_IN || t == GAUGE || t == SENSOR_BUILTIN || t == TEXT_IN
    }

    function hasDeadband(t: string): boolean {
        return t == ANALOG_IN || t == GAUGE
    }

    /** Default [min, max] per type; [] means no limits (text, SENSOR_BUILTIN). */
    export function defaultRange(t: string): number[] {
        if (t == MOTOR) return [-255, 255]
        if (t == SERVO) return [0, 180]
        if (t == ANALOG_IN || t == ANALOG_OUT || t == GAUGE) return [0, 1023]
        if (t == DIGITAL_IN || t == DIGITAL_OUT || t == BUTTON) return [0, 1]
        return []
    }

    export class HubCard {
        id: string
        type: string
        label: string
        num: number
        text: string
        hasRange: boolean
        min: number
        max: number
        reportedNum: number
        reportedText: string
        /** Called after the value changes (PC, program, E-stop, watchdog). */
        apply: (card: HubCard) => void

        constructor(id: string, type: string, label: string) {
            this.id = id
            this.type = type
            this.label = label
            this.num = 0
            this.text = ""
            const r = defaultRange(type)
            this.hasRange = r.length == 2 && !isTextType(type)
            this.min = this.hasRange ? r[0] : 0
            this.max = this.hasRange ? r[1] : 0
            this.reportedNum = 0
            this.reportedText = ""
            this.apply = null
        }

        isText(): boolean { return isTextType(this.type) }
        isWritable(): boolean { return isWritableType(this.type) }

        setRange(lo: number, hi: number): void {
            if (this.isText()) return
            this.hasRange = true
            this.min = Math.min(lo, hi)
            this.max = Math.max(lo, hi)
            this.num = this.clamp(this.num)
        }

        clamp(v: number): number {
            if (!this.hasRange) return v
            return Math.max(this.min, Math.min(this.max, v))
        }

        /** The value as it appears on the wire (text is escaped). */
        wireValue(): string {
            return this.isText() ? escape(this.text) : "" + this.num
        }

        markReported(): void {
            this.reportedNum = this.num
            this.reportedText = this.text
        }

        changedSinceReport(deadband: number): boolean {
            if (this.isText()) return this.text != this.reportedText
            if (hasDeadband(this.type)) return Math.abs(this.num - this.reportedNum) > deadband
            return this.num != this.reportedNum
        }

        definition(): string {
            const lo = this.hasRange ? "" + this.min : ""
            const hi = this.hasRange ? "" + this.max : ""
            return "CARD:" + this.id + "," + this.type + "," + this.wireValue() + "," +
                lo + "," + hi + "," + escape(this.label)
        }

        applyNow(): void {
            if (this.apply) this.apply(this)
        }
    }

    export class Hub {
        cards: HubCard[]
        name: string
        estopped: boolean
        synced: boolean
        /** Stop the motors after this many ms without HB (0 = off). */
        watchdogMs: number
        /** Analog changes up to this size are not streamed. */
        deadband: number
        /** Time of the last HB in ms, or -1 before the first one (watchdog not armed). */
        lastHb: number
        watchdogTripped: boolean

        /** Writes one line (without newline) to the PC. */
        send: (line: string) => void
        /** A writable card was changed by the PC (after ACK). */
        onPcSet: (card: HubCard) => void
        /** ESTOP, RESUME or WATCHDOG happened. */
        onEvent: (name: string) => void

        constructor(name: string) {
            this.cards = []
            this.name = name
            this.estopped = false
            this.synced = false
            this.watchdogMs = 1000
            this.deadband = 5
            this.lastHb = -1
            this.watchdogTripped = false
            this.send = null
            this.onPcSet = null
            this.onEvent = null
        }

        // ------------------------------------------------------------ cards

        find(id: string): HubCard {
            for (const c of this.cards) if (c.id == id) return c
            return null
        }

        /** Declare a card. Declaring the same ID again replaces it in place. */
        addCard(id: string, type: string, label: string): HubCard {
            const card = new HubCard(id, type, label)
            for (let i = 0; i < this.cards.length; i++) {
                if (this.cards[i].id == id) {
                    this.cards[i] = card
                    return card
                }
            }
            this.cards.push(card)
            return card
        }

        /** The program changes a numeric card (sensor reading, motor speed ...). */
        setNumber(card: HubCard, value: number): void {
            if (card.isText()) return
            let v = card.clamp(Math.round(value))
            if (this.estopped && card.type == MOTOR) v = 0
            if (v == card.num) return
            card.num = v
            card.applyNow()
            this.reportProgramChange(card)
        }

        /** The program changes a text card (text in, sound command ...). */
        setText(card: HubCard, text: string): void {
            if (!card.isText()) return
            if (text == card.text && card.type != SOUND) return
            card.text = text
            card.applyNow()
            this.reportProgramChange(card)
        }

        private reportProgramChange(card: HubCard): void {
            // Streamed cards go out on the next tick (with deadband); the rest
            // (outputs set by the program, sound commands) are sent at once.
            if (isStreamedType(card.type) || !this.synced) return
            card.markReported()
            this.reply("VAL:" + card.id + ":" + card.wireValue())
        }

        // --------------------------------------------------------- messages

        reply(line: string): void {
            if (this.send) this.send(line)
        }

        log(text: string): void {
            this.reply("LOG:" + escape(text))
        }

        private event(name: string): void {
            this.reply("EVT:" + name)
            if (this.onEvent) this.onEvent(name)
        }

        /** Handle one line from the PC. ``now`` is control.millis(). */
        handle(line: string, now: number): void {
            const p = parseLine(line)
            if (p.error == "empty line") return
            if (p.error != "") {
                this.log("Rejected line: " + p.error)
                return
            }
            const tag = p.tag
            if (tag == "HELLO") {
                const comma = p.payload.indexOf(",")
                const v = comma < 0 ? p.payload : p.payload.substr(0, comma)
                if (!isInteger(v)) {
                    this.log("Rejected line: HELLO version is not an integer")
                    return
                }
                this.reply("HELLO:" + PROTOCOL_VERSION + "," + escape(this.name) + "," + escape(FIRMWARE_VERSION))
            } else if (tag == "SYNC") {
                for (const c of this.cards) {
                    this.reply(c.definition())
                    c.markReported()
                }
                this.reply("SYNCED:" + this.cards.length)
                this.synced = true
            } else if (tag == "HB") {
                if (!isInteger(p.payload)) {
                    this.log("Rejected line: HB seq is not an integer")
                    return
                }
                this.lastHb = now
                this.watchdogTripped = false
                this.reply("HB:" + toInteger(p.payload))
            } else if (tag == "SET") {
                const colon = p.payload.indexOf(":")
                if (colon < 0) {
                    this.log("Rejected line: SET needs <id>:<value>")
                    return
                }
                const id = p.payload.substr(0, colon)
                if (!isValidId(id)) {
                    this.log("Rejected line: invalid card id")
                    return
                }
                this.applySet(id, p.payload.substr(colon + 1))
            } else if (tag == "ESTOP") {
                this.estopped = true
                this.stopMotors()
                this.event("ESTOP")
            } else if (tag == "RESUME") {
                this.estopped = false
                this.event("RESUME")
            } else if (tag == "SYNCED" || tag == "CARD" || tag == "VAL" || tag == "ACK" ||
                tag == "NAK" || tag == "LOG" || tag == "EVT") {
                this.log("Ignored " + tag)
            } else {
                this.log("Rejected line: unknown message type " + tag)
            }
        }

        private applySet(id: string, raw: string): void {
            const card = this.find(id)
            if (!card) {
                this.reply("NAK:" + id + ",UNKNOWN")
                return
            }
            if (!card.isWritable()) {
                this.reply("NAK:" + id + ",READ_ONLY")
                return
            }
            if (this.estopped && card.type == MOTOR) {
                this.reply("NAK:" + id + ",ESTOP")
                this.reply("VAL:" + id + ":" + card.wireValue()) // correct the PC's slider
                return
            }
            if (card.isText()) {
                // Like protocol.py, an integer-looking value is a number: "+5" -> "5".
                card.text = isInteger(raw) ? "" + toInteger(raw) : unescape(raw)
                card.markReported()
                card.applyNow()
                this.reply("ACK:" + id)
                if (card.type == TEXT_OUT) this.log(id + " received text: " + card.text)
            } else {
                const parsed = parseNumber(isInteger(raw) ? raw : unescape(raw))
                if (parsed[0] == 0) {
                    this.reply("NAK:" + id + ",BAD_VALUE")
                    return
                }
                const requested = parsed[1]
                card.num = card.clamp(requested)
                card.markReported()
                card.applyNow()
                this.reply("ACK:" + id)
                if (card.num != requested) this.reply("VAL:" + id + ":" + card.num)
            }
            if (this.onPcSet) this.onPcSet(card)
        }

        /** Set every motor to 0 and tell the PC. */
        stopMotors(): void {
            for (const c of this.cards) {
                if (c.type == MOTOR && c.num != 0) {
                    c.num = 0
                    c.markReported()
                    c.applyNow()
                    this.reply("VAL:" + c.id + ":0")
                }
            }
        }

        /** Stop the motors without sending anything (link already gone). */
        stopMotorsSilently(): void {
            for (const c of this.cards) {
                if (c.type == MOTOR && c.num != 0) {
                    c.num = 0
                    c.applyNow()
                }
            }
        }

        // ------------------------------------------------------------- tick

        /** Call about 20 times per second: watchdog, then stream changed sensors. */
        tick(now: number): void {
            if (this.watchdogMs > 0 && this.lastHb >= 0 && !this.watchdogTripped &&
                now - this.lastHb > this.watchdogMs) {
                this.watchdogTripped = true
                this.stopMotors()
                this.event("WATCHDOG")
            }
            if (!this.synced) return
            for (const c of this.cards) {
                if (isStreamedType(c.type) && c.changedSinceReport(this.deadband)) {
                    c.markReported()
                    this.reply("VAL:" + c.id + ":" + c.wireValue())
                }
            }
        }
    }
}
