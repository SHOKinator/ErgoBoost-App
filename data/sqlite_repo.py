# data/sqlite_repo.py
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List
from utils.logger import setup_logger

logger = setup_logger(__name__)

DB_PATH = Path("data/ergoboost.db")


class SQLiteRepository:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        with self.conn:
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    duration_seconds REAL,
                    posture_score REAL,
                    total_active_seconds REAL DEFAULT 0,
                    total_absent_seconds REAL DEFAULT 0,
                    total_breaks INTEGER DEFAULT 0,
                    avg_blink_rate REAL,
                    avg_distance_ratio REAL,
                    good_posture_percent REAL
                );

                CREATE TABLE IF NOT EXISTS posture_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    forward_shift REAL,
                    lateral_tilt REAL,
                    posture_status TEXT,
                    severity REAL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS eye_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    blink_count INTEGER,
                    ear REAL,
                    blink_rate_per_min REAL,
                    fatigue_level TEXT DEFAULT 'NORMAL',
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS distance_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    distance_ratio REAL,
                    distance_status TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS presence_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_present INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_posture_session
                    ON posture_events(session_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_eye_session
                    ON eye_events(session_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_distance_session
                    ON distance_events(session_id, timestamp);
                CREATE INDEX IF NOT EXISTS idx_presence_session
                    ON presence_events(session_id, timestamp);
            """)

    # ===== SESSION MANAGEMENT =====

    def start_session(self) -> int:
        now = datetime.utcnow().isoformat()
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO sessions (start_time) VALUES (?)", (now,)
            )
        return cur.lastrowid

    def end_session(self, session_id: int):
        now = datetime.utcnow().isoformat()
        row = self.conn.execute(
            "SELECT start_time FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()

        if row:
            start_time = datetime.fromisoformat(row['start_time'])
            end_time = datetime.fromisoformat(now)
            duration = (end_time - start_time).total_seconds()
            posture_score = self._calculate_session_score(session_id)
            posture_stats = self.get_posture_statistics(session_id)
            eye_stats = self.get_eye_statistics(session_id)
            presence_stats = self.get_presence_statistics(session_id)

            with self.conn:
                self.conn.execute(
                    """UPDATE sessions
                       SET end_time = ?, duration_seconds = ?, posture_score = ?,
                           total_active_seconds = ?, total_absent_seconds = ?,
                           total_breaks = ?, avg_blink_rate = ?,
                           good_posture_percent = ?
                       WHERE id = ?""",
                    (now, duration, posture_score,
                     presence_stats.get('active_seconds', duration),
                     presence_stats.get('absent_seconds', 0),
                     presence_stats.get('break_count', 0),
                     eye_stats.get('avg_blink_rate', 0),
                     posture_stats.get('good_posture_percent', 0),
                     session_id)
                )

    def get_session(self, session_id: int) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_sessions(self, limit: int = 100) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]

    # ===== EVENT LOGGING =====

    def log_posture_event(self, session_id, forward_shift, lateral_tilt,
                          posture_status, severity):
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                """INSERT INTO posture_events
                   (session_id, timestamp, forward_shift, lateral_tilt,
                    posture_status, severity)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, now, forward_shift, lateral_tilt,
                 posture_status, severity)
            )

    def log_eye_event(self, session_id, blink_count, ear,
                      blink_rate_per_min=0.0, fatigue_level='NORMAL'):
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                """INSERT INTO eye_events
                   (session_id, timestamp, blink_count, ear,
                    blink_rate_per_min, fatigue_level)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (session_id, now, blink_count, ear,
                 blink_rate_per_min, fatigue_level)
            )

    def log_distance_event(self, session_id, distance_ratio, distance_status):
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                """INSERT INTO distance_events
                   (session_id, timestamp, distance_ratio, distance_status)
                   VALUES (?, ?, ?, ?)""",
                (session_id, now, distance_ratio, distance_status)
            )

    def log_presence_event(self, session_id, is_present):
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                """INSERT INTO presence_events
                   (session_id, timestamp, is_present)
                   VALUES (?, ?, ?)""",
                (session_id, now, int(is_present))
            )

    # ===== STATISTICS =====

    def get_posture_statistics(self, session_id: int) -> Dict:
        result = self.conn.execute(
            """SELECT
                COUNT(*) as total_events,
                SUM(CASE WHEN posture_status = 'OK' THEN 1 ELSE 0 END) as good_events,
                AVG(severity) as avg_severity,
                MAX(severity) as max_severity,
                AVG(forward_shift) as avg_forward_shift,
                AVG(lateral_tilt) as avg_lateral_tilt
               FROM posture_events WHERE session_id = ?""",
            (session_id,)
        ).fetchone()

        if result and result['total_events'] > 0:
            good_pct = (result['good_events'] / result['total_events']) * 100
            return {
                'total_events': result['total_events'],
                'good_posture_percent': good_pct,
                'avg_severity': result['avg_severity'] or 0,
                'max_severity': result['max_severity'] or 0,
                'avg_forward_shift': result['avg_forward_shift'] or 0,
                'avg_lateral_tilt': result['avg_lateral_tilt'] or 0,
            }
        return {
            'total_events': 0, 'good_posture_percent': 0,
            'avg_severity': 0, 'max_severity': 0,
            'avg_forward_shift': 0, 'avg_lateral_tilt': 0,
        }

    def get_eye_statistics(self, session_id: int) -> Dict:
        session = self.get_session(session_id)
        if not session or not session.get('duration_seconds'):
            return {'avg_blink_rate': 0, 'avg_ear': 0,
                    'fatigue_percent': 0}

        duration_minutes = session['duration_seconds'] / 60

        blink_result = self.conn.execute(
            "SELECT MAX(blink_count) as total_blinks, AVG(ear) as avg_ear FROM eye_events WHERE session_id = ?",
            (session_id,)
        ).fetchone()

        total_blinks = blink_result['total_blinks'] or 0
        avg_blink_rate = total_blinks / duration_minutes if duration_minutes > 0 else 0

        fatigue_result = self.conn.execute(
            """SELECT COUNT(*) as total,
                      SUM(CASE WHEN fatigue_level != 'NORMAL' THEN 1 ELSE 0 END) as fatigue_events
               FROM eye_events WHERE session_id = ?""",
            (session_id,)
        ).fetchone()

        fatigue_pct = 0
        if fatigue_result and fatigue_result['total'] > 0:
            fatigue_pct = (fatigue_result['fatigue_events'] / fatigue_result['total']) * 100

        return {
            'avg_blink_rate': avg_blink_rate,
            'avg_ear': blink_result['avg_ear'] or 0,
            'fatigue_percent': fatigue_pct,
            'total_blinks': total_blinks,
        }

    def get_distance_statistics(self, session_id: int) -> Dict:
        result = self.conn.execute(
            """SELECT
                COUNT(*) as total_events,
                SUM(CASE WHEN distance_status = 'OK' THEN 1 ELSE 0 END) as ok_events,
                AVG(distance_ratio) as avg_ratio
               FROM distance_events WHERE session_id = ?""",
            (session_id,)
        ).fetchone()

        if result and result['total_events'] > 0:
            return {
                'total_events': result['total_events'],
                'distance_ok_percent': (result['ok_events'] / result['total_events']) * 100,
                'avg_distance_ratio': result['avg_ratio'] or 0,
            }
        return {'total_events': 0, 'distance_ok_percent': 0, 'avg_distance_ratio': 0}

    def get_presence_statistics(self, session_id: int) -> Dict:
        rows = self.conn.execute(
            "SELECT timestamp, is_present FROM presence_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()

        if not rows:
            return {'active_seconds': 0, 'absent_seconds': 0, 'break_count': 0}

        active_seconds = 0.0
        absent_seconds = 0.0
        break_count = 0
        prev_time = None
        prev_present = True

        for row in rows:
            ts = datetime.fromisoformat(row['timestamp'])
            if prev_time is not None:
                delta = (ts - prev_time).total_seconds()
                if prev_present:
                    active_seconds += delta
                else:
                    absent_seconds += delta
            if not row['is_present'] and prev_present:
                break_count += 1
            prev_present = bool(row['is_present'])
            prev_time = ts

        return {
            'active_seconds': active_seconds,
            'absent_seconds': absent_seconds,
            'break_count': break_count,
        }

    def get_posture_timeline(self, session_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT timestamp, forward_shift, lateral_tilt, severity, posture_status FROM posture_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_eye_timeline(self, session_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT timestamp, blink_count, ear, blink_rate_per_min, fatigue_level FROM eye_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_distance_timeline(self, session_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT timestamp, distance_ratio, distance_status FROM distance_events WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def _calculate_session_score(self, session_id: int) -> float:
        posture_stats = self.get_posture_statistics(session_id)
        eye_stats = self.get_eye_statistics(session_id)
        distance_stats = self.get_distance_statistics(session_id)

        score = 100.0
        score -= (100 - posture_stats['good_posture_percent']) * 0.5

        blink_rate = eye_stats['avg_blink_rate']
        if blink_rate > 0 and (blink_rate < 10 or blink_rate > 25):
            blink_penalty = min(abs(blink_rate - 15) * 2, 25)
            score -= blink_penalty

        score -= (100 - distance_stats['distance_ok_percent']) * 0.25
        return max(0, min(100, score))

    def get_historical_data(self, days: int = 7) -> List[Dict]:
        from datetime import timedelta
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            "SELECT * FROM sessions WHERE start_time >= ? ORDER BY start_time DESC",
            (cutoff,)
        ).fetchall()
        return [dict(row) for row in rows]

    def export_session_data(self, session_id: int) -> Dict:
        posture_events = self.conn.execute(
            "SELECT * FROM posture_events WHERE session_id = ?", (session_id,)
        ).fetchall()
        eye_events = self.conn.execute(
            "SELECT * FROM eye_events WHERE session_id = ?", (session_id,)
        ).fetchall()
        distance_events = self.conn.execute(
            "SELECT * FROM distance_events WHERE session_id = ?", (session_id,)
        ).fetchall()

        return {
            'session': self.get_session(session_id),
            'posture_events': [dict(row) for row in posture_events],
            'eye_events': [dict(row) for row in eye_events],
            'distance_events': [dict(row) for row in distance_events],
        }

    def save_setting(self, key: str, value: str):
        now = datetime.utcnow().isoformat()
        with self.conn:
            self.conn.execute(
                "INSERT OR REPLACE INTO user_settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, value, now)
            )

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM user_settings WHERE key = ?", (key,)
        ).fetchone()
        return row['value'] if row else default

    def close(self):
        self.conn.close()
