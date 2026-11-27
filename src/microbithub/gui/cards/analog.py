"""Read-only numeric cards: Analog input (live chart) and Gauge (bar)."""

from __future__ import annotations

import time
from collections import deque

import numpy as np
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from ...core.model import Card, Scalar
from .base import CardWidget

#: Seconds of history shown in a chart.
CHART_SECONDS = 10.0
#: Chart redraw interval.
REDRAW_MS = 50


class AnalogInCard(CardWidget):
    """Big value label plus a scrolling pyqtgraph chart of the last seconds.

    The device sends changes only (with a deadband), so the chart keeps
    scrolling on a timer and extends the last value up to "now".
    """

    wide = True

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        self.samples: deque[tuple[float, float]] = deque(maxlen=2000)

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setMinimumWidth(90)
        self.value_label.setStyleSheet("font-size: 26px; font-weight: 600;")

        self.plot = pg.PlotWidget()
        self.plot.setBackground(self.palette().color(QPalette.ColorRole.Base))
        self.plot.setMenuEnabled(False)
        self.plot.setMouseEnabled(x=False, y=False)
        self.plot.hideButtons()
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.plot.setXRange(-CHART_SECONDS, 0, padding=0)
        if card.min is not None and card.max is not None and card.min < card.max:
            self.plot.setYRange(card.min, card.max, padding=0.05)
        self.curve = self.plot.plot(pen=pg.mkPen("#2f80ed", width=2))

        layout = QHBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self.plot, 1)

        self._timer = QTimer(self)
        self._timer.setInterval(REDRAW_MS)
        self._timer.timeout.connect(self.redraw)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        self.value_label.setText(str(value))
        if isinstance(value, int):
            self.samples.append((time.monotonic(), float(value)))

    def set_live(self, live: bool) -> None:
        super().set_live(live)
        if live:
            self._timer.start()
        else:
            self._timer.stop()

    def redraw(self) -> None:
        if not self.samples:
            return
        now = time.monotonic()
        while len(self.samples) > 1 and self.samples[1][0] < now - CHART_SECONDS:
            self.samples.popleft()
        data = np.array(self.samples)
        xs = np.append(data[:, 0] - now, 0.0)
        ys = np.append(data[:, 1], data[-1, 1])
        self.curve.setData(xs, ys)


class GaugeCard(CardWidget):
    """Read-only value shown as a big number and a bar."""

    def __init__(self, card: Card, parent: QWidget | None = None) -> None:
        super().__init__(card, parent)
        lo = card.min if card.min is not None else 0
        hi = card.max if card.max is not None else 1023

        self.value_label = QLabel()
        self.value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.value_label.setStyleSheet("font-size: 26px; font-weight: 600;")
        self.bar = QProgressBar()
        self.bar.setRange(lo, hi)
        self.bar.setTextVisible(False)
        self.range_label = QLabel(f"{lo} … {hi}")
        self.range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.range_label.setStyleSheet("color: palette(mid); font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.addWidget(self.value_label)
        layout.addWidget(self.bar)
        layout.addWidget(self.range_label)
        self.show_value(card.value)

    def show_value(self, value: Scalar) -> None:
        self.value_label.setText(str(value))
        if isinstance(value, int):
            self.bar.setValue(max(self.bar.minimum(), min(self.bar.maximum(), value)))
