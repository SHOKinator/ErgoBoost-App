# services/session_manager.py
from datetime import datetime
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SessionManager:
    def __init__(self, db):
        self.db = db

    def start_session(self):
        session_id = self.db.start_session()
        logger.info(f"Started session {session_id}")
        return session_id

    def end_session(self, session_id):
        self.db.end_session(session_id)
        logger.info(f"Ended session {session_id}")

    def get_session_summary(self, session_id):
        try:
            session = self.db.get_session(session_id)
            if not session:
                return None

            start_time = datetime.fromisoformat(session['start_time'])
            end_time = datetime.fromisoformat(session['end_time']) if session['end_time'] else datetime.utcnow()
            duration = (end_time - start_time).total_seconds() / 60

            posture_stats = self.db.get_posture_statistics(session_id)
            eye_stats = self.db.get_eye_statistics(session_id)
            distance_stats = self.db.get_distance_statistics(session_id)
            presence_stats = self.db.get_presence_statistics(session_id)

            return {
                'session_id': session_id,
                'duration_minutes': duration,
                'good_posture_percent': posture_stats.get('good_posture_percent', 0),
                'avg_severity': posture_stats.get('avg_severity', 0),
                'avg_blink_rate': eye_stats.get('avg_blink_rate', 0),
                'fatigue_percent': eye_stats.get('fatigue_percent', 0),
                'distance_ok_percent': distance_stats.get('distance_ok_percent', 0),
                'active_minutes': presence_stats.get('active_seconds', 0) / 60,
                'break_count': presence_stats.get('break_count', 0),
                'posture_score': session.get('posture_score', 0),
            }
        except Exception as e:
            logger.error(f"Failed to get session summary: {e}")
            return None
