/**
 * MicrobitHub blocks: connect a micro:bit + Cytron Motion:bit robot to the
 * MicrobitHub dashboard over USB serial or Bluetooth UART.
 *
 * Protocol and safety logic live in hub.ts; this file binds cards to the
 * hardware (Motion:bit motors and servos, pins, built-in sensors) and to the
 * two links.
 */

enum HubMotor {
    //% block="M1"
    M1,
    //% block="M2"
    M2,
    //% block="M3"
    M3,
    //% block="M4"
    M4
}

enum HubServo {
    //% block="S1"
    S1,
    //% block="S2"
    S2,
    //% block="S3"
    S3,
    //% block="S4"
    S4,
    //% block="S5"
    S5,
    //% block="S6"
    S6,
    //% block="S7"
    S7,
    //% block="S8"
    S8
}

enum HubInputKind {
    //% block="analog"
    Analog,
    //% block="digital"
    Digital
}

enum HubOutputKind {
    //% block="analog (PWM)"
    Analog,
    //% block="digital (on/off)"
    Digital,
    //% block="push button"
    Button
}

enum HubTextDirection {
    //% block="micro:bit → dashboard"
    ToDashboard,
    //% block="dashboard → micro:bit"
    FromDashboard
}

/** Pins on the Motion:bit breakout. Analog input works on P0, P1 and P2 only. */
enum HubPin {
    //% block="no pin"
    None,
    //% block="P0"
    P0,
    //% block="P1"
    P1,
    //% block="P2"
    P2,
    //% block="P9"
    P9,
    //% block="P12"
    P12,
    //% block="P13"
    P13,
    //% block="P14"
    P14,
    //% block="P15"
    P15,
    //% block="P16"
    P16
}

enum HubSensor {
    //% block="temperature (°C)"
    Temperature,
    //% block="light level"
    LightLevel,
    //% block="compass heading (°)"
    Compass,
    //% block="acceleration X (mg)"
    AccelX,
    //% block="acceleration Y (mg)"
    AccelY,
    //% block="acceleration Z (mg)"
    AccelZ,
    //% block="acceleration strength (mg)"
    AccelStrength
}

enum HubSound {
    //% block="siren"
    Siren,
    //% block="chime"
    Chime,
    //% block="beep"
    Beep
}

enum HubSoundMode {
    //% block="once"
    Once,
    //% block="loop"
    Loop
}

//% color="#2f80ed" weight=100 icon="" block="MicrobitHub"
//% groups='["Setup", "Actions", "Values", "Events"]'
namespace microbithub {
    /** Sensor loop period (20 Hz, like the simulator). */
    const TICK_MS = 50

    let hub: Hub = null
    let started = false
    let replyOverBle = false

    // Pins and sensors linked to cards (parallel arrays: MakeCode has no Map).
    let pinCards: HubCard[] = []
    let pinNumbers: HubPin[] = []
    let sensorCards: HubCard[] = []
    let sensorKinds: HubSensor[] = []

    // Servo smoothing, index = servo channel 0..7.
    let servoCards: HubCard[] = [null, null, null, null, null, null, null, null]
    let servoCurrent: number[] = [90, 90, 90, 90, 90, 90, 90, 90]
    let servoDelay: number[] = [0, 0, 0, 0, 0, 0, 0, 0]
    let servoLastStep: number[] = [0, 0, 0, 0, 0, 0, 0, 0]

    // User event handlers.
    let valueIds: string[] = []
    let valueHandlers: ((value: number) => void)[] = []
    let textIds: string[] = []
    let textHandlers: ((text: string) => void)[] = []
    let estopHandlers: (() => void)[] = []

    function theHub(): Hub {
        if (!hub) {
            hub = new Hub("MicrobitHub-" + control.deviceName())
            hub.send = sendLine
            hub.onPcSet = dispatchPcSet
            hub.onEvent = dispatchEvent
        }
        return hub
    }

    function sendLine(line: string): void {
        if (replyOverBle) bluetooth.uartWriteString(line + "\n")
        else serial.writeString(line + "\n")
    }

    // Handlers run in their own fiber so a slow handler (e.g. showString)
    // never delays the reply to the dashboard.
    function runTextHandler(h: (text: string) => void, t: string): void {
        control.runInParallel(() => h(t))
    }

    function runValueHandler(h: (value: number) => void, v: number): void {
        control.runInParallel(() => h(v))
    }

