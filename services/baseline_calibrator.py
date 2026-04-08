# services/baseline_calibrator.py
"""
Calibrates user's baseline posture and distance.
Users sit in their natural comfortable position during calibration.
All future deviations are measured relative to this personal baseline.
"""

import time
import numpy as np
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BaselineCalibrator:
    def __init__(self, duration=5.0, min_samples=30):
        self.calibration_duration = duration
        self.min_samples = min_samples

        self.baseline = {}
        self.samples = []
        self.start_time = None

        self.is_calibrating = False
        self.is_calibrated = False

    def start_calibration(self):
        self.samples.clear()
        self.start_time = time.time()
        self.is_calibrating = True
        self.is_calibrated = False
        logger.info("Baseline calibration started")

    def update(self, metrics: dict):
        """
        metrics should include: forward_shift, lateral_tilt, distance_ratio
        """
        if not self.is_calibrating:
            return False

        clean = {k: v for k, v in metrics.items() if v is not None}
        if clean:
            self.samples.append(clean)

        if time.time() - self.start_time >= self.calibration_duration:
            self._finalize()
            return True
        return False

    def _finalize(self):
        if len(self.samples) < self.min_samples:
            logger.warning(f"Insufficient calibration samples: {len(self.samples)}")
            self.is_calibrating = False
            self.is_calibrated = False
            return

        self.baseline = {}
        all_keys = set()
        for s in self.samples:
            all_keys.update(s.keys())

        for key in all_keys:
            values = [s[key] for s in self.samples if key in s]
            if values:
                self.baseline[key] = float(np.median(values))

        self.is_calibrating = False
        self.is_calibrated = True
        logger.info(f"Baseline calibrated: {self.baseline}")

    def deviation(self, current: dict):
        if not self.is_calibrated:
            return None

        deviation = {}

        WEIGHTS = {
            "forward_shift": 1.5,
            "lateral_tilt": 1.0,
        }

        for k, base_val in self.baseline.items():
            cur_val = current.get(k)
            if cur_val is not None:
                raw_dev = cur_val - base_val

                # remove noise
                if abs(raw_dev) < 0.01:
                    raw_dev = 0

                # apply weight
                deviation[k] = raw_dev * WEIGHTS.get(k, 1.0)

        return deviation

    def get_baseline_value(self, key: str):
        return self.baseline.get(key)

    def reset(self):
        self.baseline.clear()
        self.samples.clear()
        self.start_time = None
        self.is_calibrating = False
        self.is_calibrated = False

    def get_status(self):
        if self.is_calibrating:
            return "CALIBRATING"
        if self.is_calibrated:
            return "MONITORING"
        return "WAITING"

    def get_progress(self):
        if not self.is_calibrating or self.start_time is None:
            return 0.0
        elapsed = time.time() - self.start_time
        return min(1.0, elapsed / self.calibration_duration)
