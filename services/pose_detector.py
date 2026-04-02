# services/pose_detector.py
"""
Pose detector using MediaPipe Pose landmarks.
Works relative to baseline calibration.
3 sensitivity levels: low, medium, high.
Uses ONLY shoulders (11, 12) and ears (7, 8) — ignores hands/arms.
Includes temporal smoothing to avoid false BAD from brief movements.
"""

import math
from collections import deque

SENSITIVITY_PRESETS = {
    'low':    {'forward': 0.15, 'lateral': 8.0},
    'medium': {'forward': 0.10, 'lateral': 5.0},
    'high':   {'forward': 0.05, 'lateral': 3.0},
}

# How many frames to average over for smoothing
SMOOTHING_WINDOW = 8


class PoseDetector:
    def __init__(self, forward_threshold=0.1, lateral_threshold=5.0,
                 sensitivity='medium'):
        # MediaPipe Pose landmark indices — ONLY these are used
        self.L_ear = 8
        self.R_ear = 7
        self.L_shoulder = 12
        self.R_shoulder = 11

        # Smoothing buffers
        self.forward_buffer = deque(maxlen=SMOOTHING_WINDOW)
        self.lateral_buffer = deque(maxlen=SMOOTHING_WINDOW)

        self.set_sensitivity(sensitivity)

    def set_sensitivity(self, level: str):
        preset = SENSITIVITY_PRESETS.get(level, SENSITIVITY_PRESETS['medium'])
        self.FORWARD_DEV_THRESHOLD = preset['forward']
        self.LATERAL_DEV_THRESHOLD = preset['lateral']

    def calculate_forward_shift(self, landmarks):
        if landmarks is None or len(landmarks) <= max(
                self.L_ear, self.R_ear, self.L_shoulder, self.R_shoulder):
            return None

        le, re = landmarks[self.L_ear], landmarks[self.R_ear]
        ls, rs = landmarks[self.L_shoulder], landmarks[self.R_shoulder]

        if min(le.visibility, re.visibility, ls.visibility, rs.visibility) < 0.3:
            return None

        ear_center_z = (le.z + re.z) * 0.5
        shoulder_center_z = (ls.z + rs.z) * 0.5
        shoulder_width = abs(ls.x - rs.x)

        if shoulder_width < 1e-4:
            return None

        raw = (ear_center_z - shoulder_center_z) / shoulder_width

        # Smoothing
        self.forward_buffer.append(raw)
        return sum(self.forward_buffer) / len(self.forward_buffer)

    def calculate_lateral_tilt(self, landmarks):
        if landmarks is None or len(landmarks) <= max(self.L_shoulder, self.R_shoulder):
            return None

        ls, rs = landmarks[self.L_shoulder], landmarks[self.R_shoulder]

        if min(ls.visibility, rs.visibility) < 0.3:
            return None

        dx = rs.x - ls.x
        dy = rs.y - ls.y
        raw = math.degrees(math.atan2(dy, dx))

        # Smoothing
        self.lateral_buffer.append(raw)
        return sum(self.lateral_buffer) / len(self.lateral_buffer)

    def evaluate_posture(self, deviation: dict):
        """
        Evaluate posture from deviation dict (difference from baseline).
        Returns: (has_issue, messages, severity)
        """
        messages = []
        severity = 0.0

        if deviation is None:
            return False, messages, severity

        fwd = deviation.get("forward_shift")
        tilt = deviation.get("lateral_tilt")

        if fwd is not None and abs(fwd) > self.FORWARD_DEV_THRESHOLD:
            direction = "forward" if fwd < 0 else "backward"
            messages.append(f"Head leaning {direction} (Δ={fwd:.2f})")
            severity += abs(fwd) / self.FORWARD_DEV_THRESHOLD

        if tilt is not None and abs(tilt) > self.LATERAL_DEV_THRESHOLD:
            direction = "left" if tilt < 0 else "right"
            messages.append(f"Shoulder tilt {direction} (Δ={tilt:.1f}°)")
            severity += abs(tilt) / self.LATERAL_DEV_THRESHOLD

        return len(messages) > 0, messages, severity

    def reset_buffers(self):
        """Reset smoothing buffers (call after recalibration)"""
        self.forward_buffer.clear()
        self.lateral_buffer.clear()
