"""Connection bar: transport picker, Connect button, link status and E-Stop."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtCore import Signal as QtSignal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from ..core.session import SessionState

#: Transports that are planned but not implemented yet (shown greyed out).
PLANNED_TRANSPORTS = ("USB serial (phase 4)", "Bluetooth (phase 5)")

_DOT = "●"
_STATE_TEXT = {
    SessionState.DISCONNECTED: "Disconnected",
    SessionState.CONNECTING: "Connecting…",
    SessionState.HANDSHAKE: "Handshake…",
    SessionState.SYNCING: "Loading cards…",
    SessionState.READY: "Connected",
}
_STOP_STYLE = (
    "QPushButton { background: #c0392b; color: white; font-weight: 700; font-size: 15px;"
    " border-radius: 6px; padding: 6px 18px; }"
    "QPushButton:disabled { background: #d9a19b; }"
)
_RESUME_STYLE = (
    "QPushButton { background: #27ae60; color: white; font-weight: 700; font-size: 15px;"
    " border-radius: 6px; padding: 6px 18px; }"
)


class ConnectionBar(QFrame):
    connectRequested = QtSignal(str)  # transport name
    disconnectRequested = QtSignal()
    estopRequested = QtSignal()
    resumeRequested = QtSignal()

    def __init__(self, transports: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = SessionState.DISCONNECTED
        self.estopped = False

        self.transport_box = QComboBox()
        self.transport_box.addItems(transports)
        model = self.transport_box.model()
        for name in PLANNED_TRANSPORTS:
            self.transport_box.addItem(name)
            if isinstance(model, QStandardItemModel):
                model.item(self.transport_box.count() - 1).setEnabled(False)

        self.connect_button = QPushButton("Connect")
        self.connect_button.setMinimumWidth(100)
        self.connect_button.clicked.connect(self._on_connect_clicked)

        self.dot = QLabel(_DOT)
        self.status_label = QLabel()
        self.latency_label = QLabel()
        self.latency_label.setMinimumWidth(70)

        self.estop_button = QPushButton()
        self.estop_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.estop_button.setMinimumHeight(36)
        self.estop_button.clicked.connect(self._on_estop_clicked)

        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Transport"))
        layout.addWidget(self.transport_box)
        layout.addWidget(self.connect_button)
        layout.addSpacing(16)
        layout.addWidget(self.dot)
        layout.addWidget(self.status_label)
        layout.addWidget(self.latency_label)
        layout.addStretch()
        layout.addWidget(self.estop_button)

        self.set_state(SessionState.DISCONNECTED)

    # ---------------------------------------------------------------- updates

    def set_state(self, state: SessionState) -> None:
        self.state = state
        busy = state not in (SessionState.DISCONNECTED, SessionState.READY)
        self.transport_box.setEnabled(state is SessionState.DISCONNECTED)
        self.connect_button.setEnabled(not busy)
        self.connect_button.setText("Disconnect" if state is SessionState.READY else "Connect")
        self.status_label.setText(_STATE_TEXT[state])
        if state is SessionState.READY:
            self._set_dot("#27ae60")
        elif busy:
            self._set_dot("#f1c40f")
        else:
            self._set_dot("#999999")
            self.set_latency(None)
            self.set_estopped(False)
        self._update_estop()

    def set_latency(self, ms: float | None) -> None:
        self.latency_label.setText("" if ms is None else f"{ms:.0f} ms")

    def set_link_ok(self, ok: bool) -> None:
        if self.state is not SessionState.READY:
            return
        self._set_dot("#27ae60" if ok else "#e67e22")
        self.status_label.setText("Connected" if ok else "Link lost — no data")

    def set_estopped(self, stopped: bool) -> None:
        self.estopped = stopped
        self._update_estop()

    # -------------------------------------------------------------- internals

    def _set_dot(self, colour: str) -> None:
        self.dot.setStyleSheet(f"color: {colour}; font-size: 18px;")

    def _update_estop(self) -> None:
        if self.estopped:
            self.estop_button.setText("▶ RESUME")
            self.estop_button.setToolTip("Clear the emergency stop")
            self.estop_button.setStyleSheet(_RESUME_STYLE)
        else:
            self.estop_button.setText("■ STOP  (Space)")
            self.estop_button.setToolTip("Emergency stop: all motors off (Space key)")
            self.estop_button.setStyleSheet(_STOP_STYLE)
        self.estop_button.setEnabled(self.state is SessionState.READY)

    def _on_connect_clicked(self) -> None:
        if self.state is SessionState.READY:
            self.disconnectRequested.emit()
        else:
            self.connectRequested.emit(self.transport_box.currentText())

    def _on_estop_clicked(self) -> None:
        if self.estopped:
            self.resumeRequested.emit()
        else:
            self.estopRequested.emit()
