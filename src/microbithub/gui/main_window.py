"""Main window: connection bar, card grid and terminal, wired to a DeviceSession."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Coroutine
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox, QSplitter, QVBoxLayout, QWidget

from .. import __version__
from ..core.model import CardType
from ..core.session import DeviceSession, SessionState
from ..transport.base import Transport
from ..transport.sim import SimTransport
from .bridge import SessionBridge
from .card_grid import CardGrid
from .cards import CardWidget
from .connection_bar import ConnectionBar
from .terminal import Terminal

TransportFactory = Callable[[], Transport]


def default_transports() -> dict[str, TransportFactory]:
    return {"Simulator": lambda: SimTransport(latency=0.02)}


class MainWindow(QMainWindow):
    """The dashboard.

    Args:
        transports: name -> factory creating a new transport for each connect.
            Defaults to the simulator only (USB and BLE arrive in phases 4 and 5).
        session_options: extra keyword arguments for :class:`DeviceSession`
            (tests use shorter timeouts).
    """

    def __init__(
        self,
        transports: dict[str, TransportFactory] | None = None,
        session_options: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("MicrobitHub")
        self.resize(1100, 720)
        self.setMinimumSize(640, 420)

        self.transports = transports if transports is not None else default_transports()
        self.session_options = session_options or {}
        self.session: DeviceSession | None = None
        self._tasks: set[asyncio.Task] = set()
        self._closing = False

        self.bridge = SessionBridge(self)
        self.connection_bar = ConnectionBar(list(self.transports))
        self.grid = CardGrid()
        self.terminal = Terminal()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.grid)
        splitter.addWidget(self.terminal)
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([520, 160])

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.addWidget(self.connection_bar)
        layout.addWidget(splitter, 1)
        self.setCentralWidget(central)

        self.status_label = QLabel("Disconnected")
        self.statusBar().addWidget(self.status_label)
        self.statusBar().addPermanentWidget(QLabel(f"v{__version__}"))

        # Space = emergency stop anywhere in the window. Text boxes keep Space for
        # typing (Qt gives a focused QLineEdit priority over shortcuts).
        self.estop_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        self.estop_shortcut.setContext(Qt.ShortcutContext.WindowShortcut)
        self.estop_shortcut.activated.connect(self.request_estop)

        self._build_menus()
        self._wire()

    # ------------------------------------------------------------------ setup

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        view_menu = self.menuBar().addMenu("&View")
        clear_action = QAction("&Clear terminal", self)
        clear_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_action.triggered.connect(self.terminal.clear)
        view_menu.addAction(clear_action)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About MicrobitHub", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _wire(self) -> None:
        bar, bridge = self.connection_bar, self.bridge
        bar.connectRequested.connect(self.request_connect)
        bar.disconnectRequested.connect(self.request_disconnect)
        bar.estopRequested.connect(self.request_estop)
        bar.resumeRequested.connect(self.request_resume)
        self.grid.valueRequested.connect(self._on_value_requested)

        bridge.stateChanged.connect(self._on_state)
        bridge.cardsCleared.connect(self.grid.clear)
        bridge.cardAdded.connect(self.grid.add_card)
        bridge.valueChanged.connect(self.grid.update_value)
        bridge.logReceived.connect(self.terminal.log)
        bridge.eventReceived.connect(self._on_event)
        bridge.latencyUpdated.connect(bar.set_latency)
        bridge.linkLost.connect(self._on_link_lost)
        bridge.linkRestored.connect(self._on_link_restored)
        bridge.error.connect(self.terminal.error)

    # ---------------------------------------------------------------- actions

    def request_connect(self, transport_name: str) -> None:
        if self.session is not None and self.session.state is not SessionState.DISCONNECTED:
            return
        factory = self.transports.get(transport_name)
        if factory is None:
            self.terminal.error(f"Transport {transport_name!r} is not available yet")
            return
        self.spawn(self.connect_device(transport_name, factory), "Connect")

    def request_disconnect(self) -> None:
        self.spawn(self.disconnect_device(), "Disconnect")

    def request_estop(self) -> None:
        session = self.session
        if session is None or not session.is_ready:
            return
        self.terminal.warning("EMERGENCY STOP sent")
        self.spawn(session.estop(), "E-Stop")

    def request_resume(self) -> None:
        session = self.session
        if session is None or not session.is_ready:
            return
        self.terminal.info("Resume sent")
        self.spawn(session.resume(), "Resume")

    async def connect_device(self, name: str, factory: TransportFactory) -> bool:
        self.terminal.info(f"Connecting via {name}…")
        try:
            session = DeviceSession(factory(), **self.session_options)
            self.session = session
            self.bridge.attach(session)
            await session.connect()
        except Exception as exc:  # noqa: BLE001 - shown to the user
            self.terminal.error(f"Connect failed: {exc}")
            return False
        info = session.device_info
        if info is not None:
            self.terminal.info(
                f"Connected to {info.name} (firmware {info.firmware}), {len(session.cards)} cards"
            )
        return True

    async def disconnect_device(self) -> None:
        session = self.session
        if session is None or session.state is SessionState.DISCONNECTED:
            return
        if session.is_ready:
            # Stop the motors right away instead of waiting for the watchdog.
            for card in list(session.cards.values()):
                if card.type is CardType.MOTOR and card.value != 0:
                    try:
                        await session.set_value(card.id, 0, wait_ack=False)
                    except Exception:  # noqa: BLE001 - disconnecting anyway
                        break
        await session.disconnect()
        self.terminal.info("Disconnected")

    def spawn(self, coro: Coroutine[Any, Any, Any], what: str) -> asyncio.Task:
        """Run a coroutine on the asyncio loop; errors go to the terminal."""
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)

        def done(t: asyncio.Task) -> None:
            self._tasks.discard(t)
            if not t.cancelled() and t.exception() is not None:
                self.terminal.error(f"{what} failed: {t.exception()}")

        task.add_done_callback(done)
        return task

    # --------------------------------------------------------------- handlers

    def _on_value_requested(self, card_id: str, value: object, wait_ack: bool) -> None:
        session = self.session
        if session is None or not session.is_ready:
            return
        self.spawn(session.set_value(card_id, value, wait_ack=wait_ack), f"Set {card_id}")

    def _on_state(self, state: SessionState) -> None:
        self.connection_bar.set_state(state)
        self.grid.set_live(state is SessionState.READY)
        session = self.session
        if state is SessionState.READY and session is not None and session.device_info:
            info = session.device_info
            self.status_label.setText(
                f"Connected to {info.name} · firmware {info.firmware} · {len(session.cards)} cards"
            )
        else:
            self.status_label.setText(self.connection_bar.status_label.text())

    def _on_event(self, name: str) -> None:
        self.terminal.device_event(name)
        if name == "ESTOP":
            self.connection_bar.set_estopped(True)
        elif name == "RESUME":
            self.connection_bar.set_estopped(False)
        elif name == "WATCHDOG":
            self.terminal.warning("Watchdog: the micro:bit stopped the motors (no heartbeat)")

    def _on_link_lost(self) -> None:
        self.connection_bar.set_link_ok(False)
        self.terminal.warning("Link lost: no data from the micro:bit")

    def _on_link_restored(self) -> None:
        self.connection_bar.set_link_ok(True)
        self.terminal.info("Link restored")

    # ------------------------------------------------------------------ misc

    def card_widget(self, card_id: str) -> CardWidget:
        """The widget for ``card_id`` (used by tests)."""
        return self.grid.widgets[card_id]

    def closeEvent(self, event: QCloseEvent) -> None:
        session = self.session
        if session is not None and session.state is not SessionState.DISCONNECTED:
            if not self._closing:
                # Disconnect cleanly (motors to 0), then close for real.
                self._closing = True
                event.ignore()
                task = self.spawn(self.disconnect_device(), "Disconnect")
                task.add_done_callback(lambda _t: self.close())
                return
        self.bridge.detach()
        super().closeEvent(event)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About MicrobitHub",
            f"<b>MicrobitHub</b> v{__version__}<br>Dashboard for micro:bit + Motion:bit robots.",
        )
