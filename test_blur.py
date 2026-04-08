import sys
from PySide6.QtWidgets import QApplication, QWidget
from PySide6.QtCore import Qt, QTimer, Signal, QObject
from PySide6.QtGui import QPainter, QColor\

class BlurOverlay(QWidget):
    def __init__(self, alpha=150):
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(QApplication.primaryScreen().geometry())
        self._alpha = alpha

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, self._alpha))

    def show_blur(self):
        self.showFullScreen()

    def hide_blur(self):
        self.hide()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = BlurOverlay()
    w.show()
    # Close after 4 seconds for testing
    QTimer.singleShot(4000, app.quit)
    sys.exit(app.exec())
