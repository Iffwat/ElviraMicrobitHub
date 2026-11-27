# MicrobitHub (MakeCode extension)

Connects a micro:bit + Cytron **Motion:bit** robot to the MicrobitHub desktop
dashboard over **USB serial** or **Bluetooth UART**.

* Cards declared in your program appear on the dashboard automatically.
* **Safety:** motors stop 1 second after the dashboard goes silent (watchdog),
  stop immediately on the dashboard's **STOP** button (Space key), and stop when
  the Bluetooth link drops. Servo and motor limits are enforced on the micro:bit.

## Add it to a project

1. Open <https://makecode.microbit.org> → **New Project**.
2. **Extensions** → paste the URL of this folder on GitHub, e.g.
   `https://github.com/Iffwat/ElviraMicrobitHub/firmware/makecode`
   (or copy `pxt.json`, `protocol.ts`, `hub.ts` and `main.ts` into the project in
   JavaScript mode, then add the `bluetooth` and
   `github:cytrontechnologies/pxt-motionbit` extensions).
3. Project settings (gear icon) → **No Pairing Required** for Bluetooth.
   (The extension asks for this too, but check it on older editors.)

Adding this extension removes the **radio** blocks: Bluetooth and radio cannot
be used together on the micro:bit.

## Example

```blocks
microbithub.addMotor(HubMotor.M1, "Left wheel")
microbithub.addMotor(HubMotor.M2, "Right wheel")
microbithub.addServo(HubServo.S1, "Gripper", 90, 20, 160, 5)
microbithub.addInput(HubInputKind.Analog, "A1", HubPin.P0, "Light sensor")
microbithub.addOutput(HubOutputKind.Digital, "D2", HubPin.P12, "Headlight")
microbithub.addText("T2", HubTextDirection.FromDashboard, "Message")
microbithub.start()

microbithub.onTextReceived("T2", function (text) {
    basic.showString(text)
})
```

Declare the cards, then call **start MicrobitHub**. Cards can also be added
later; the dashboard sees them on its next connect.

## Blocks

| Group | Blocks |
|-------|--------|
| Setup | start · add motor / servo / input / output / text / sensor / gauge / sound / joystick card |
| Actions | run motor · set servo · set card value · set text card · play / stop sound · log to dashboard |
| Values | card value · card text · joystick x / y · emergency stop active · dashboard connected |
| Events | on card changed · on text received · on emergency stop |

* **Input cards** linked to a pin are read 20 times per second; changes are
  sent (analog changes of 5 or less are skipped to save bandwidth).
* **Output cards** linked to a pin follow the dashboard: digital on/off, PWM,
  or a push button (1 while held).
* **Sensor cards** send temperature, light level, compass heading or
  acceleration automatically. The compass asks for calibration on first use.

## Protocol

Text lines, protocol v2, the same over USB (115200 baud) and Bluetooth UART.
Type them in a serial monitor to test without the dashboard:

```
HELLO:2        →  HELLO:2,MicrobitHub-<name>,0.1.0
SYNC           →  CARD:… lines, then SYNCED:<count>
SET:M1:120     →  ACK:M1
ESTOP          →  VAL:M1:0, EVT:ESTOP
```

Full message list: `docs/phases/phase-1-core-simulator.md` in the MicrobitHub repository.