    function dispatchPcSet(card: HubCard): void {
        if (card.isText()) {
            for (let i = 0; i < textIds.length; i++) {
                if (textIds[i] == card.id) runTextHandler(textHandlers[i], card.text)
            }
        } else {
            for (let i = 0; i < valueIds.length; i++) {
                if (valueIds[i] == card.id) runValueHandler(valueHandlers[i], card.num)
            }
        }
    }

    function dispatchEvent(name: string): void {
        if (name != "ESTOP") return
        for (const h of estopHandlers) control.runInParallel(h)
    }

    // ------------------------------------------------------------ hardware

    function motorChannel(m: HubMotor): MotionBitMotorChannel {
        if (m == HubMotor.M2) return MotionBitMotorChannel.M2
        if (m == HubMotor.M3) return MotionBitMotorChannel.M3
        if (m == HubMotor.M4) return MotionBitMotorChannel.M4
        return MotionBitMotorChannel.M1
    }

    function servoChannel(index: number): MotionBitServoChannel {
        if (index == 1) return MotionBitServoChannel.S2
        if (index == 2) return MotionBitServoChannel.S3
        if (index == 3) return MotionBitServoChannel.S4
        if (index == 4) return MotionBitServoChannel.S5
        if (index == 5) return MotionBitServoChannel.S6
        if (index == 6) return MotionBitServoChannel.S7
        if (index == 7) return MotionBitServoChannel.S8
        return MotionBitServoChannel.S1
    }

    function driveMotor(m: HubMotor, speed: number): void {
        const ch = motorChannel(m)
        if (speed > 0) motionbit.runMotor(ch, MotionBitMotorDirection.Forward, speed)
        else if (speed < 0) motionbit.runMotor(ch, MotionBitMotorDirection.Backward, -speed)
        else motionbit.runMotor(ch, MotionBitMotorDirection.Forward, 0)
    }

    function digitalPin(p: HubPin): DigitalPin {
        if (p == HubPin.P1) return DigitalPin.P1
        if (p == HubPin.P2) return DigitalPin.P2
        if (p == HubPin.P9) return DigitalPin.P9
        if (p == HubPin.P12) return DigitalPin.P12
        if (p == HubPin.P13) return DigitalPin.P13
        if (p == HubPin.P14) return DigitalPin.P14
        if (p == HubPin.P15) return DigitalPin.P15
        if (p == HubPin.P16) return DigitalPin.P16
        return DigitalPin.P0
    }

    function analogPin(p: HubPin): AnalogPin {
        if (p == HubPin.P1) return AnalogPin.P1
        if (p == HubPin.P2) return AnalogPin.P2
        if (p == HubPin.P9) return AnalogPin.P9
        if (p == HubPin.P12) return AnalogPin.P12
        if (p == HubPin.P13) return AnalogPin.P13
        if (p == HubPin.P14) return AnalogPin.P14
        if (p == HubPin.P15) return AnalogPin.P15
        if (p == HubPin.P16) return AnalogPin.P16
        return AnalogPin.P0
    }

    function readSensor(s: HubSensor): number {
        if (s == HubSensor.Temperature) return input.temperature()
        if (s == HubSensor.LightLevel) return input.lightLevel()
        if (s == HubSensor.Compass) return input.compassHeading()
        if (s == HubSensor.AccelX) return input.acceleration(Dimension.X)
        if (s == HubSensor.AccelY) return input.acceleration(Dimension.Y)
        if (s == HubSensor.AccelZ) return input.acceleration(Dimension.Z)
        return input.acceleration(Dimension.Strength)
    }

    function writePin(card: HubCard): void {
        for (let i = 0; i < pinCards.length; i++) {
            if (pinCards[i] == card) {
                if (card.type == ANALOG_OUT) pins.analogWritePin(analogPin(pinNumbers[i]), card.num)
                else pins.digitalWritePin(digitalPin(pinNumbers[i]), card.num)
            }
        }
    }

    function readInputs(): void {
        const h = theHub()
        for (let i = 0; i < pinCards.length; i++) {
            const c = pinCards[i]
            if (c.type == ANALOG_IN) h.setNumber(c, pins.analogReadPin(analogPin(pinNumbers[i])))
            else if (c.type == DIGITAL_IN) h.setNumber(c, pins.digitalReadPin(digitalPin(pinNumbers[i])))
        }
        for (let i = 0; i < sensorCards.length; i++) {
            h.setNumber(sensorCards[i], readSensor(sensorKinds[i]))
        }
    }

