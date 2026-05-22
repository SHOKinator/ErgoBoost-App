# gui/settings_tab.py
"""
Settings tab - Application configuration
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QComboBox, QFrame, QScrollArea, QSlider, QPushButton,
    QMessageBox, QGroupBox, QSpinBox, QKeySequenceEdit
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QKeySequence


class SettingsTab(QWidget):
    settings_changed = Signal()

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setFont(QFont("Segoe UI", 20, QFont.DemiBold))
        title.setStyleSheet("color: #e0e0ee;")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        c_layout = QVBoxLayout(content)
        c_layout.setSpacing(12)

        c_layout.addWidget(self._create_general_group())
        c_layout.addWidget(self._create_calibration_group())
        c_layout.addWidget(self._create_posture_group())
        c_layout.addWidget(self._create_alert_group())
        c_layout.addWidget(self._create_break_group())
        c_layout.addWidget(self._create_eye_group())
        c_layout.addWidget(self._create_hotkeys_group())
        c_layout.addWidget(self._create_visual_group())
        c_layout.addStretch()

        scroll.setWidget(content)
        layout.addWidget(scroll)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("Reset Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        btn_row.addWidget(reset_btn)

        save_btn = QPushButton("Save")
        save_btn.setProperty("class", "primary")
        save_btn.setMinimumSize(100, 36)
        save_btn.clicked.connect(self._save_settings)
        btn_row.addWidget(save_btn)
        layout.addLayout(btn_row)

    def _create_general_group(self):
        group = QGroupBox("General")
        layout = QVBoxLayout(group)

        self.auto_start_cb = QCheckBox("Auto-start monitoring on launch")
        layout.addWidget(self.auto_start_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Do Not Disturb duration:"))
        self.dnd_duration_spin = QSpinBox()
        self.dnd_duration_spin.setRange(5, 120)
        self.dnd_duration_spin.setSuffix(" min")
        self.dnd_duration_spin.setValue(30)
        row.addWidget(self.dnd_duration_spin)
        row.addStretch()
        layout.addLayout(row)

        info = QLabel("DND pauses all alerts and overlay for the set duration.")
        info.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_calibration_group(self):
        group = QGroupBox("Calibration")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Mode:"))
        self.cal_mode_combo = QComboBox()
        self.cal_mode_combo.addItems(["Always calibrate", "Use last calibration"])
        row.addWidget(self.cal_mode_combo)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Duration:"))
        self.cal_duration_combo = QComboBox()
        self.cal_duration_combo.addItems(["3 seconds", "5 seconds", "10 seconds"])
        row.addWidget(self.cal_duration_combo)
        row.addStretch()
        layout.addLayout(row)

        return group

    def _create_posture_group(self):
        group = QGroupBox("Posture Monitoring")
        layout = QVBoxLayout(group)

        self.posture_enabled_cb = QCheckBox("Enable Posture Monitoring")
        layout.addWidget(self.posture_enabled_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Sensitivity:"))
        self.sensitivity_combo = QComboBox()
        self.sensitivity_combo.addItems(["Low", "Medium", "High"])
        row.addWidget(self.sensitivity_combo)
        row.addStretch()
        layout.addLayout(row)

        info = QLabel("Low: fewer alerts  |  Medium: balanced  |  High: strict")
        info.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        layout.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Detection:"))
        self.detection_combo = QComboBox()
        self.detection_combo.addItems(["Rule-based", "ML Model"])
        row.addWidget(self.detection_combo)
        row.addStretch()
        layout.addLayout(row)

        det_info = QLabel("Rule-based: threshold logic  |  ML Model: trained classifier (97% acc)")
        det_info.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        layout.addWidget(det_info)

        return group

    def _create_alert_group(self):
        group = QGroupBox("Alerts")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Reaction:"))
        self.reaction_combo = QComboBox()
        self.reaction_combo.addItems(["Alert only", "Blur OS"])
        row.addWidget(self.reaction_combo)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Overlay delay:"))
        self.overlay_delay_spin = QSpinBox()
        self.overlay_delay_spin.setRange(1, 15)
        self.overlay_delay_spin.setSuffix(" sec")
        self.overlay_delay_spin.setValue(4)
        row.addWidget(self.overlay_delay_spin)
        row.addStretch()
        layout.addLayout(row)

        self.sound_cb = QCheckBox("Enable Sound Alerts")
        layout.addWidget(self.sound_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Cooldown:"))
        self.cooldown_slider = QSlider(Qt.Horizontal)
        self.cooldown_slider.setMinimum(10)
        self.cooldown_slider.setMaximum(120)
        self.cooldown_slider.setValue(30)
        row.addWidget(self.cooldown_slider)
        self.cooldown_label = QLabel("30s")
        self.cooldown_label.setMinimumWidth(35)
        self.cooldown_slider.valueChanged.connect(
            lambda v: self.cooldown_label.setText(f"{v}s"))
        row.addWidget(self.cooldown_label)
        layout.addLayout(row)

        return group

    def _create_break_group(self):
        group = QGroupBox("Break Reminders")
        layout = QVBoxLayout(group)

        self.break_enabled_cb = QCheckBox("Enable Break Reminders")
        layout.addWidget(self.break_enabled_cb)

        row = QHBoxLayout()
        row.addWidget(QLabel("Soft reminder after:"))
        self.soft_limit_spin = QSpinBox()
        self.soft_limit_spin.setRange(30, 180)
        self.soft_limit_spin.setSuffix(" min")
        self.soft_limit_spin.setValue(90)
        row.addWidget(self.soft_limit_spin)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Hard reminder after:"))
        self.hard_limit_spin = QSpinBox()
        self.hard_limit_spin.setRange(60, 240)
        self.hard_limit_spin.setSuffix(" min")
        self.hard_limit_spin.setValue(120)
        row.addWidget(self.hard_limit_spin)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Min. absence for break:"))
        self.absence_spin = QSpinBox()
        self.absence_spin.setRange(1, 30)
        self.absence_spin.setSuffix(" min")
        self.absence_spin.setValue(10)
        row.addWidget(self.absence_spin)
        row.addStretch()
        layout.addLayout(row)

        info = QLabel("If you leave for longer than the absence threshold, it counts as a real break.")
        info.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        return group

    def _create_eye_group(self):
        group = QGroupBox("Eye Tracking")
        layout = QVBoxLayout(group)
        self.blink_cb = QCheckBox("Enable Blink Tracking")
        layout.addWidget(self.blink_cb)
        return group

    def _create_hotkeys_group(self):
        group = QGroupBox("Hotkeys")
        layout = QVBoxLayout(group)

        row = QHBoxLayout()
        row.addWidget(QLabel("Toggle monitoring:"))
        self.hk_monitoring = QKeySequenceEdit(QKeySequence("Ctrl+M"))
        row.addWidget(self.hk_monitoring)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Toggle pause:"))
        self.hk_pause = QKeySequenceEdit(QKeySequence("Ctrl+P"))
        row.addWidget(self.hk_pause)
        row.addStretch()
        layout.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Dismiss overlay:"))
        self.hk_dismiss = QKeySequenceEdit(QKeySequence("Escape"))
        row.addWidget(self.hk_dismiss)
        row.addStretch()
        layout.addLayout(row)

        info = QLabel("Click the field and press your desired key combination.")
        info.setStyleSheet("color: #5a5a6a; font-size: 11px;")
        layout.addWidget(info)
        return group

    def _create_visual_group(self):
        group = QGroupBox("Visual")
        layout = QVBoxLayout(group)
        self.face_lm_cb = QCheckBox("Show Face Landmarks")
        layout.addWidget(self.face_lm_cb)
        self.pose_lm_cb = QCheckBox("Show Pose Landmarks")
        layout.addWidget(self.pose_lm_cb)
        return group

    def _load_settings(self):
        s = self.settings

        self.auto_start_cb.setChecked(s.get('auto_start_monitoring', False))
        self.dnd_duration_spin.setValue(s.get('dnd_duration_minutes', 30))

        cal_mode = s.get('calibration_mode', 'always')
        self.cal_mode_combo.setCurrentText(
            "Always calibrate" if cal_mode == 'always' else "Use last calibration")

        dur = s.get('calibration_duration', 5.0)
        self.cal_duration_combo.setCurrentText(
            f"{int(dur)} seconds" if dur in (3, 5, 10) else "5 seconds")

        self.posture_enabled_cb.setChecked(s.get('posture_control_enabled', True))
        self.sensitivity_combo.setCurrentText(
            s.get('posture_sensitivity', 'medium').capitalize())

        mode = s.get('detection_mode', 'rule_based')
        self.detection_combo.setCurrentText("ML Model" if mode == 'ml' else "Rule-based")

        rm = s.get('reaction_mode', 'alert_only')
        if rm == 'blur_os_screen':
            self.reaction_combo.setCurrentText("Blur OS")
        else:
            self.reaction_combo.setCurrentText("Alert only")

        self.overlay_delay_spin.setValue(s.get('overlay_delay_seconds', 4))
        self.sound_cb.setChecked(s.get('sound_alerts_enabled', False))
        self.cooldown_slider.setValue(int(s.get('alert_cooldown', 30)))

        self.break_enabled_cb.setChecked(s.get('break_reminder_enabled', True))
        self.soft_limit_spin.setValue(int(s.get('break_work_duration', 5400) / 60))
        self.hard_limit_spin.setValue(int(s.get('break_max_work_duration', 7200) / 60))
        self.absence_spin.setValue(int(s.get('absence_threshold', 600) / 60))

        self.blink_cb.setChecked(s.get('blink_tracking_enabled', True))
        self.face_lm_cb.setChecked(s.get('show_face_landmarks', False))
        self.pose_lm_cb.setChecked(s.get('show_pose_landmarks', True))

        self.hk_monitoring.setKeySequence(QKeySequence(s.get('hotkey_toggle_monitoring', 'Ctrl+M')))
        self.hk_pause.setKeySequence(QKeySequence(s.get('hotkey_toggle_pause', 'Ctrl+P')))
        self.hk_dismiss.setKeySequence(QKeySequence(s.get('hotkey_dismiss_overlay', 'Escape')))

    def _save_settings(self):
        updates = {
            'auto_start_monitoring': self.auto_start_cb.isChecked(),
            'dnd_duration_minutes': self.dnd_duration_spin.value(),
            'calibration_mode': 'always' if self.cal_mode_combo.currentText() == "Always calibrate" else 'once',
            'calibration_duration': float(self.cal_duration_combo.currentText().split()[0]),
            'posture_control_enabled': self.posture_enabled_cb.isChecked(),
            'posture_sensitivity': self.sensitivity_combo.currentText().lower(),
            'detection_mode': 'ml' if self.detection_combo.currentText() == "ML Model" else 'rule_based',
            'reaction_mode': 'blur_os_screen' if self.reaction_combo.currentText() == "Blur OS" else 'alert_only',
            'overlay_delay_seconds': self.overlay_delay_spin.value(),
            'sound_alerts_enabled': self.sound_cb.isChecked(),
            'alert_cooldown': self.cooldown_slider.value(),
            'break_reminder_enabled': self.break_enabled_cb.isChecked(),
            'break_work_duration': self.soft_limit_spin.value() * 60,
            'break_max_work_duration': self.hard_limit_spin.value() * 60,
            'absence_threshold': self.absence_spin.value() * 60,
            'blink_tracking_enabled': self.blink_cb.isChecked(),
            'show_face_landmarks': self.face_lm_cb.isChecked(),
            'show_pose_landmarks': self.pose_lm_cb.isChecked(),
            'hotkey_toggle_monitoring': self.hk_monitoring.keySequence().toString(),
            'hotkey_toggle_pause': self.hk_pause.keySequence().toString(),
            'hotkey_dismiss_overlay': self.hk_dismiss.keySequence().toString(),
        }
        self.settings.batch_update(updates)
        self.settings_changed.emit()
        QMessageBox.information(self, "Saved", "Settings saved.")

    def _reset_defaults(self):
        reply = QMessageBox.question(self, "Reset",
            "Reset all settings to defaults?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.settings.reset_to_defaults()
            self._load_settings()
            self.settings_changed.emit()
