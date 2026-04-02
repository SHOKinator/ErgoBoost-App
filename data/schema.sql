-- data/schema.sql
-- ErgoBoost Database Schema

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

CREATE INDEX IF NOT EXISTS idx_posture_session ON posture_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_eye_session ON eye_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_distance_session ON distance_events(session_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_presence_session ON presence_events(session_id, timestamp);