    /** Moves each servo one degree towards its target every ``servoDelay`` ms. */
    function stepServos(now: number): boolean {
        let moving = false
        for (let i = 0; i < 8; i++) {
            const c = servoCards[i]
            if (!c || servoCurrent[i] == c.num) continue
            if (servoDelay[i] <= 0) {
                servoCurrent[i] = c.num
                motionbit.setServoPosition(servoChannel(i), servoCurrent[i])
            } else if (now - servoLastStep[i] >= servoDelay[i]) {
                servoLastStep[i] = now
                servoCurrent[i] += servoCurrent[i] < c.num ? 1 : -1
                motionbit.setServoPosition(servoChannel(i), servoCurrent[i])
            }
            if (servoCurrent[i] != c.num) moving = true
        }
        return moving
    }

    function onLine(line: string, overBle: boolean): void {
        replyOverBle = overBle
        theHub().handle(line, control.millis())
    }

    // --------------------------------------------------------------- setup

    /**
     * Start MicrobitHub: listen on USB serial (115200 baud) and Bluetooth UART,
     * answer the dashboard, run the 1-second safety watchdog and stream sensors.
     */
    //% block="start MicrobitHub"
    //% group="Setup" weight=100
    export function start(): void {
        if (started) return
        started = true
        theHub()

        serial.redirectToUSB()
        serial.setBaudRate(BaudRate.BaudRate115200)
        serial.setRxBufferSize(128)
        serial.setTxBufferSize(128)
        serial.onDataReceived(serial.delimiters(Delimiters.NewLine), () => {
            onLine(serial.readUntil(serial.delimiters(Delimiters.NewLine)), false)
        })

        bluetooth.startUartService()
        bluetooth.onUartDataReceived(serial.delimiters(Delimiters.NewLine), () => {
            onLine(bluetooth.uartReadUntil(serial.delimiters(Delimiters.NewLine)), true)
        })
        bluetooth.onBluetoothDisconnected(() => {
            // The radio link is gone: stop now instead of waiting for the watchdog.
            if (replyOverBle) {
                theHub().stopMotorsSilently()
                replyOverBle = false
            }
        })

        control.inBackground(() => {
            while (true) {
                readInputs()
                theHub().tick(control.millis())
                basic.pause(TICK_MS)
            }
        })
        control.inBackground(() => {
            while (true) {
                basic.pause(stepServos(control.millis()) ? 5 : 20)
            }
        })
    }

    /**
     * Add a dashboard card for a Motion:bit DC motor (speed -255..255).
     * @param maxSpeed limit for both directions, eg: 255
     */
    //% block="add motor card $motor||label $label max speed $maxSpeed"
    //% maxSpeed.min=0 maxSpeed.max=255 maxSpeed.defl=255
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=90
    export function addMotor(motor: HubMotor, label: string = "", maxSpeed: number = 255): void {
        const card = theHub().addCard("M" + (motor + 1), MOTOR, label)
        const limit = Math.max(0, Math.min(255, maxSpeed))
        card.setRange(-limit, limit)
        card.apply = (c: HubCard) => driveMotor(motor, c.num)
        card.applyNow()
    }

    /**
     * Add a dashboard card for a Motion:bit servo. Limits are enforced here on
     * the micro:bit, whatever the dashboard sends.
     * @param start starting angle, eg: 90
     * @param delay ms per degree when moving (0 = jump at once), eg: 0
     */
    //% block="add servo card $servo||label $label start $start ° limits $low ° to $high ° move delay $delay ms/°"
    //% start.defl=90 low.defl=0 high.defl=180 delay.defl=0
    //% start.min=0 start.max=180 low.min=0 low.max=180 high.min=0 high.max=180
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=89
    export function addServo(servo: HubServo, label: string = "", start: number = 90,
        low: number = 0, high: number = 180, delay: number = 0): void {
        const card = theHub().addCard("S" + (servo + 1), SERVO, label)
        card.setRange(low, high)
        card.num = card.clamp(start)
        servoCards[servo] = card
        servoDelay[servo] = Math.max(0, delay)
        servoCurrent[servo] = card.num
        motionbit.setServoPosition(servoChannel(servo), card.num)
    }

