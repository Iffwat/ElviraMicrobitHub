// Example robot program, also compiled by `pxt build` to check the blocks.
// It declares the same cards as the simulator's demo robot (demo_cards()).

microbithub.addMotor(HubMotor.M1, "Left wheel")
microbithub.addMotor(HubMotor.M2, "Right wheel")
microbithub.addServo(HubServo.S1, "Gripper", 90, 20, 160, 5)
microbithub.addInput(HubInputKind.Analog, "A1", HubPin.P0, "Light sensor")
microbithub.addInput(HubInputKind.Digital, "D1", HubPin.P1, "Bumper")
microbithub.addOutput(HubOutputKind.Digital, "D2", HubPin.P12, "Headlight")
microbithub.addText("T1", HubTextDirection.ToDashboard, "Status")
microbithub.addText("T2", HubTextDirection.FromDashboard, "Message")
microbithub.addSound("B1", "Alarm")
microbithub.start()

microbithub.onTextReceived("T2", function (text) {
    basic.showString(text)
})
microbithub.onEmergencyStop(function () {
    basic.showIcon(IconNames.No)
})

let bumper = 0
basic.forever(function () {
    microbithub.setText("T1", "uptime " + Math.idiv(control.millis(), 1000) + "s")
    const pressed = microbithub.value("D1")
    if (pressed == 1 && bumper == 0) {
        microbithub.playSound("B1", HubSound.Chime, HubSoundMode.Once)
    }
    bumper = pressed
    basic.pause(200)
})
