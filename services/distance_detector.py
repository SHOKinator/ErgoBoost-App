# services/distance_detector.py
"""
Distance detector using face width ratio.
Uses baseline calibration: the ideal distance is whatever the user
sat at during calibration. Deviations from that baseline trigger alerts.
"""


class DistanceDetector:
    def __init__(self, tolerance_close=0.15, tolerance_far=0.15):
        """
        tolerance_close/far: how much deviation from baseline is allowed.
        E.g., 0.15 means 15% closer or farther than baseline.
        """
        self.tolerance_close = tolerance_close
        self.tolerance_far = tolerance_far

        self.LEFT = 234
        self.RIGHT = 454

        # Set from baseline calibration
        self.baseline_ratio = None

    def set_baseline(self, baseline_ratio: float):
        """Set the baseline distance ratio from calibration"""
        self.baseline_ratio = baseline_ratio

    def face_size_ratio(self, landmarks):
        left = landmarks[self.LEFT]
        right = landmarks[self.RIGHT]
        return ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5

    def check_distance(self, landmarks):
        ratio = self.face_size_ratio(landmarks)

        if self.baseline_ratio is None:
            # No baseline yet, use absolute thresholds
            if ratio > 0.3:
                return "TOO_CLOSE", ratio
            elif ratio < 0.18:
                return "TOO_FAR", ratio
            return "OK", ratio

        # Relative to baseline
        deviation = (ratio - self.baseline_ratio) / self.baseline_ratio

        if deviation > self.tolerance_close:
            return "TOO_CLOSE", ratio
        elif deviation < -self.tolerance_far:
            return "TOO_FAR", ratio
        return "OK", ratio
