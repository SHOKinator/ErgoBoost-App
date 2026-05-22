"""
Generate a synthetic user with ~300 sessions over 3 months.
Realistic posture, eye, distance, and presence data.
"""

import sys
import random
import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

DB_PATH = Path("data/ergoboost.db")

# --- Config ---
USERNAME = "demo"
PASSWORD = "demo1234"
DISPLAY_NAME = "Demo User"
MONTHS = 3
SESSIONS_PER_DAY_RANGE = (1, 4)  # 1-4 sessions per day
SESSION_DURATION_RANGE = (300, 5400)  # 5 min - 90 min
EVENT_INTERVAL = 3  # seconds between events

# PBKDF2 hashing (must match auth_service.py)
PBKDF2_ITERATIONS = 600_000

def hash_password(password, salt):
    dk = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return f"pbkdf2${PBKDF2_ITERATIONS}${dk.hex()}"


def generate():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    # Check if user exists
    existing = conn.execute("SELECT id FROM users WHERE username = ?", (USERNAME,)).fetchone()
    if existing:
        print(f"User '{USERNAME}' already exists (id={existing[0]}). Deleting old data...")
        uid = existing[0]
        # Delete old sessions and events
        session_ids = [r[0] for r in conn.execute(
            "SELECT id FROM sessions WHERE user_id = ?", (uid,)).fetchall()]
        for sid in session_ids:
            conn.execute("DELETE FROM posture_events WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM eye_events WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM distance_events WHERE session_id = ?", (sid,))
            conn.execute("DELETE FROM presence_events WHERE session_id = ?", (sid,))
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (uid,))
        conn.execute("DELETE FROM users WHERE id = ?", (uid,))
        conn.commit()

    # Create user
    salt = secrets.token_hex(16)
    pw_hash = hash_password(PASSWORD, salt)
    now_str = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')

    cur = conn.execute(
        "INSERT INTO users (username, password_hash, salt, display_name, created_at) VALUES (?,?,?,?,?)",
        (USERNAME, pw_hash, salt, DISPLAY_NAME, now_str)
    )
    user_id = cur.lastrowid
    conn.commit()
    print(f"Created user '{USERNAME}' (id={user_id})")

    # Generate sessions over 3 months
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=MONTHS * 30)

    current_date = start_date
    total_sessions = 0
    total_events = 0

    # Simulate improving posture over time (learning curve)
    total_days = (end_date - start_date).days

    while current_date < end_date:
        # Skip some days randomly (weekends, days off)
        if random.random() < 0.15:
            current_date += timedelta(days=1)
            continue

        day_progress = (current_date - start_date).days / max(total_days, 1)

        # More sessions as user gets into habit
        num_sessions = random.randint(*SESSIONS_PER_DAY_RANGE)
        if day_progress < 0.3:
            num_sessions = min(num_sessions, 2)

        for _ in range(num_sessions):
            # Session start: random time during work hours (8:00 - 20:00)
            hour = random.randint(8, 19)
            minute = random.randint(0, 59)
            session_start = current_date.replace(
                hour=hour, minute=minute, second=random.randint(0, 59),
                microsecond=0
            )

            duration = random.randint(*SESSION_DURATION_RANGE)
            # Shorter sessions early on, longer later
            if day_progress < 0.2:
                duration = min(duration, 1800)

            session_end = session_start + timedelta(seconds=duration)
            start_str = session_start.strftime('%Y-%m-%dT%H:%M:%S')
            end_str = session_end.strftime('%Y-%m-%dT%H:%M:%S')

            # Posture quality improves over time
            base_good_pct = 0.45 + day_progress * 0.40  # 45% -> 85%
            base_good_pct += random.uniform(-0.10, 0.10)
            base_good_pct = max(0.30, min(0.95, base_good_pct))

            # Insert session
            cur = conn.execute(
                "INSERT INTO sessions (user_id, start_time) VALUES (?, ?)",
                (user_id, start_str)
            )
            session_id = cur.lastrowid

            # Generate events
            t = 0
            good_count = 0
            bad_count = 0
            blink_rates = []
            distance_ok_count = 0
            distance_total = 0
            active_seconds = 0
            absent_count = 0
            break_count = 0
            was_absent = False

            while t < duration:
                event_time = session_start + timedelta(seconds=t)
                ts = event_time.strftime('%Y-%m-%dT%H:%M:%S')

                # Presence (occasionally absent for breaks)
                is_present = random.random() > 0.05
                if not is_present:
                    if not was_absent:
                        break_count += 1
                    was_absent = True
                    absent_count += 1
                else:
                    was_absent = False
                    active_seconds += EVENT_INTERVAL

                conn.execute(
                    "INSERT INTO presence_events (session_id, timestamp, is_present) VALUES (?,?,?)",
                    (session_id, ts, 1 if is_present else 0)
                )

                if is_present:
                    # Posture
                    is_good = random.random() < base_good_pct
                    if is_good:
                        good_count += 1
                        fwd = random.uniform(-0.02, 0.04)
                        tilt = random.uniform(-0.03, 0.03)
                        status = 'OK'
                        severity = 0.0
                    else:
                        bad_count += 1
                        fwd = random.uniform(0.05, 0.20)
                        tilt = random.uniform(-0.15, 0.15)
                        status = 'BAD'
                        severity = random.uniform(0.5, 3.0)

                    conn.execute(
                        """INSERT INTO posture_events 
                           (session_id, timestamp, forward_shift, lateral_tilt, posture_status, severity)
                           VALUES (?,?,?,?,?,?)""",
                        (session_id, ts, round(fwd, 4), round(tilt, 4), status, round(severity, 2))
                    )

                    # Eye
                    blink_rate = random.uniform(10, 22) if is_good else random.uniform(5, 15)
                    ear = random.uniform(0.22, 0.35)
                    blink_count = int(blink_rate * t / 60) if t > 0 else 0
                    fatigue = 'NORMAL' if blink_rate > 10 else 'TIRED'
                    blink_rates.append(blink_rate)

                    conn.execute(
                        """INSERT INTO eye_events
                           (session_id, timestamp, blink_count, ear, blink_rate_per_min, fatigue_level)
                           VALUES (?,?,?,?,?,?)""",
                        (session_id, ts, blink_count, round(ear, 4),
                         round(blink_rate, 2), fatigue)
                    )

                    # Distance
                    distance_total += 1
                    if random.random() < (0.7 + day_progress * 0.2):
                        dist_ratio = random.uniform(0.85, 1.15)
                        dist_status = 'OK'
                        distance_ok_count += 1
                    else:
                        if random.random() < 0.5:
                            dist_ratio = random.uniform(1.2, 1.8)
                            dist_status = 'TOO_CLOSE'
                        else:
                            dist_ratio = random.uniform(0.4, 0.7)
                            dist_status = 'TOO_FAR'

                    conn.execute(
                        """INSERT INTO distance_events
                           (session_id, timestamp, distance_ratio, distance_status)
                           VALUES (?,?,?,?)""",
                        (session_id, ts, round(dist_ratio, 4), dist_status)
                    )

                total_events += 1
                t += EVENT_INTERVAL

            # Calculate session stats
            total_posture = good_count + bad_count
            good_pct = (good_count / total_posture * 100) if total_posture > 0 else 50
            avg_blink = sum(blink_rates) / len(blink_rates) if blink_rates else 15
            dist_ok_pct = (distance_ok_count / distance_total * 100) if distance_total > 0 else 80

            # Score calculation (mirrors _calculate_session_score)
            score = 100.0
            score -= (100 - good_pct) * 0.5
            if avg_blink > 0 and (avg_blink < 10 or avg_blink > 25):
                score -= min(abs(avg_blink - 15) * 2, 25)
            score -= (100 - dist_ok_pct) * 0.25
            score = max(0, min(100, score))

            # Update session
            conn.execute(
                """UPDATE sessions SET end_time=?, duration_seconds=?, posture_score=?,
                   total_active_seconds=?, total_absent_seconds=?,
                   total_breaks=?, avg_blink_rate=?, good_posture_percent=?
                   WHERE id=?""",
                (end_str, duration, round(score, 1),
                 active_seconds, absent_count * EVENT_INTERVAL,
                 break_count, round(avg_blink, 2), round(good_pct, 1),
                 session_id)
            )

            total_sessions += 1

            if total_sessions % 50 == 0:
                conn.commit()
                print(f"  ... {total_sessions} sessions generated")

        current_date += timedelta(days=1)

    conn.commit()
    conn.close()

    print(f"\n{'='*50}")
    print(f"  Done!")
    print(f"  User: {USERNAME}")
    print(f"  Password: {PASSWORD}")
    print(f"  Sessions: {total_sessions}")
    print(f"  Events: {total_events:,}")
    print(f"  Period: {start_date.strftime('%Y-%m-%d')} — {end_date.strftime('%Y-%m-%d')}")
    print(f"{'='*50}")


if __name__ == '__main__':
    generate()
