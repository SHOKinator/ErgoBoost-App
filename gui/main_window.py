# gui/main_window.py
"""
ErgoBoost - Main GUI Application
PySide6 Frontend with professional dark design.
Features: system tray, hotkeys, DND, auto-start, overlay countdown.
"""

import sys
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTabWidget, QLabel, QPushButton, QMessageBox, QMenu, QSystemTrayIcon
)
from PySide6.QtCore import Qt, QThread, QTimer
from PySide6.QtGui import QIcon, QFont, QKeySequence, QShortcut, QAction

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

QKeySequenceEdit {
    background-color: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #c8c8d8;
}

QMenu {
    background-color: #1a1a24;
    border: 1px solid #2a2a3a;
    color: #c8c8d8;
    padding: 4px;
}

QMenu::item {
    padding: 6px 24px;
    border-radius: 3px;
}

QMenu::item:selected {
    background-color: #4a6adf;
}

QMenu::separator {
    height: 1px;
    background: #2a2a3a;
    margin: 4px 8px;
}

QSpinBox {
    background-color: #1a1a24;
    border: 1px solid #2a2a3a;
    border-radius: 4px;
    padding: 4px 8px;
    color: #c8c8d8;
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
        self.monitoring_worker = None
        self.monitoring_thread = None
        self.screen_overlay = ScreenBlurOverlay()
        self._dnd_active = False
        self._dnd_timer = QTimer(self)
        self._dnd_timer.setSingleShot(True)
        self._dnd_timer.timeout.connect(self._end_dnd)
        self._shortcuts = []
        self._init_ui()
        self._setup_tray()
        self._setup_shortcuts()

        # Auto-start monitoring if configured
        if self.settings.get('auto_start_monitoring', False):
            QTimer.singleShot(800, self._auto_start_monitoring)

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

        # DND button
        self.dnd_btn = QPushButton("DND")
        self.dnd_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6a6a7a; border: none; "
            "font-size: 11px; padding: 4px 8px; } "
            "QPushButton:hover { color: #b08030; }"
        )
        self.dnd_btn.setToolTip("Do Not Disturb — pause all alerts")
        self.dnd_btn.clicked.connect(self._toggle_dnd)
        h_layout.addWidget(self.dnd_btn)

        self.dnd_label = QLabel("")
        self.dnd_label.setStyleSheet("color: #b08030; font-size: 11px; background: transparent; border: none;")
        self.dnd_label.hide()
        h_layout.addWidget(self.dnd_label)

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

    # ===== System Tray =====

    def _setup_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon_path = Path("assets/icons/app_icon.png")
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            self.tray_icon.setIcon(self.style().standardIcon(
                self.style().StandardPixmap.SP_ComputerIcon))

        tray_menu = QMenu()

        self.tray_show_action = tray_menu.addAction("Show Window")
        self.tray_show_action.triggered.connect(self._show_from_tray)

        tray_menu.addSeparator()

        self.tray_monitor_action = tray_menu.addAction("Start Monitoring")
        self.tray_monitor_action.triggered.connect(self._toggle_monitoring)

        self.tray_pause_action = tray_menu.addAction("Pause")
        self.tray_pause_action.triggered.connect(self._toggle_pause)
        self.tray_pause_action.setEnabled(False)

        tray_menu.addSeparator()

        self.tray_dnd_action = tray_menu.addAction("Do Not Disturb")
        self.tray_dnd_action.triggered.connect(self._toggle_dnd)

        tray_menu.addSeparator()

        quit_action = tray_menu.addAction("Quit")
        quit_action.triggered.connect(self._quit_app)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._on_tray_activated)
        self.tray_icon.setToolTip("ErgoBoost — Posture Monitor")
        self.tray_icon.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._show_from_tray()

    def _show_from_tray(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _update_tray_tooltip(self):
        status = "monitoring" if self.monitoring_worker else "idle"
        dnd = " [DND]" if self._dnd_active else ""
        self.tray_icon.setToolTip(f"ErgoBoost — {status}{dnd}")

    # ===== Hotkeys =====

    def _setup_shortcuts(self):
        # Clear old shortcuts
        for sc in self._shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self._shortcuts.clear()

        hk_monitor = self.settings.get('hotkey_toggle_monitoring', 'Ctrl+M')
        hk_pause = self.settings.get('hotkey_toggle_pause', 'Ctrl+P')
        hk_dismiss = self.settings.get('hotkey_dismiss_overlay', 'Escape')

        sc1 = QShortcut(QKeySequence(hk_monitor), self)
        sc1.activated.connect(self._toggle_monitoring)
        self._shortcuts.append(sc1)

        sc2 = QShortcut(QKeySequence(hk_pause), self)
        sc2.activated.connect(self._toggle_pause)
        self._shortcuts.append(sc2)

        sc3 = QShortcut(QKeySequence(hk_dismiss), self)
        sc3.activated.connect(self._dismiss_overlay)
        self._shortcuts.append(sc3)

    # ===== DND Mode =====

    def _toggle_dnd(self):
        if self._dnd_active:
            self._end_dnd()
        else:
            self._start_dnd()

    def _start_dnd(self):
        duration_min = self.settings.get('dnd_duration_minutes', 30)
        self._dnd_active = True
        self._dnd_timer.start(duration_min * 60 * 1000)

        if self.monitoring_worker:
            self.monitoring_worker.set_dnd(True)

        self.dnd_btn.setStyleSheet(
            "QPushButton { background: #3a2818; color: #e0a040; border: 1px solid #5a4020; "
            "font-size: 11px; padding: 4px 8px; border-radius: 3px; } "
            "QPushButton:hover { background: #4a3828; }"
        )
        self.dnd_btn.setText(f"DND ({duration_min}m)")
        self.dnd_label.setText("Alerts paused")
        self.dnd_label.show()
        self.tray_dnd_action.setText(f"Stop DND ({duration_min}m remaining)")
        self._update_tray_tooltip()
        self.statusBar().showMessage(f"Do Not Disturb — {duration_min} minutes")
        logger.info(f"DND enabled for {duration_min} minutes")

    def _end_dnd(self):
        self._dnd_active = False
        self._dnd_timer.stop()

        if self.monitoring_worker:
            self.monitoring_worker.set_dnd(False)

        self.dnd_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #6a6a7a; border: none; "
            "font-size: 11px; padding: 4px 8px; } "
            "QPushButton:hover { color: #b08030; }"
        )
        self.dnd_btn.setText("DND")
        self.dnd_label.hide()
        self.tray_dnd_action.setText("Do Not Disturb")
        self._update_tray_tooltip()
        self.statusBar().showMessage("Do Not Disturb ended")
        logger.info("DND disabled")

    # ===== Signals =====

    def _connect_signals(self):
        self.dashboard_tab.monitoring_started.connect(self.start_monitoring)
        self.dashboard_tab.monitoring_stopped.connect(self.stop_monitoring)
        self.dashboard_tab.monitoring_paused.connect(self.pause_monitoring)
        self.settings_tab.settings_changed.connect(self.on_settings_changed)
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

    # ===== Monitoring =====

    def _auto_start_monitoring(self):
        if self.monitoring_worker is None:
            self.dashboard_tab._on_start_clicked()

    def _toggle_monitoring(self):
        if self.monitoring_worker is not None:
            self.dashboard_tab._on_stop_clicked()
        else:
            self.dashboard_tab._on_start_clicked()

    def _toggle_pause(self):
        if self.monitoring_worker is not None:
            self.dashboard_tab._on_pause_clicked()

    def _dismiss_overlay(self):
        """Emergency dismiss overlay."""
        self.screen_overlay.hide_overlay()
        if self.monitoring_worker and self.monitoring_worker._is_overlay_active:
            self.monitoring_worker._is_overlay_active = False
            self.monitoring_worker._bad_state_start_time = None

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
            self.monitoring_worker.overlay_countdown.connect(self._on_overlay_countdown)

            self.monitoring_thread.started.connect(self.monitoring_worker.run)
            self.monitoring_worker.finished.connect(self.monitoring_thread.quit)
            self.monitoring_worker.finished.connect(self.on_monitoring_finished)

            if self._dnd_active:
                self.monitoring_worker.set_dnd(True)

            self.monitoring_thread.start()

            self.tray_monitor_action.setText("Stop Monitoring")
            self.tray_pause_action.setEnabled(True)
            self._update_tray_tooltip()
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
        self.tray_pause_action.setText("Resume" if paused else "Pause")
        self.statusBar().showMessage("Paused" if paused else "Monitoring active")

    def on_monitoring_finished(self):
        if self.monitoring_thread:
            self.monitoring_thread.quit()
            self.monitoring_thread.wait()
        self.monitoring_worker = None
        self.monitoring_thread = None
        self.sessions_tab.refresh_sessions()
        self.tray_monitor_action.setText("Start Monitoring")
        self.tray_pause_action.setText("Pause")
        self.tray_pause_action.setEnabled(False)
        self._update_tray_tooltip()
        self.statusBar().showMessage("Stopped")

    def on_monitoring_error(self, error_msg):
        QMessageBox.warning(self, "Monitoring Error", error_msg)

    def _on_overlay_requested(self, show: bool, message: str):
        if show:
            self.screen_overlay.show_overlay(message)
        else:
            self.screen_overlay.hide_overlay()

    def _on_overlay_countdown(self, seconds: int):
        """Handle overlay countdown from worker."""
        self.dashboard_tab.update_overlay_countdown(seconds)
        if seconds > 0:
            self.screen_overlay.show_countdown(seconds)
        elif seconds < 0:
            self.screen_overlay.hide_overlay()

    def on_settings_changed(self):
        if self.monitoring_worker:
            self.monitoring_worker.update_settings(self.settings)
        self._setup_shortcuts()  # Rebuild hotkeys in case they changed
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
        self.tray_icon.hide()
        self.close()
        # Signal to app that we want to restart auth
        if self.sign_out_requested:
            self.sign_out_requested()

    def _quit_app(self):
        """Full quit from tray."""
        if self.monitoring_worker is not None:
            self.monitoring_worker.stop()
            if self.monitoring_thread:
                self.monitoring_thread.quit()
                self.monitoring_thread.wait(3000)
        self.screen_overlay.hide_overlay()
        self.tray_icon.hide()
        QApplication.quit()

    def closeEvent(self, event):
        # Minimize to tray instead of quitting
        if self.monitoring_worker is not None:
            event.ignore()
            self.hide()
            self.tray_icon.showMessage(
                "ErgoBoost",
                "Monitoring continues in background. Right-click tray icon to quit.",
                QSystemTrayIcon.MessageIcon.Information, 3000
            )
        else:
            self.tray_icon.hide()
            event.accept()


def main():
    """Main entry point with auth flow"""
    app = QApplication(sys.argv)
    app.setApplicationName("ErgoBoost")
    app.setOrganizationName("ErgoBoost")
    app.setApplicationVersion("1.0.0")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

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
