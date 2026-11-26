"""Main window (phase 0 shell; filled in during phase 2)."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QLabel, QMainWindow, QMessageBox

from .. import __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MicrobitHub")
        self.resize(1100, 720)
        self.setMinimumSize(640, 420)

        placeholder = QLabel("No device connected\n\nThe dashboard arrives in phase 2.")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setObjectName("placeholder")
        placeholder.setStyleSheet("color: palette(mid); font-size: 16px;")
        self.setCentralWidget(placeholder)

        self.status_label = QLabel("Disconnected")
        self.statusBar().addWidget(self.status_label)
        self.statusBar().addPermanentWidget(QLabel(f"v{__version__}"))

        self._build_menus()

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("&Help")
        about_action = QAction("&About MicrobitHub", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About MicrobitHub",
            f"<b>MicrobitHub</b> v{__version__}<br>Dashboard for micro:bit + Motion:bit robots.",
        )
