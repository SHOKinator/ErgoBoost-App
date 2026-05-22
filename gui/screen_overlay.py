# gui/screen_overlay.py
"""
Fullscreen overlay that darkens the OS screen when posture violations persist.
Supports multi-monitor, countdown warning, and atexit crash safety.
"""

import atexit
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QFont

# Module-level list for atexit cleanup
_active_overlays = []


def _cleanup_overlays():
    for overlay in _active_overlays:
        try:
            overlay.hide()
        except Exception:
            pass
    _active_overlays.clear()


atexit.register(_cleanup_overlays)


class _SingleScreenOverlay(QWidget):
    """Overlay for a single screen."""

    def __init__(self, screen, alpha=150):
        super().__init__()
        self._screen = screen
        self._alpha = alpha
        self._countdown = 0  # 0 = no countdown, >0 = seconds remaining

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool |
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.text_label = QLabel("")
        self.text_label.setStyleSheet(
            "color: white; font-size: 56px; font-weight: bold; "
            "background-color: rgba(200, 50, 50, 180); "
            "border-radius: 20px; padding: 30px 50px;"
        )
        self.text_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.text_label, alignment=Qt.AlignCenter)

        # Countdown label (shown during warning phase)
        self.countdown_label = QLabel("")
        self.countdown_label.setFont(QFont("Segoe UI", 18))
        self.countdown_label.setStyleSheet(
            "color: rgba(255,255,255,200); background: transparent;"
        )
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.hide()
        layout.addWidget(self.countdown_label, alignment=Qt.AlignCenter)

    def _update_geometry(self):
        geo = self._screen.geometry()
        self.setGeometry(geo)

    def paintEvent(self, event):
        painter = QPainter(self)
        if self._countdown > 0:
            # Warning phase: lighter overlay
            painter.fillRect(self.rect(), QColor(0, 0, 0, 60))
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, self._alpha))

    def show_full(self, message):
        self._countdown = 0
        self._update_geometry()
        self.text_label.setText(message)
        self.text_label.show()
        self.countdown_label.hide()
        self.showFullScreen()
        self.update()

    def show_countdown(self, seconds_left):
        self._countdown = seconds_left
        self._update_geometry()
        self.text_label.hide()
        self.countdown_label.setText(f"⚠ Fix your posture! Overlay in {seconds_left}s...")
        self.countdown_label.show()
        self.showFullScreen()
        self.update()

    def hide_overlay(self):
        self._countdown = 0
        self.hide()


class ScreenBlurOverlay:
    """
    Multi-monitor overlay manager.
    Creates one overlay per screen, supports countdown and full modes.
    """

    def __init__(self, alpha=150):
        self._alpha = alpha
        self._overlays = []
        self._rebuild_overlays()
        _active_overlays.append(self)

    def _rebuild_overlays(self):
        """Create/recreate overlays for all current screens."""
        for ov in self._overlays:
            ov.hide()
            ov.deleteLater()
        self._overlays.clear()

        app = QApplication.instance()
        if app is None:
            return
        for screen in app.screens():
            ov = _SingleScreenOverlay(screen, self._alpha)
            self._overlays.append(ov)

    def show_overlay(self, message="Poor posture detected!"):
        """Show full dark overlay on all screens."""
        self._rebuild_overlays()
        for ov in self._overlays:
            ov.show_full(message)

    def show_countdown(self, seconds_left: int):
        """Show light warning countdown on all screens."""
        if not self._overlays:
            self._rebuild_overlays()
        for ov in self._overlays:
            ov.show_countdown(seconds_left)

    def hide_overlay(self):
        """Hide overlay on all screens."""
        for ov in self._overlays:
            ov.hide_overlay()

    def hide(self):
        """Alias for hide_overlay."""
        self.hide_overlay()
