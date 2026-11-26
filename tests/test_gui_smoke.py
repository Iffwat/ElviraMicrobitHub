"""GUI smoke tests. They run headless with Qt's offscreen platform."""

import os
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from microbithub.gui.main_window import MainWindow  # noqa: E402


def test_main_window_builds():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    assert window.windowTitle() == "MicrobitHub"
    assert window.status_label.text() == "Disconnected"
    window.close()
    app.processEvents()


def test_app_starts_and_quits_with_asyncio_loop():
    # Runs in a subprocess so the qasync event loop does not affect pytest-asyncio.
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen"}
    result = subprocess.run(
        [sys.executable, "-m", "microbithub", "--quit-after", "0.3"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
