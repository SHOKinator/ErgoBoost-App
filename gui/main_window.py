# gui/main_window.py
"""
ErgoBoost - Main GUI Application
PySide6 Frontend with professional dark design
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QIcon, QFont

from gui.dashboard_tab import DashboardTab
from gui.sessions_tab import SessionsTab
from gui.statistics_tab import StatisticsTab
from gui.exercises_tab import ExercisesTab
from gui.settings_tab import SettingsTab
from gui.monitoring_worker import MonitoringWorker
from gui.screen_overlay import ScreenBlurOverlay

from config.settings import Settings
from utils.logger import setup_logger

logger = setup_logger(__name__)

STYLESHEET = """
* {
    font-family: 'Segoe UI', 'SF Pro Display', sans-serif;
}

QMainWindow {
    background-color: #0f0f14;
}

QTabWidget::pane {
    border: none;
    background-color: #0f0f14;
}

QTabBar::tab {
    background-color: #16161e;
    color: #8a8a9a;
    padding: 10px 28px;
    margin-right: 1px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 13px;
    font-weight: 500;
    letter-spacing: 0.3px;
}

QTabBar::tab:selected {
    background-color: #1a1a24;
    color: #e0e0ee;
    border-bottom: 2px solid #6c8cff;
}

QTabBar::tab:hover:!selected {
    background-color: #1c1c28;
    color: #b0b0c0;
}

QWidget {
    background-color: #0f0f14;
    color: #c8c8d8;
}

QPushButton {
    background-color: #2a2a3a;
    color: #d0d0e0;
    border: 1px solid #3a3a4a;
    border-radius: 4px;
    padding: 8px 18px;
    font-size: 13px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #35354a;
    border-color: #6c8cff;
}

QPushButton:pressed {
    background-color: #252538;
}

QPushButton:disabled {
    background-color: #1a1a24;
    color: #4a4a5a;
    border-color: #252530;
}

QPushButton[class="primary"] {
    background-color: #4a6adf;
    color: #ffffff;
    border: none;
}

QPushButton[class="primary"]:hover {
    background-color: #5a7aef;
}

QPushButton[class="danger"] {
    background-color: #c04050;
    color: #ffffff;
    border: none;
}

QPushButton[class="danger"]:hover {
    background-color: #d05060;
}

QPushButton[class="success"] {
    background-color: #3a8a5a;
    color: #ffffff;
    border: none;
}

QPushButton[class="success"]:hover {
    background-color: #4a9a6a;
}

QPushButton[class="warning"] {
    background-color: #b08030;
    color: #ffffff;
    border: none;
}

QPushButton[class="warning"]:hover {
    background-color: #c09040;
}

QLabel {
    color: #c8c8d8;
    background: transparent;
}

QFrame {
    background-color: #16161e;
    border-radius: 4px;
    border: none;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: #16161e;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: #3a3a4a;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4a4a5a;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QComboBox {
    background-color: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    padding: 6px 12px;
    color: #c8c8d8;
    min-height: 20px;
}

QComboBox:hover {
    border-color: #6c8cff;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1a1a24;
    border: 1px solid #2a2a3a;
    selection-background-color: #4a6adf;
    color: #c8c8d8;
}

QCheckBox {
    spacing: 8px;
    color: #c8c8d8;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 3px;
    border: 1px solid #3a3a4a;
    background-color: #1a1a24;
}

QCheckBox::indicator:checked {
    background-color: #4a6adf;
    border-color: #4a6adf;
}

QCheckBox::indicator:hover {
    border-color: #6c8cff;
}

QSlider::groove:horizontal {
    height: 4px;
    background-color: #2a2a3a;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #6c8cff;
    width: 14px;
    height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background-color: #8cacff;
}

QTableWidget {
    background-color: #16161e;
    border: none;
    gridline-color: #1e1e2a;
    alternate-background-color: #1a1a24;
}

QTableWidget::item {
    padding: 8px;
    color: #c8c8d8;
    border: none;
}

