"""Sound card: the micro:bit asks the PC to play a sound.

Values: ``PLAY:<NAME>[:ONCE|LOOP]`` or ``STOP`` (empty also means stop).
Bundled sound files arrive in phase 6; until then every sound is the system
beep (once, or once per second while looping).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...core.model import Card, Scalar
from .base import CardWidget

LOOP_INTERVAL_MS = 1000


@dataclass(frozen=True)
class SoundCommand:
    action: str  # "PLAY" or "STOP"
    name: str = ""
    loop: bool = False


def parse_sound(value: object) -> SoundCommand | None:
    """Parse a SOUND card value. Returns None for values it does not understand."""
    text = str(value).strip().upper()
    if text in ("", "STOP"):
        return SoundCommand("STOP")
    parts = text.split(":")
    if parts[0] != "PLAY" or len(parts) < 2 or not parts[1]:
        return None
    mode = parts[2] if len(parts) > 2 else "ONCE"
    if mode not in ("ONCE", "LOOP"):
        return None
    return SoundCommand("PLAY", parts[1], mode == "LOOP")


class SoundCard(CardWidget):
    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        #: Plays one sound; replaced in tests. Phase 6 swaps in real sound files.
        self.player: Callable[[str], None] = lambda _name: QApplication.beep()
        self.playing: SoundCommand | None = None
        self.play_count = 0

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        self.status_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        self.mute = QCheckBox("Mute")
        self.mute.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.mute.toggled.connect(lambda on: on and self.stop())
        self.stop_button = QPushButton("Stop sound")
        self.stop_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.stop_button.clicked.connect(self.stop)

        row = QHBoxLayout()
        row.addWidget(self.mute)
        row.addStretch()
        row.addWidget(self.stop_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.status_label)
        layout.addLayout(row)

        self._loop_timer = QTimer(self)
        self._loop_timer.setInterval(LOOP_INTERVAL_MS)
        self._loop_timer.timeout.connect(self._play_once)
        self._show_status()

    def update_card(self, card: Card) -> None:
        # Every VAL is a command (the same "PLAY:CHIME:ONCE" can arrive twice),
        # so handle it even when the value did not change.
        self.card = card
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        cmd = parse_sound(value)
        if cmd is None:
            self.status_label.setText(f"? {value}")
            return
        if cmd.action == "STOP":
            self.stop()
            return
        if self.mute.isChecked():
            self.stop()
            self.status_label.setText(f"♪ {cmd.name} (muted)")
            return
        self._loop_timer.stop()
        self.playing = cmd
        self._play_once()
        if cmd.loop:
            self._loop_timer.start()
            self._show_status()
        else:
            self.playing = None
            self.status_label.setText(f"♪ {cmd.name} (once)")

    def stop(self) -> None:
        self._loop_timer.stop()
        self.playing = None
        self._show_status()

    def set_live(self, live: bool) -> None:
        super().set_live(live)
        if not live:
            self.stop()

    def _play_once(self) -> None:
        if self.mute.isChecked():
            self.stop()
            return
        self.play_count += 1
        self.player(self.playing.name if self.playing else "")

    def _show_status(self) -> None:
        if self.playing is not None and self.playing.loop:
            self.status_label.setText(f"♪ {self.playing.name} (looping)")
        else:
            self.status_label.setText("silent")
