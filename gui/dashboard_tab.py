# gui/dashboard_tab.py
"""
Dashboard tab - Main monitoring interface with extended metrics
"""

import numpy as np
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QProgressBar, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QImage, QPixmap, QFont


class DashboardTab(QWidget):
    monitoring_started = Signal()
    monitoring_stopped = Signal()
    monitoring_paused = Signal(bool)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.is_monitoring = False
        self.is_paused = False
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QHBoxLayout()
        title = QLabel("Live Monitoring")
        title.setFont(QFont("Segoe UI", 20, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        header.addWidget(title)
        header.addStretch()

        self.presence_indicator = QLabel("  OFFLINE  ")
        self.presence_indicator.setStyleSheet(
            "color: #6a6a7a; background-color: #1a1a24; padding: 4px 12px; "
            "border-radius: 3px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;"
        )
        header.addWidget(self.presence_indicator)

        self.work_time_label = QLabel("0 min")
        self.work_time_label.setStyleSheet(
            "color: #8a8a9a; background-color: #1a1a24; padding: 4px 12px; "
            "border-radius: 3px; font-size: 11px;"
        )
        header.addWidget(self.work_time_label)
        layout.addLayout(header)

        # Main content
        content_layout = QHBoxLayout()
        content_layout.setSpacing(12)

        # Camera panel
        left_panel = self._create_camera_panel()
        content_layout.addWidget(left_panel, 3)

        # Metrics panel
        right_panel = self._create_metrics_panel()
        content_layout.addWidget(right_panel, 1)
        layout.addLayout(content_layout)

        # Controls
        controls = self._create_controls()
        layout.addWidget(controls)

        # Alert banner
        self.alert_banner = self._create_alert_banner()
        self.alert_banner.hide()
        layout.addWidget(self.alert_banner)

    def _create_camera_panel(self):
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #0a0a0f;
                border: 1px solid #1e1e2a;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(2, 2, 2, 2)

        self.camera_label = QLabel()
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setMinimumSize(640, 480)
        self.camera_label.setStyleSheet("background-color: #0a0a0f; border: none;")
        self.camera_label.setText("Camera feed will appear here")
        layout.addWidget(self.camera_label)

        self.calibration_bar = QProgressBar()
        self.calibration_bar.setMaximum(100)
        self.calibration_bar.setTextVisible(True)
        self.calibration_bar.setFormat("Calibrating... %p%")
        self.calibration_bar.hide()
        layout.addWidget(self.calibration_bar)

        return panel

    def _create_metrics_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #16161e; border: 1px solid #1e1e2a; border-radius: 4px; }")

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # Status
        self._add_section_label(layout, "STATUS")
        self.status_value = QLabel("Ready")
        self.status_value.setStyleSheet(
            "color: #6a6a7a; padding: 6px 10px; background-color: #1a1a24; border-radius: 3px; font-size: 12px;"
        )
        layout.addWidget(self.status_value)

        self._add_divider(layout)

        # Posture
        self._add_section_label(layout, "POSTURE")
        grid = QGridLayout()
        grid.setSpacing(6)

        self.posture_status_label = self._make_value_label("OK", "#5a9a6a")
        grid.addWidget(QLabel("Status"), 0, 0)
        grid.addWidget(self.posture_status_label, 0, 1)

        self.forward_shift_label = self._make_value_label("-")
        grid.addWidget(QLabel("Forward"), 1, 0)
        grid.addWidget(self.forward_shift_label, 1, 1)

        self.lateral_tilt_label = self._make_value_label("-")
        grid.addWidget(QLabel("Tilt"), 2, 0)
        grid.addWidget(self.lateral_tilt_label, 2, 1)

        self.severity_label = self._make_value_label("0.0")
        grid.addWidget(QLabel("Severity"), 3, 0)
        grid.addWidget(self.severity_label, 3, 1)

        layout.addLayout(grid)

        self._add_divider(layout)

        # Distance
        self._add_section_label(layout, "DISTANCE")
        self.distance_status_label = self._make_value_label("--", "#6a6a7a")
        layout.addWidget(self.distance_status_label)

        self._add_divider(layout)

        # Eyes
        self._add_section_label(layout, "EYES")
        eye_grid = QGridLayout()
        eye_grid.setSpacing(6)

        self.blink_count_label = self._make_value_label("0")
        eye_grid.addWidget(QLabel("Blinks"), 0, 0)
        eye_grid.addWidget(self.blink_count_label, 0, 1)

        self.blink_rate_label = self._make_value_label("--/min")
        eye_grid.addWidget(QLabel("Rate"), 1, 0)
        eye_grid.addWidget(self.blink_rate_label, 1, 1)

        self.ear_label = self._make_value_label("-")
        eye_grid.addWidget(QLabel("EAR"), 2, 0)
        eye_grid.addWidget(self.ear_label, 2, 1)

        self.fatigue_label = self._make_value_label("Normal", "#5a9a6a")
        eye_grid.addWidget(QLabel("Fatigue"), 3, 0)
        eye_grid.addWidget(self.fatigue_label, 3, 1)

        layout.addLayout(eye_grid)
        layout.addStretch()
        return panel

    def _add_section_label(self, layout, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(
            "color: #5a5a6a; font-size: 10px; font-weight: 700; "
            "letter-spacing: 1.5px; padding-top: 4px;"
        )
        layout.addWidget(lbl)

    def _add_divider(self, layout):
        line = QFrame()
        line.setFixedHeight(1)
        line.setStyleSheet("background-color: #1e1e2a; border: none; border-radius: 0;")
        layout.addWidget(line)

    def _make_value_label(self, text, color="#c8c8d8"):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignRight)
        lbl.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 500;")
        return lbl

    def _create_controls(self):
        controls = QFrame()
        controls.setStyleSheet("QFrame { background-color: transparent; border: none; }")
        layout = QHBoxLayout(controls)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.addStretch()

        self.start_button = QPushButton("Start Monitoring")
        self.start_button.setMinimumSize(160, 40)
        self.start_button.setProperty("class", "success")
        self.start_button.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_button)

        self.pause_button = QPushButton("Pause")
        self.pause_button.setMinimumSize(100, 40)
        self.pause_button.setProperty("class", "warning")
        self.pause_button.clicked.connect(self._on_pause_clicked)
        self.pause_button.hide()
        layout.addWidget(self.pause_button)

        self.stop_button = QPushButton("Stop")
        self.stop_button.setMinimumSize(100, 40)
        self.stop_button.setProperty("class", "danger")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        self.stop_button.hide()
        layout.addWidget(self.stop_button)

        layout.addStretch()
        return controls

    def _create_alert_banner(self):
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #3a2020;
                border: 1px solid #5a3030;
                border-radius: 4px;
                padding: 10px;
            }
        """)
        layout = QHBoxLayout(banner)

        self.alert_icon = QLabel("!")
        self.alert_icon.setStyleSheet(
            "color: #ff6070; font-size: 16px; font-weight: 700; "
            "background-color: transparent;"
        )
        layout.addWidget(self.alert_icon)

        self.alert_text = QLabel("")
        self.alert_text.setWordWrap(True)
        self.alert_text.setStyleSheet("color: #e0a0a0; font-size: 12px; background: transparent;")
        layout.addWidget(self.alert_text, 1)

        close_btn = QPushButton("x")
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent; color: #8a5050;
                font-size: 14px; font-weight: bold; border: none;
            }
            QPushButton:hover { color: #ff6070; }
        """)
        close_btn.clicked.connect(lambda: self.alert_banner.hide())
        layout.addWidget(close_btn)
        return banner

    def _on_start_clicked(self):
        self.is_monitoring = True
        self.start_button.hide()
        self.pause_button.show()
        self.stop_button.show()
        self.monitoring_started.emit()

    def _on_pause_clicked(self):
        self.is_paused = not self.is_paused
        self.pause_button.setText("Resume" if self.is_paused else "Pause")
        self.monitoring_paused.emit(self.is_paused)

    def _on_stop_clicked(self):
        self.is_monitoring = False
        self.is_paused = False
        self.start_button.show()
        self.pause_button.hide()
        self.stop_button.hide()
        self.pause_button.setText("Pause")
        self.camera_label.setText("Camera feed will appear here")
        self.camera_label.setPixmap(QPixmap())
        self.monitoring_stopped.emit()

    def update_camera_frame(self, frame: np.ndarray):
        height, width, channel = frame.shape
        bytes_per_line = 3 * width
        q_image = QImage(frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_image)
        scaled = pixmap.scaled(self.camera_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.camera_label.setPixmap(scaled)

    def update_metrics(self, metrics: dict):
        # Status
        status = metrics.get('calibration_status', 'Ready')
        self.status_value.setText(status)
        status_colors = {
            'CALIBRATING': '#b08030',
            'MONITORING': '#5a9a6a',
        }
        c = status_colors.get(status, '#6a6a7a')
        self.status_value.setStyleSheet(
            f"color: {c}; padding: 6px 10px; background-color: #1a1a24; border-radius: 3px; font-size: 12px;"
        )

        # Presence
        is_present = metrics.get('is_present', False)
        if is_present:
            self.presence_indicator.setText("  PRESENT  ")
            self.presence_indicator.setStyleSheet(
                "color: #5a9a6a; background-color: #1a2a1e; padding: 4px 12px; "
                "border-radius: 3px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;"
            )
        else:
            self.presence_indicator.setText("  AWAY  ")
            self.presence_indicator.setStyleSheet(
                "color: #8a6a3a; background-color: #2a2418; padding: 4px 12px; "
                "border-radius: 3px; font-size: 11px; font-weight: 600; letter-spacing: 0.5px;"
            )

        # Work time
        work_min = metrics.get('work_minutes', 0)
        hours = int(work_min // 60)
        mins = int(work_min % 60)
        if hours > 0:
            self.work_time_label.setText(f"{hours}h {mins}m")
        else:
            self.work_time_label.setText(f"{mins} min")

        # Posture
        ps = metrics.get('posture_status', 'OK')
        ps_color = '#5a9a6a' if ps == 'OK' else '#c04050'
        self.posture_status_label.setText(ps)
        self.posture_status_label.setStyleSheet(
            f"color: {ps_color}; font-size: 12px; font-weight: 600;"
        )

        fwd = metrics.get('forward_shift')
        self.forward_shift_label.setText(f"{fwd:.3f}" if fwd is not None else "-")

        tilt = metrics.get('lateral_tilt')
        self.lateral_tilt_label.setText(f"{tilt:.1f}°" if tilt is not None else "-")

        sev = metrics.get('severity', 0)
        sev_color = '#5a9a6a' if sev < 1 else '#b08030' if sev < 2 else '#c04050'
        self.severity_label.setText(f"{sev:.1f}")
        self.severity_label.setStyleSheet(f"color: {sev_color}; font-size: 12px; font-weight: 500;")

        # Distance
        ds = metrics.get('distance_status', 'Unknown')
        ds_color = '#5a9a6a' if ds == 'OK' else '#c04050' if ds != 'Unknown' else '#6a6a7a'
        self.distance_status_label.setText(ds.replace('_', ' '))
        self.distance_status_label.setStyleSheet(f"color: {ds_color}; font-size: 12px; font-weight: 500;")

        # Eyes
        self.blink_count_label.setText(str(metrics.get('blink_count', 0)))
        br = metrics.get('blink_rate', 0)
        self.blink_rate_label.setText(f"{br:.0f}/min")

        ear = metrics.get('ear')
        self.ear_label.setText(f"{ear:.3f}" if ear is not None else "-")

        fatigue = metrics.get('fatigue_level', 'NORMAL')
        f_text = {'NORMAL': 'Normal', 'LOW_BLINK': 'Low blink', 'HIGH_BLINK': 'High blink'}
        f_color = {'NORMAL': '#5a9a6a', 'LOW_BLINK': '#c04050', 'HIGH_BLINK': '#b08030'}
        self.fatigue_label.setText(f_text.get(fatigue, fatigue))
        self.fatigue_label.setStyleSheet(
            f"color: {f_color.get(fatigue, '#6a6a7a')}; font-size: 12px; font-weight: 500;"
        )

    def update_calibration_progress(self, progress: float):
        if 0 < progress < 1:
            self.calibration_bar.show()
            self.calibration_bar.setValue(int(progress * 100))
        else:
            self.calibration_bar.hide()

    def show_alert(self, alert_type: str, message: str):
        colors = {
            'posture':  ('#3a2020', '#5a3030', '#ff6070', '#e0a0a0'),
            'distance': ('#2a2818', '#4a4030', '#e0a040', '#d0c0a0'),
            'fatigue':  ('#1a2030', '#2a3050', '#6090d0', '#a0c0e0'),
            'break':    ('#1a2a1e', '#2a4a30', '#60c070', '#a0d0a0'),
        }
        bg, border, icon_c, text_c = colors.get(alert_type, colors['posture'])

        self.alert_banner.setStyleSheet(
            f"QFrame {{ background-color: {bg}; border: 1px solid {border}; "
            f"border-radius: 4px; padding: 10px; }}"
        )
        self.alert_icon.setStyleSheet(
            f"color: {icon_c}; font-size: 16px; font-weight: 700; background: transparent;"
        )
        self.alert_text.setText(message)
        self.alert_text.setStyleSheet(f"color: {text_c}; font-size: 12px; background: transparent;")
        self.alert_banner.show()
        QTimer.singleShot(8000, self.alert_banner.hide)
