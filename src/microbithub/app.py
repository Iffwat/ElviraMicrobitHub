"""Qt application with an asyncio event loop (via qasync).

The transports (bleak, pyserial-asyncio) and DeviceSession are asyncio-based,
so the Qt event loop and the asyncio loop must be the same loop. qasync makes
asyncio run on top of Qt's event loop: ``await`` works inside the GUI code.
"""

from __future__ import annotations

import asyncio
import sys

import qasync
from PySide6.QtWidgets import QApplication

from . import __version__
from .gui.main_window import MainWindow


def run_gui(argv: list[str] | None = None, *, quit_after: float | None = None) -> int:
    """Start the GUI and block until the last window closes.

    Args:
        quit_after: close automatically after this many seconds. It is scheduled
            as an asyncio task, so it also checks that asyncio runs inside Qt
            (used by the smoke test).
    """
    app = QApplication.instance() or QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName("MicrobitHub")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("MicrobitHub")

    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    closed = asyncio.Event()
    app.aboutToQuit.connect(closed.set)

    window = MainWindow()
    window.show()

    async def auto_quit(delay: float) -> None:
        await asyncio.sleep(delay)
        window.close()
        app.quit()

    with loop:
        if quit_after is not None:
            loop.create_task(auto_quit(quit_after))
        loop.run_until_complete(closed.wait())
    return 0
