"""Terminal panel: LOG lines, events, errors and app messages with timestamps."""

from __future__ import annotations

import html
import time

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

MAX_LINES = 2000

#: kind -> (tag, colour). ``None`` uses the normal text colour.
KINDS: dict[str, tuple[str, str | None]] = {
    "info": ("APP", "#808080"),
    "log": ("LOG", None),
    "event": ("EVT", "#2f80ed"),
    "warning": ("WARN", "#e67e22"),
    "error": ("ERR", "#e74c3c"),
}


class Terminal(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = QPlainTextEdit()
        self.view.setReadOnly(True)
        self.view.setMaximumBlockCount(MAX_LINES)
        self.view.setFont(QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont))
        self.view.setPlaceholderText("Messages from the micro:bit appear here.")

        clear = QPushButton("Clear")
        clear.clicked.connect(self.clear)
        header = QHBoxLayout()
        header.addWidget(QLabel("<b>Terminal</b>"))
        header.addStretch()
        header.addWidget(clear)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.view)

    def append(self, kind: str, text: str) -> None:
        tag, colour = KINDS.get(kind, KINDS["info"])
        stamp = time.strftime("%H:%M:%S")
        body = html.escape(text)
        style = f' style="color:{colour}"' if colour else ""
        self.view.appendHtml(
            f'<span style="color:#808080">{stamp}</span> <b{style}>{tag:<4}</b> '
            f"<span{style}>{body}</span>"
        )

    def info(self, text: str) -> None:
        self.append("info", text)

    def log(self, text: str) -> None:
        self.append("log", text)

    def device_event(self, name: str) -> None:
        self.append("event", name)

    def warning(self, text: str) -> None:
        self.append("warning", text)

    def error(self, text: str) -> None:
        self.append("error", text)

    def clear(self) -> None:
        self.view.clear()

    def lines(self) -> list[str]:
        """Plain text of every line (used by tests)."""
        return self.view.toPlainText().splitlines()
