# utils/chart_utils.py
"""
Shared chart utilities for ErgoBoost GUI.
"""

import numpy as np
from PySide6.QtGui import QImage, QPixmap
from matplotlib.backends.backend_agg import FigureCanvasAgg

# Shared chart color palette
BG = '#0f0f14'
CARD_BG = '#16161e'
GRID = '#1e1e2a'
TEXT = '#8a8a9a'
BLUE = '#6c8cff'
GREEN = '#5a9a6a'
RED = '#c04050'
ORANGE = '#b08030'


def fig_to_pixmap(fig):
    """Convert a matplotlib figure to a QPixmap."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = canvas.buffer_rgba()
    arr = np.asarray(buf)
    h, w, ch = arr.shape
    qimg = QImage(arr.data, w, h, ch * w, QImage.Format_RGBA8888)
    return QPixmap.fromImage(qimg)


def style_axis(ax):
    """Apply dark theme styling to a matplotlib axis."""
    ax.set_facecolor(BG)
    ax.tick_params(colors=TEXT, labelsize=8)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_color(GRID)
    ax.spines['left'].set_color(GRID)
