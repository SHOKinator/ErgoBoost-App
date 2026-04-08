# gui/screen_overlay.py
import sys
from PySide6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor

class ScreenBlurOverlay(QWidget):
    """
    A fullscreen transparency overlay that darkens the screen 
    and shows a warning message.
    """
    def __init__(self, alpha=150):
        super().__init__()
        # Frameless, stays on top, tool window (no taskbar icon), clicks pass through
        self.setWindowFlags(
            Qt.FramelessWindowHint | 
            Qt.WindowStaysOnTopHint | 
            Qt.Tool | 
            Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self._alpha = alpha
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_label = QLabel("Нарушение осанки!")
        self.text_label.setStyleSheet(
            "color: white; font-size: 64px; font-weight: bold; "
            "background-color: rgba(200, 50, 50, 180); "
            "border-radius: 20px; padding: 40px;"
        )
        self.text_label.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(self.text_label, alignment=Qt.AlignCenter)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._alpha))

    def show_overlay(self, message="Нарушение осанки!"):
        self.text_label.setText(message)
        self.showFullScreen()
        
    def hide_overlay(self):
        self.hide()