    /**
     * Add an input card. With a pin, the pin is read 20 times per second and
     * changes are sent to the dashboard. Without a pin, use "set card value".
     */
    //% block="add $kind input card $id read from $pin||label $label"
    //% id.defl="A1" pin.defl=HubPin.P0
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=88
    export function addInput(kind: HubInputKind, id: string, pin: HubPin, label: string = ""): void {
        const type = kind == HubInputKind.Analog ? ANALOG_IN : DIGITAL_IN
        const card = theHub().addCard(id, type, label)
        if (pin != HubPin.None) linkPin(card, pin)
    }

    /**
     * Add an output card the dashboard controls. With a pin, the value is
     * written to the pin; you can also read it with "card value".
     */
    //% block="add $kind output card $id write to $pin||label $label"
    //% id.defl="D1" pin.defl=HubPin.P12
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=87
    export function addOutput(kind: HubOutputKind, id: string, pin: HubPin, label: string = ""): void {
        let type = DIGITAL_OUT
        if (kind == HubOutputKind.Analog) type = ANALOG_OUT
        else if (kind == HubOutputKind.Button) type = BUTTON
        const card = theHub().addCard(id, type, label)
        if (pin != HubPin.None) {
            linkPin(card, pin)
            card.apply = writePin
            card.applyNow()
        }
    }

    function linkPin(card: HubCard, pin: HubPin): void {
        for (let i = 0; i < pinCards.length; i++) {
            if (pinCards[i].id == card.id) {
                pinCards[i] = card
                pinNumbers[i] = pin
                return
            }
        }
        pinCards.push(card)
        pinNumbers.push(pin)
    }

    /** Add a text card: messages to the dashboard, or a text box on the dashboard. */
    //% block="add text card $id $direction||label $label"
    //% id.defl="T1"
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=86
    export function addText(id: string, direction: HubTextDirection, label: string = ""): void {
        theHub().addCard(id, direction == HubTextDirection.ToDashboard ? TEXT_IN : TEXT_OUT, label)
    }

    /** Add a built-in sensor card; it is read and sent automatically. */
    //% block="add sensor card $id showing $sensor||label $label"
    //% id.defl="E1"
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=85
    export function addSensor(id: string, sensor: HubSensor, label: string = ""): void {
        const card = theHub().addCard(id, SENSOR_BUILTIN, label)
        for (let i = 0; i < sensorCards.length; i++) {
            if (sensorCards[i].id == id) {
                sensorCards[i] = card
                sensorKinds[i] = sensor
                return
            }
        }
        sensorCards.push(card)
        sensorKinds.push(sensor)
    }

    /** Add a gauge card (a number shown as a bar). Set it with "set card value". */
    //% block="add gauge card $id from $low to $high||label $label"
    //% id.defl="G1" low.defl=0 high.defl=100
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=84
    export function addGauge(id: string, low: number = 0, high: number = 100, label: string = ""): void {
        theHub().addCard(id, GAUGE, label).setRange(low, high)
    }

    /** Add a sound card: the dashboard plays the sounds this program asks for. */
    //% block="add sound card $id||label $label"
    //% id.defl="B1"
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=83
    export function addSound(id: string, label: string = ""): void {
        theHub().addCard(id, SOUND, label)
    }

    /** Add a joystick card (x and y from -100 to 100). */
    //% block="add joystick card $id||label $label"
    //% id.defl="J1"
    //% expandableArgumentMode="toggle" inlineInputMode=inline
    //% group="Setup" weight=82
    export function addJoystick(id: string, label: string = ""): void {
        theHub().addCard(id, JOYSTICK, label).text = "0,0"
    }

    // ------------------------------------------------------------- actions

    /** Run a motor from your program (-255..255). Ignored during an emergency stop. */
    //% block="run motor $motor at speed $speed"
    //% speed.min=-255 speed.max=255
    //% group="Actions" weight=80
    export function runMotor(motor: HubMotor, speed: number): void {
        const card = theHub().find("M" + (motor + 1))
        if (card) theHub().setNumber(card, speed)
        else if (!theHub().estopped) driveMotor(motor, Math.max(-255, Math.min(255, Math.round(speed))))
    }

    /** Move a servo from your program; its card limits still apply. */
    //% block="set servo $servo to $angle °"
    //% angle.min=0 angle.max=180 angle.defl=90
    //% group="Actions" weight=79
    export function setServo(servo: HubServo, angle: number): void {
        const card = theHub().find("S" + (servo + 1))
        if (card) theHub().setNumber(card, angle)
        else motionbit.setServoPosition(servoChannel(servo), Math.max(0, Math.min(180, angle)))
    }

