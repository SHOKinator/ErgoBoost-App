# services/alert_manager.py
"""
Alert manager with Windows 11 native toast notifications.
Falls back to console output on other platforms.
"""

import time
import threading
import platform
from pathlib import Path
from utils.logger import setup_logger

logger = setup_logger(__name__)

# Try to import Windows notification library
_WINOTIFY_AVAILABLE = False
_PLYER_AVAILABLE = False

if platform.system() == 'Windows':
    try:
        from winotify import Notification, audio
        _WINOTIFY_AVAILABLE = True
    except ImportError:
        try:
            from plyer import notification as plyer_notification
            _PLYER_AVAILABLE = True
        except ImportError:
            pass


class AlertManager:
    """Manages alerts with Windows 11 native toast notifications"""

    def __init__(self, settings):
        self.settings = settings
        self.last_posture_alert = 0
        self.last_distance_alert = 0
        self.last_break_reminder = 0
        self.last_fatigue_alert = 0
        self.posture_alert_cooldown = settings.get('alert_cooldown', 30)
        self.sound_enabled = settings.get('sound_alerts_enabled', False)
        self.visual_enabled = settings.get('visual_alerts_enabled', True)

        self.sounds_dir = Path("assets/sounds")
        self.sounds_dir.mkdir(parents=True, exist_ok=True)

        self._app_id = "ErgoBoost"

    def trigger_posture_alert(self, severity, messages):
        current_time = time.time()
        if current_time - self.last_posture_alert < self.posture_alert_cooldown:
            return
        self.last_posture_alert = current_time

        msg = "\n".join(messages)
        if self.visual_enabled:
            self._show_toast("Posture Alert", msg, "warning")
        logger.warning(f"Posture alert: {messages}")

    def trigger_distance_alert(self, status):
        current_time = time.time()
        if current_time - self.last_distance_alert < self.posture_alert_cooldown:
            return
        self.last_distance_alert = current_time

        msg = f"You are sitting too {status.lower()} from the screen!"
        if self.visual_enabled:
            self._show_toast("Distance Alert", msg, "warning")
        logger.warning(f"Distance alert: {status}")

    def trigger_fatigue_alert(self, fatigue_level, blink_rate):
        current_time = time.time()
        if current_time - self.last_fatigue_alert < 120:  # 2 min cooldown
            return
        self.last_fatigue_alert = current_time

        if fatigue_level == 'LOW_BLINK':
            msg = f"Your blink rate is low ({blink_rate:.0f}/min). Your eyes may be getting tired. Try blinking more or take a short break."
        else:
            msg = f"Your blink rate is unusually high ({blink_rate:.0f}/min). You may be experiencing eye strain."

        if self.visual_enabled:
            self._show_toast("Eye Fatigue", msg, "info")
        logger.warning(f"Fatigue alert: {fatigue_level}, rate={blink_rate:.1f}")

    def trigger_break_reminder(self, work_minutes):
        current_time = time.time()
        if current_time - self.last_break_reminder < 300:  # 5 min cooldown
            return
        self.last_break_reminder = current_time

        msg = f"You've been working for {work_minutes:.0f} minutes. Time to take a break and stretch!"
        if self.visual_enabled:
            self._show_toast("Break Reminder", msg, "info")
        logger.info(f"Break reminder: {work_minutes:.0f} min")

    def _show_toast(self, title, message, level="info"):
        """Show a native Windows 11 toast notification"""
        def _send():
            try:
                if _WINOTIFY_AVAILABLE:
                    toast = Notification(
                        app_id=self._app_id,
                        title=title,
                        msg=message,
                        duration="short",
                    )
                    if self.sound_enabled:
                        toast.set_audio(audio.Default, loop=False)
                    toast.show()
                elif _PLYER_AVAILABLE:
                    plyer_notification.notify(
                        title=title,
                        message=message,
                        app_name=self._app_id,
                        timeout=5,
                    )
                else:
                    # Fallback to console
                    logger.info(f"[{title}] {message}")
            except Exception as e:
                logger.error(f"Failed to show notification: {e}")

        thread = threading.Thread(target=_send, daemon=True)
        thread.start()
