# gui/monitoring_worker.py
"""
Background worker for monitoring posture in separate thread.
Integrates: pose detection, blink/fatigue detection, distance detection,
break reminders with presence tracking, baseline calibration.
"""

import cv2
import mediapipe as mp
import time
import json
import numpy as np
from PySide6.QtCore import QObject, Signal

from services.models_loader import ModelLoader
from services.blink_detector import BlinkDetector
from services.distance_detector import DistanceDetector
from services.pose_detector import PoseDetector
from services.baseline_calibrator import BaselineCalibrator
from services.break_reminder import BreakReminder
from services.alert_manager import AlertManager
from services.session_manager import SessionManager
from data.sqlite_repo import SQLiteRepository
from utils.logger import setup_logger

# ML predictor (optional — works without trained model)
try:
    from ml.predictor import PosturePredictor
    _ML_AVAILABLE = True
except ImportError:
    _ML_AVAILABLE = False

# Online trainer (optional — retrains model from rule-based data)
try:
    from ml.online_trainer import OnlineTrainer
    _TRAINER_AVAILABLE = True
except ImportError:
    _TRAINER_AVAILABLE = False

logger = setup_logger(__name__)


class MonitoringWorker(QObject):
    frame_ready = Signal(np.ndarray)
    metrics_updated = Signal(dict)
    alert_triggered = Signal(str, str)
    calibration_progress = Signal(float)
    error_occurred = Signal(str)
    finished = Signal()
    overlay_requested = Signal(bool, str)

    def __init__(self, settings, user_id: int = 0):
        super().__init__()
        self.settings = settings
        self.user_id = user_id
        self.running = False
        self.paused = False

        self.db = None
        self.session_manager = None
        self.session_id = None
        self.camera = None
        self.models = None
        self.blink_detector = None
        self.distance_detector = None
        self.pose_detector = None
        self.baseline = None
        self.break_reminder = None
        self.alert_manager = None
        self.ml_predictor = None
        self.online_trainer = None
        self._session_detection_mode = 'rule_based'

        self.last_log_time = 0
        self.last_alert_time = {}
        self.frame_count = 0
        self.last_presence_state = True

        # Flag: calibration just finished this frame
        self._calibration_just_finished = False
        self._is_overlay_active = False
        self._bad_state_start_time = None

    def run(self):
        try:
            self._initialize()
            self._monitoring_loop()
        except Exception as e:
            logger.error(f"Monitoring error: {e}", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            self._cleanup()
            self.finished.emit()

    def _initialize(self):
        logger.info("Initializing monitoring worker...")

        self.db = SQLiteRepository()
        self.session_manager = SessionManager(self.db)

        camera_index = self.settings.get('camera_index', 0)
        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_index}")

        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        self.models = ModelLoader()

        self.blink_detector = BlinkDetector(
            threshold=self.settings.get('blink_ear_threshold', 0.21),
            fatigue_window=self.settings.get('fatigue_blink_window', 60),
            low_rate=self.settings.get('fatigue_low_blink_rate', 8),
            high_rate=self.settings.get('fatigue_high_blink_rate', 30),
        )

        self.distance_detector = DistanceDetector(
            tolerance_close=0.15,
            tolerance_far=0.15,
        )

        sensitivity = self.settings.get('posture_sensitivity', 'medium')
        self.pose_detector = PoseDetector(sensitivity=sensitivity)

        self.break_reminder = BreakReminder(
            soft_limit=self.settings.get('break_work_duration', 5400),
            hard_limit=self.settings.get('break_max_work_duration', 7200),
            absence_threshold=self.settings.get('absence_threshold', 600),
        )

        self.alert_manager = AlertManager(self.settings)

        # Baseline calibration
        cal_mode = self.settings.get('calibration_mode', 'always')
        self.baseline = BaselineCalibrator(
            duration=self.settings.get('calibration_duration', 5.0),
            min_samples=self.settings.get('min_calibration_samples', 30),
        )

        if cal_mode == 'once':
            last_baseline = self.db.get_setting('last_baseline')
            if last_baseline:
                baseline_data = json.loads(last_baseline)
                self.baseline.baseline = baseline_data
                self.baseline.is_calibrated = True
                if 'distance_ratio' in baseline_data:
                    self.distance_detector.set_baseline(baseline_data['distance_ratio'])
                logger.info("Loaded previous baseline")
            else:
                self.baseline.start_calibration()
        else:
            self.baseline.start_calibration()

        self.session_id = self.session_manager.start_session(self.user_id)
        self.running = True

        # ML predictor (optional)
        self._session_detection_mode = self.settings.get('detection_mode', 'rule_based')
        if _ML_AVAILABLE and self._session_detection_mode == 'ml':
            self.ml_predictor = PosturePredictor()
            if self.ml_predictor.is_available():
                logger.info("ML posture predictor loaded")
            else:
                logger.warning("ML model not found, falling back to rule-based")
                self.ml_predictor = None

        # Online trainer — will retrain model after rule-based sessions
        if _TRAINER_AVAILABLE:
            self.online_trainer = OnlineTrainer()

        logger.info("Monitoring worker initialized")

    def _monitoring_loop(self):
        target_fps = self.settings.get('target_fps', 30)
        frame_time = 1.0 / target_fps

        while self.running:
            loop_start = time.time()

            if self.paused:
                time.sleep(0.1)
                continue

            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.1)
                continue

            processed_frame, metrics = self._process_frame(frame)
            self.frame_ready.emit(processed_frame)
            self.metrics_updated.emit(metrics)

            # === Calibration progress handling ===
            if self.baseline.is_calibrating:
                progress = self.baseline.get_progress()
                self.calibration_progress.emit(progress)

            elif self._calibration_just_finished:
                # Calibration just completed — emit 1.0 to hide the bar
                self._calibration_just_finished = False
                self.calibration_progress.emit(1.0)

                # Save baseline if mode is 'once'
                if self.baseline.is_calibrated:
                    if self.settings.get('calibration_mode', 'always') == 'once':
                        baseline_json = json.dumps(self.baseline.baseline)
                        self.db.save_setting('last_baseline', baseline_json)

                    # Set distance baseline from calibration
                    br = self.baseline.get_baseline_value('distance_ratio')
                    if br:
                        self.distance_detector.set_baseline(br)
                        logger.info(f"Distance baseline set: {br:.4f}")

                    # Reset pose smoothing buffers after calibration
                    self.pose_detector.reset_buffers()

            # Log metrics periodically
            current_time = time.time()
            if current_time - self.last_log_time >= self.settings.get('log_interval', 5.0):
                self._log_metrics(metrics)
                self.last_log_time = current_time

            elapsed = time.time() - loop_start
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)

    def _process_frame(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        face_result = self.models.face_mesh.detect(mp_image)
        pose_result = self.models.pose.detect(mp_image)

        annotated = mp_image.numpy_view().copy()

        face_detected = bool(face_result.face_landmarks)
        body_detected = bool(pose_result.pose_landmarks)
        is_calibrating = self.baseline.is_calibrating

        # Presence detection
        is_present = face_detected
        break_info = self.break_reminder.update(is_present)

        # Log presence changes
        if is_present != self.last_presence_state:
            self.db.log_presence_event(self.session_id, is_present)
            self.last_presence_state = is_present

        # Break reminders (only when NOT calibrating)
        if not is_calibrating:
            if break_info['reminder'] == 'soft':
                self.alert_manager.trigger_break_reminder(break_info['work_minutes'])
                self.alert_triggered.emit('break',
                    f"You've been working for {break_info['work_minutes']:.0f} minutes. Consider taking a break!")
            elif break_info['reminder'] == 'hard':
                self.alert_manager.trigger_break_reminder(break_info['work_minutes'])
                self.alert_triggered.emit('break',
                    f"You've been working for {break_info['work_minutes']:.0f} minutes! Please take a break now.")

        metrics = {
            'blink_count': 0,
            'ear': None,
            'blink_rate': 0.0,
            'fatigue_level': 'NORMAL',
            'distance_status': 'OK',       # default OK, not Unknown during calibration
            'distance_ratio': None,
            'forward_shift': None,
            'lateral_tilt': None,
            'posture_status': 'OK',
            'severity': 0.0,
            'confidence': 0.0,
            'detection_method': 'ml' if self.ml_predictor else 'rules',
            'messages': [],
            'calibration_status': self.baseline.get_status(),
            'is_present': is_present,
            'work_minutes': break_info['work_minutes'],
        }

        # === Process face ===
        if face_detected:
            if self.settings.get('show_face_landmarks', True):
                annotated = self.models.draw_face_landmarks(annotated, face_result)

            lm_face = face_result.face_landmarks[0]

            # Blink detection (always, even during calibration)
            if self.settings.get('blink_tracking_enabled', True):
                blink_count, ear, blink_rate, fatigue = self.blink_detector.update(lm_face)
                metrics['blink_count'] = blink_count
                metrics['ear'] = ear
                metrics['blink_rate'] = blink_rate
                metrics['fatigue_level'] = fatigue

                # Fatigue alert (only after calibration)
                if not is_calibrating and fatigue != 'NORMAL':
                    self.alert_manager.trigger_fatigue_alert(fatigue, blink_rate)
                    self.alert_triggered.emit('fatigue',
                        f"Eye fatigue detected! Blink rate: {blink_rate:.0f}/min")

            # Distance detection — get ratio always (for calibration), but only check status after calibration
            distance_status, distance_ratio = self.distance_detector.check_distance(lm_face)
            metrics['distance_ratio'] = distance_ratio

            if is_calibrating:
                # During calibration: show OK, don't alert
                metrics['distance_status'] = 'OK'
            else:
                metrics['distance_status'] = distance_status

        # === Process pose ===
        if body_detected:
            if self.settings.get('show_pose_landmarks', True):
                annotated = self.models.draw_pose_landmarks(annotated, pose_result)

            lm_pose = pose_result.pose_landmarks[0]
            metrics['forward_shift'] = self.pose_detector.calculate_forward_shift(lm_pose)
            metrics['lateral_tilt'] = self.pose_detector.calculate_lateral_tilt(lm_pose)

        # === Handle calibration ===
        if is_calibrating:
            cal_metrics = {
                'forward_shift': metrics['forward_shift'],
                'lateral_tilt': metrics['lateral_tilt'],
                'distance_ratio': metrics['distance_ratio'],
            }
            finished = self.baseline.update(cal_metrics)
            if finished:
                # Calibration just completed on this frame
                self._calibration_just_finished = True
                logger.info("Calibration completed")

        elif self.baseline.is_calibrated and self.settings.get('posture_control_enabled', True):
            cal_metrics = {
                'forward_shift': metrics['forward_shift'],
                'lateral_tilt': metrics['lateral_tilt'],
            }
            deviation = self.baseline.deviation(cal_metrics)

            # Choose detection method: ML or rule-based
            if self.ml_predictor is not None and metrics['forward_shift'] is not None:
                # === ML-based detection ===
                # Pass deviation values (not raw), matching training data distribution
                dev_forward = deviation.get('forward_shift', 0.0) if deviation else 0.0
                dev_lateral = deviation.get('lateral_tilt', 0.0) if deviation else 0.0

                ml_result = self.ml_predictor.predict(
                    forward_shift=dev_forward,
                    lateral_tilt=dev_lateral,
                )
                metrics['posture_status'] = ml_result['status']
                metrics['severity'] = ml_result['severity']
                metrics['confidence'] = ml_result['confidence']
                metrics['detection_method'] = 'ml'

                if ml_result['status'] == 'BAD':
                    messages = [f"Bad posture detected (ML confidence: {ml_result['confidence']:.0%})"]
                    metrics['messages'] = messages
                    self._trigger_alert('posture', messages, ml_result['severity'])
            elif deviation:
                # === Rule-based detection ===
                has_issue, messages, severity = self.pose_detector.evaluate_posture(deviation)
                metrics['posture_status'] = 'BAD' if has_issue else 'OK'
                metrics['severity'] = severity
                metrics['messages'] = messages
                metrics['detection_method'] = 'rule_based'

                if has_issue:
                    self._trigger_alert('posture', messages, severity)

        # === Distance alerts (only after calibration) ===
        if not is_calibrating and metrics['distance_status'] not in ('OK', 'Unknown'):
            self._trigger_alert('distance',
                [f"Too {metrics['distance_status'].lower().replace('_', ' ')}"], 1.0)

        # OS Screen overlay logic
        reaction_mode = self.settings.get('reaction_mode', 'alert_only')
        if reaction_mode == 'blur_os_screen' and not is_calibrating:
            is_bad_state = (metrics['posture_status'] == 'BAD' or 
                            metrics['distance_status'] not in ('OK', 'Unknown'))
            if is_bad_state:
                if self._bad_state_start_time is None:
                    self._bad_state_start_time = time.time()
                elif time.time() - self._bad_state_start_time >= 4.0:  # 4 seconds delay
                    if not self._is_overlay_active:
                        msg = "Нарушение осанки!"
                        if metrics.get('messages'):
                            msg = metrics['messages'][0]
                        self.overlay_requested.emit(True, msg)
                        self._is_overlay_active = True
            else:
                self._bad_state_start_time = None
                if self._is_overlay_active:
                    self.overlay_requested.emit(False, "")
                    self._is_overlay_active = False

        return annotated, metrics

    def _trigger_alert(self, alert_type, messages, severity):
        current_time = time.time()
        cooldown = self.settings.get('alert_cooldown', 30)

        if alert_type in self.last_alert_time:
            if current_time - self.last_alert_time[alert_type] < cooldown:
                return

        self.last_alert_time[alert_type] = current_time
        message = "\n".join(messages)
        self.alert_triggered.emit(alert_type, message)

        if alert_type == 'posture':
            self.alert_manager.trigger_posture_alert(severity, messages)
        elif alert_type == 'distance':
            self.alert_manager.trigger_distance_alert(messages[0] if messages else "distance issue")

    def _log_metrics(self, metrics):
        try:
            if metrics['forward_shift'] is not None or metrics['lateral_tilt'] is not None:
                self.db.log_posture_event(
                    session_id=self.session_id,
                    forward_shift=metrics['forward_shift'],
                    lateral_tilt=metrics['lateral_tilt'],
                    posture_status=metrics['posture_status'],
                    severity=metrics['severity'],
                )

            if metrics['ear'] is not None:
                self.db.log_eye_event(
                    session_id=self.session_id,
                    blink_count=metrics['blink_count'],
                    ear=metrics['ear'],
                    blink_rate_per_min=metrics.get('blink_rate', 0),
                    fatigue_level=metrics.get('fatigue_level', 'NORMAL'),
                )

            if metrics['distance_ratio'] is not None:
                self.db.log_distance_event(
                    session_id=self.session_id,
                    distance_ratio=metrics['distance_ratio'],
                    distance_status=metrics['distance_status'],
                )
        except Exception as e:
            logger.error(f"Failed to log metrics: {e}")

    def _cleanup(self):
        logger.info("Cleaning up monitoring worker...")
        if self._is_overlay_active:
            self.overlay_requested.emit(False, "")
            self._is_overlay_active = False
        if self.session_id:
            self.session_manager.end_session(self.session_id)
        if self.camera:
            self.camera.release()
        if self.db:
            self.db.close()

        # Trigger background retraining after rule-based sessions
        if (self.online_trainer is not None
                and self._session_detection_mode == 'rule_based'):
            logger.info("Rule-based session ended — checking if model retraining is needed")
            self.online_trainer.maybe_retrain_async(predictor=self.ml_predictor)

        logger.info("Monitoring worker cleaned up")

    def stop(self):
        self.running = False

    def set_paused(self, paused: bool):
        self.paused = paused

    def update_settings(self, settings):
        self.settings = settings
        if self.pose_detector:
            sensitivity = settings.get('posture_sensitivity', 'medium')
            self.pose_detector.set_sensitivity(sensitivity)
        logger.info("Settings updated in monitoring worker")