    /** Set a number card (input, gauge, output ...). The dashboard is updated. */
    //% block="set card $id value to $value"
    //% id.defl="A1"
    //% group="Actions" weight=78
    export function setValue(id: string, value: number): void {
        const card = theHub().find(id)
        if (card) theHub().setNumber(card, value)
    }

    /** Show text on a text card. */
    //% block="set text card $id to $text"
    //% id.defl="T1"
    //% group="Actions" weight=77
    export function setText(id: string, text: string): void {
        const card = theHub().find(id)
        if (card) theHub().setText(card, text)
    }

    /** Ask the dashboard to play a sound. */
    //% block="play $sound on sound card $id $mode"
    //% id.defl="B1"
    //% group="Actions" weight=76
    export function playSound(id: string, sound: HubSound, mode: HubSoundMode): void {
        let name = "BEEP"
        if (sound == HubSound.Siren) name = "SIREN"
        else if (sound == HubSound.Chime) name = "CHIME"
        setText(id, "PLAY:" + name + ":" + (mode == HubSoundMode.Loop ? "LOOP" : "ONCE"))
    }

    /** Stop the sound on a sound card. */
    //% block="stop sound card $id"
    //% id.defl="B1"
    //% group="Actions" weight=75
    export function stopSound(id: string): void {
        setText(id, "STOP")
    }

    /** Write a line in the dashboard terminal. */
    //% block="log $text to dashboard"
    //% group="Actions" weight=74
    export function log(text: string): void {
        theHub().log(text)
    }

    // -------------------------------------------------------------- values

    /** The current value of a number card. */
    //% block="card $id value"
    //% id.defl="D1"
    //% group="Values" weight=70
    export function value(id: string): number {
        const card = theHub().find(id)
        return card && !card.isText() ? card.num : 0
    }

    /** The current text of a text card. */
    //% block="card $id text"
    //% id.defl="T2"
    //% group="Values" weight=69
    export function text(id: string): string {
        const card = theHub().find(id)
        return card && card.isText() ? card.text : ""
    }

    function joystickPart(id: string, index: number): number {
        const t = text(id)
        const comma = t.indexOf(",")
        if (comma < 0) return 0
        const part = index == 0 ? t.substr(0, comma) : t.substr(comma + 1)
        const parsed = parseNumber(part)
        return parsed[0] == 1 ? Math.max(-100, Math.min(100, parsed[1])) : 0
    }

    /** Joystick X (-100 left .. 100 right). */
    //% block="joystick $id x"
    //% id.defl="J1"
    //% group="Values" weight=68
    export function joystickX(id: string): number {
        return joystickPart(id, 0)
    }

    /** Joystick Y (-100 back .. 100 forward). */
    //% block="joystick $id y"
    //% id.defl="J1"
    //% group="Values" weight=67
    export function joystickY(id: string): number {
        return joystickPart(id, 1)
    }

    /** True while the dashboard's emergency stop is active. */
    //% block="emergency stop active"
    //% group="Values" weight=66
    export function isEstopped(): boolean {
        return theHub().estopped
    }

    /** True while the dashboard is connected (heartbeat in the last second). */
    //% block="dashboard connected"
    //% group="Values" weight=65
    export function isConnected(): boolean {
        const h = theHub()
        return h.lastHb >= 0 && control.millis() - h.lastHb <= h.watchdogMs
    }

    // -------------------------------------------------------------- events

    /** Runs when the dashboard changes a number card (slider, switch, button). */
    //% block="on card $id changed"
    //% id.defl="D1"
    //% draggableParameters="reporter"
    //% group="Events" weight=60
    export function onValueChanged(id: string, handler: (value: number) => void): void {
        valueIds.push(id)
        valueHandlers.push(handler)
    }

    /** Runs when text arrives from the dashboard on a text or joystick card. */
    //% block="on text received on card $id"
    //% id.defl="T2"
    //% draggableParameters="reporter"
    //% group="Events" weight=59
    export function onTextReceived(id: string, handler: (text: string) => void): void {
        textIds.push(id)
        textHandlers.push(handler)
    }

    /** Runs when the dashboard's emergency stop is pressed (motors are already off). */
    //% block="on emergency stop"
    //% group="Events" weight=58
    export function onEmergencyStop(handler: () => void): void {
        estopHandlers.push(handler)
    }
}
