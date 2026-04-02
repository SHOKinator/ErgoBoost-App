# services/blink_detector.py
"""
Blink detection with fatigue monitoring.
Tracks blink rate per minute over a rolling window.
If rate drops below threshold for sustained period -> fatigue.
If rate is very high -> eye strain.
"""

import time
from math import sqrt
from collections import deque
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BlinkDetector:
    def __init__(self, threshold=0.21, fatigue_window=60,
                 low_rate=8, high_rate=30):
        self.threshold = threshold
        self.blink_count = 0
        self.eyes_closed = False

        # MediaPipe Face mesh eye landmark indices
        self.right_eye = [33, 160, 158, 133, 153, 144]
        self.left_eye  = [263, 387, 385, 362, 380, 373]

        # Fatigue detection
        self.fatigue_window = fatigue_window  # seconds
        self.low_blink_rate = low_rate        # blinks/min
        self.high_blink_rate = high_rate      # blinks/min
        self.blink_timestamps = deque()       # timestamps of each blink
        self.fatigue_level = 'NORMAL'         # NORMAL, LOW_BLINK, HIGH_BLINK
        self.fatigue_sustained_since = None   # when abnormal rate started
        self.fatigue_alert_threshold = 60     # must be abnormal for 60s

    def calculate_ear(self, landmarks, eye_indices):
        p1 = landmarks[eye_indices[0]]
        p2 = landmarks[eye_indices[1]]
        p3 = landmarks[eye_indices[2]]
        p4 = landmarks[eye_indices[3]]
        p5 = landmarks[eye_indices[4]]
        p6 = landmarks[eye_indices[5]]

        def dist(a, b):
            return sqrt((a.x - b.x)**2 + (a.y - b.y)**2)

        vertical1 = dist(p2, p6)
        vertical2 = dist(p3, p5)
        horizontal = dist(p1, p4)

        if horizontal < 1e-6:
            return 0.3  # safe default
        return (vertical1 + vertical2) / (2.0 * horizontal)

    def update(self, landmarks):
        right_ear = self.calculate_ear(landmarks, self.right_eye)
        left_ear  = self.calculate_ear(landmarks, self.left_eye)
        ear = (right_ear + left_ear) / 2.0

        now = time.time()

        if ear < self.threshold and not self.eyes_closed:
            self.eyes_closed = True
        elif ear >= self.threshold and self.eyes_closed:
            self.blink_count += 1
            self.eyes_closed = False
            self.blink_timestamps.append(now)

        # Clean old timestamps outside the window
        cutoff = now - self.fatigue_window
        while self.blink_timestamps and self.blink_timestamps[0] < cutoff:
            self.blink_timestamps.popleft()

        # Calculate current blink rate (blinks per minute)
        blink_rate = self._get_blink_rate()

        # Update fatigue level
        self._update_fatigue(blink_rate, now)

        return self.blink_count, ear, blink_rate, self.fatigue_level

    def _get_blink_rate(self) -> float:
        """Get current blink rate in blinks per minute"""
        if len(self.blink_timestamps) < 2:
            return 15.0  # assume normal if not enough data

        window_seconds = min(self.fatigue_window,
                            time.time() - self.blink_timestamps[0])
        if window_seconds < 10:
            return 15.0  # not enough data yet

        return (len(self.blink_timestamps) / window_seconds) * 60.0

    def _update_fatigue(self, blink_rate, now):
        current_level = 'NORMAL'
        if blink_rate < self.low_blink_rate:
            current_level = 'LOW_BLINK'
        elif blink_rate > self.high_blink_rate:
            current_level = 'HIGH_BLINK'

        if current_level != 'NORMAL':
            if self.fatigue_sustained_since is None:
                self.fatigue_sustained_since = now

            if now - self.fatigue_sustained_since >= self.fatigue_alert_threshold:
                self.fatigue_level = current_level
        else:
            self.fatigue_sustained_since = None
            self.fatigue_level = 'NORMAL'

    def reset(self):
        self.blink_count = 0
        self.eyes_closed = False
        self.blink_timestamps.clear()
        self.fatigue_level = 'NORMAL'
        self.fatigue_sustained_since = None
