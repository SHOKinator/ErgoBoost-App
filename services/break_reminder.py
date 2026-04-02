# services/break_reminder.py
"""
Smart break reminder system.
- Tracks continuous work time (when user is present at screen).
- If user is absent >10 minutes, that counts as a real break and resets the timer.
- If user is absent <10 minutes, it does NOT count as a break.
- Sends reminder after 1.5 hours of continuous work.
- Sends stronger reminder after 2 hours.
"""

import time
from utils.logger import setup_logger

logger = setup_logger(__name__)


class BreakReminder:
    def __init__(self, soft_limit=5400, hard_limit=7200,
                 absence_threshold=600):
        """
        soft_limit: seconds of continuous work before soft reminder (1.5h)
        hard_limit: seconds of continuous work before hard reminder (2h)
        absence_threshold: seconds of absence to count as a real break (10 min)
        """
        self.soft_limit = soft_limit
        self.hard_limit = hard_limit
        self.absence_threshold = absence_threshold

        # State
        self.continuous_work_seconds = 0.0
        self.last_update_time = None
        self.is_present = True
        self.absence_start_time = None

        # Tracking
        self.soft_reminder_sent = False
        self.hard_reminder_sent = False

    def update(self, is_present: bool) -> dict:
        """
        Call every frame/tick with whether user face is detected.
        Returns dict with possible reminder info.
        """
        now = time.time()
        result = {
            'reminder': None,
            'work_minutes': self.continuous_work_seconds / 60,
            'is_present': is_present,
        }

        if self.last_update_time is None:
            self.last_update_time = now
            self.is_present = is_present
            if not is_present:
                self.absence_start_time = now
            return result

        delta = now - self.last_update_time
        self.last_update_time = now

        if is_present:
            if not self.is_present:
                # User just came back
                absence_duration = now - self.absence_start_time if self.absence_start_time else 0

                if absence_duration >= self.absence_threshold:
                    # Real break! Reset work timer
                    logger.info(f"User returned after {absence_duration:.0f}s absence (real break)")
                    self.continuous_work_seconds = 0.0
                    self.soft_reminder_sent = False
                    self.hard_reminder_sent = False
                else:
                    logger.info(f"User returned after {absence_duration:.0f}s (short absence, not a break)")
                    # Short absence - don't reset timer, but don't count absence time as work

                self.absence_start_time = None

            # User is working, accumulate work time
            self.continuous_work_seconds += delta

            # Check if reminder needed
            if self.continuous_work_seconds >= self.hard_limit and not self.hard_reminder_sent:
                self.hard_reminder_sent = True
                result['reminder'] = 'hard'
                result['work_minutes'] = self.continuous_work_seconds / 60
            elif self.continuous_work_seconds >= self.soft_limit and not self.soft_reminder_sent:
                self.soft_reminder_sent = True
                result['reminder'] = 'soft'
                result['work_minutes'] = self.continuous_work_seconds / 60

        else:
            # User not present
            if self.is_present:
                # User just left
                self.absence_start_time = now
            # Don't accumulate work time while absent

        self.is_present = is_present
        result['work_minutes'] = self.continuous_work_seconds / 60
        return result

    def reset(self):
        self.continuous_work_seconds = 0.0
        self.last_update_time = None
        self.is_present = True
        self.absence_start_time = None
        self.soft_reminder_sent = False
        self.hard_reminder_sent = False

    def get_work_minutes(self):
        return self.continuous_work_seconds / 60
