# config/settings.py
"""
Configuration management for ErgoBoost
"""

import yaml
from pathlib import Path
from typing import Any, Dict
from utils.logger import setup_logger

logger = setup_logger(__name__)


class Settings:
    DEFAULT_CONFIG = {
        # Detection thresholds
        'blink_ear_threshold': 0.21,
        'forward_shift_threshold': 0.1,
        'lateral_tilt_threshold': 5.0,
        'distance_too_close': 0.3,
        'distance_too_far': 0.18,

        # Calibration
        'calibration_duration': 5.0,
        'min_calibration_samples': 30,
        'calibration_mode': 'always',

        # Performance
        'target_fps': 30,
        'frame_skip': 1,

        # Logging
        'log_interval': 5.0,

        # Alerts
        'sound_alerts_enabled': False,
        'visual_alerts_enabled': True,
        'alert_cooldown': 30,

        # Break reminders
        'break_work_duration': 5400,      # 1.5 hours continuous work -> reminder
        'break_max_work_duration': 7200,   # 2 hours hard limit
        'absence_threshold': 600,          # 10 min absence = real break
        'break_reminder_enabled': True,

        # Posture
        'posture_control_enabled': True,
        'posture_sensitivity': 'medium',

        # Eye tracking
        'blink_tracking_enabled': True,
        'fatigue_blink_window': 60,        # seconds window for blink rate
        'fatigue_low_blink_rate': 8,       # blinks/min below = fatigue
        'fatigue_high_blink_rate': 30,     # blinks/min above = strain

        # Reaction
        'reaction_mode': 'alert_only',

        # UI
        'show_face_landmarks': True,
        'show_pose_landmarks': True,
        'window_width': 1280,
        'window_height': 800,

        # Database
        'db_path': 'data/ergoboost.db',

        # Analytics
        'enable_spark_analytics': True,
        'analytics_export_interval': 86400,
    }

    def __init__(self, config_file: Path = Path("config/settings.yaml")):
        self.config_file = config_file
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r') as f:
                    user_config = yaml.safe_load(f) or {}
                config = self.DEFAULT_CONFIG.copy()
                config.update(user_config)
                return config
            except Exception as e:
                logger.error(f"Failed to load config: {e}, using defaults")
                return self.DEFAULT_CONFIG.copy()
        else:
            self._save_config(self.DEFAULT_CONFIG)
            return self.DEFAULT_CONFIG.copy()

    def _save_config(self, config: Dict):
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=True)

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        self._save_config(self.config)

    def reset_to_defaults(self):
        self.config = self.DEFAULT_CONFIG.copy()
        self._save_config(self.config)