QTableWidget::item:selected {
    background-color: #2a3a5a;
    color: #e0e0ee;
}

QHeaderView::section {
    background-color: #16161e;
    color: #8a8a9a;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #2a2a3a;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}

QStatusBar {
    background-color: #16161e;
    color: #6a6a7a;
    border-top: 1px solid #1e1e2a;
    font-size: 12px;
}

QGroupBox {
    background-color: #16161e;
    border: 1px solid #1e1e2a;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 18px;
    font-weight: 600;
    color: #a0a0b0;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #8a8a9a;
}

QProgressBar {
    border: 1px solid #2a2a3a;
    border-radius: 3px;
    text-align: center;
    background-color: #1a1a24;
    color: #c8c8d8;
    height: 22px;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #4a6adf;
    border-radius: 2px;
}
"""


class ErgoBoostMainWindow(QMainWindow):
    # Signal to request sign out (app.py will restart auth flow)
    sign_out_requested = None  # set by app.py

    def __init__(self, user: dict, auth_service=None):
        super().__init__()
        self.user = user
        self.user_id = user['id']
        self.auth_service = auth_service
        self.settings = Settings()
        self._init_ui()
        self.monitoring_worker = None
        self.monitoring_thread = None
        self.screen_overlay = ScreenBlurOverlay()
        logger.info(f"ErgoBoost GUI initialized for user {user['username']}")

    def _init_ui(self):
        self.setWindowTitle(f"ErgoBoost — {self.user.get('display_name', self.user['username'])}")
        self.setMinimumSize(1280, 800)

        icon_path = Path("assets/icons/app_icon.png")
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # User header bar
        header = QWidget()
        header.setStyleSheet("background-color: #16161e; border-bottom: 1px solid #1e1e2a;")
        header.setFixedHeight(36)
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(16, 0, 16, 0)
        h_layout.setSpacing(8)
        h_layout.addStretch()

        user_label = QLabel(f"{self.user.get('display_name', self.user['username'])}")
        user_label.setStyleSheet("color: #8a8a9a; font-size: 12px; background: transparent; border: none;")
        h_layout.addWidget(user_label)

        sign_out_btn = QPushButton("Sign Out")
        sign_out_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6c8cff; border: none; "
            "font-size: 11px; padding: 4px 8px; } "
            "QPushButton:hover { color: #8cacff; }"
        )
        sign_out_btn.clicked.connect(self._on_sign_out)
        h_layout.addWidget(sign_out_btn)
        main_layout.addWidget(header)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setDocumentMode(True)

        self.setStyleSheet(STYLESHEET)

        self.dashboard_tab = DashboardTab(self.settings)
        self.sessions_tab = SessionsTab(self.settings, user_id=self.user_id)
        self.statistics_tab = StatisticsTab(self.settings, user_id=self.user_id)
        self.exercises_tab = ExercisesTab(self.settings)
        self.settings_tab = SettingsTab(self.settings)

        self.tab_widget.addTab(self.dashboard_tab, "Dashboard")
        self.tab_widget.addTab(self.sessions_tab, "Sessions")
        self.tab_widget.addTab(self.statistics_tab, "Statistics")
        self.tab_widget.addTab(self.exercises_tab, "Exercises")
        self.tab_widget.addTab(self.settings_tab, "Settings")

        main_layout.addWidget(self.tab_widget)
        self._connect_signals()
        self.statusBar().showMessage("Ready")

    def _connect_signals(self):
        self.dashboard_tab.monitoring_started.connect(self.start_monitoring)
        self.dashboard_tab.monitoring_stopped.connect(self.stop_monitoring)
        self.dashboard_tab.monitoring_paused.connect(self.pause_monitoring)
        self.settings_tab.settings_changed.connect(self.on_settings_changed)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    def start_monitoring(self):
        if self.monitoring_worker is not None:
            return
        try:
            self.monitoring_thread = QThread()
            self.monitoring_worker = MonitoringWorker(self.settings, user_id=self.user_id)
            self.monitoring_worker.moveToThread(self.monitoring_thread)

            self.monitoring_worker.frame_ready.connect(self.dashboard_tab.update_camera_frame)
            self.monitoring_worker.metrics_updated.connect(self.dashboard_tab.update_metrics)
            self.monitoring_worker.alert_triggered.connect(self.dashboard_tab.show_alert)
            self.monitoring_worker.calibration_progress.connect(self.dashboard_tab.update_calibration_progress)
            self.monitoring_worker.error_occurred.connect(self.on_monitoring_error)
            self.monitoring_worker.overlay_requested.connect(self._on_overlay_requested)

            self.monitoring_thread.started.connect(self.monitoring_worker.run)
            self.monitoring_worker.finished.connect(self.monitoring_thread.quit)
            self.monitoring_worker.finished.connect(self.on_monitoring_finished)

            self.monitoring_thread.start()
            self.statusBar().showMessage("Monitoring active")
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to start monitoring:\n{str(e)}")

    def stop_monitoring(self):
        if self.monitoring_worker is None:
            return
        self.monitoring_worker.stop()
        self.statusBar().showMessage("Stopping...")

    def pause_monitoring(self, paused):
        if self.monitoring_worker is None:
            return
        self.monitoring_worker.set_paused(paused)
        self.statusBar().showMessage("Paused" if paused else "Monitoring active")

    def on_monitoring_finished(self):
        if self.monitoring_thread:
            self.monitoring_thread.quit()
            self.monitoring_thread.wait()
        self.monitoring_worker = None
        self.monitoring_thread = None
        self.sessions_tab.refresh_sessions()
        self.statusBar().showMessage("Stopped")

    def on_monitoring_error(self, error_msg):
        QMessageBox.warning(self, "Monitoring Error", error_msg)

    def _on_overlay_requested(self, show: bool, message: str):
        if show:
            self.screen_overlay.show_overlay(message)
        else:
            self.screen_overlay.hide_overlay()

    def on_settings_changed(self):
        if self.monitoring_worker:
            self.monitoring_worker.update_settings(self.settings)
        self.statusBar().showMessage("Settings updated")

    def on_tab_changed(self, index):
        tab_name = self.tab_widget.tabText(index)
        if "Sessions" in tab_name:
            self.sessions_tab.refresh_sessions()
        elif "Statistics" in tab_name:
            self.statistics_tab.refresh_statistics()

    def _on_sign_out(self):
        """Handle sign out"""
        if self.monitoring_worker is not None:
            QMessageBox.warning(self, "Cannot Sign Out",
                "Stop monitoring first before signing out.")
            return
        if self.auth_service:
            self.auth_service.sign_out()
        self.screen_overlay.hide_overlay()
        self.close()
        # Signal to app that we want to restart auth
        if self.sign_out_requested:
            self.sign_out_requested()

    def closeEvent(self, event):
        if self.monitoring_worker is not None:
            reply = QMessageBox.question(
                self, "Confirm Exit",
                "Monitoring is active. Exit?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.stop_monitoring()
                if self.monitoring_thread:
                    self.monitoring_thread.quit()
                    self.monitoring_thread.wait(2000)
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()


def main():
    """Main entry point with auth flow"""
    app = QApplication(sys.argv)
    app.setApplicationName("ErgoBoost")
    app.setOrganizationName("ErgoBoost")
    app.setApplicationVersion("1.0.0")

    from gui.auth_window import AuthWindow

    # Keep reference to prevent garbage collection
    app._main_window = None

    def run_auth():
        # Close existing window if sign out
        if app._main_window is not None:
            app._main_window.close()
            app._main_window = None

        auth_win = AuthWindow()
        result = auth_win.exec()

        if result == AuthWindow.Accepted and auth_win.get_user():
            user = auth_win.get_user()
            auth_service = auth_win.get_auth_service()

            window = ErgoBoostMainWindow(user=user, auth_service=auth_service)
            window.sign_out_requested = run_auth
            window.show()
            app._main_window = window  # prevent GC
        else:
            app.quit()

    run_auth()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
