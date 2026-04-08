# tools/generate_synthetic_data.py
"""
Generate synthetic data for ErgoBoost.
Creates realistic sessions with posture degradation, blink patterns,
distance fluctuations, and presence/absence patterns.

Use this to:
1. Demo the app with rich data
2. Test PySpark analytics on large datasets
3. Show at diploma defense that the system handles big data

Usage:
    python -m tools.generate_synthetic_data --users 5 --days 90 --sessions-per-day 3
"""

import sys
import argparse
import random
import math
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.sqlite_repo import SQLiteRepository
from services.auth_service import AuthService


def generate_users(db: SQLiteRepository, count: int) -> list:
    """Create demo users and return their IDs"""
    auth = AuthService(db)
    users = []

    names = [
        ("alice", "Alice K."),
        ("bob", "Bob M."),
        ("carol", "Carol S."),
        ("dave", "Dave R."),
        ("emma", "Emma L."),
        ("frank", "Frank T."),
        ("grace", "Grace N."),
        ("henry", "Henry P."),
    ]

    for i in range(min(count, len(names))):
        username, display = names[i]
        try:
            existing = db.get_user_by_username(username)
            if existing:
                users.append(existing['id'])
                print(f"  User '{username}' already exists (id={existing['id']})")
            else:
                user = auth.sign_up(username, "demo1234", display)
                users.append(user['id'])
                print(f"  Created user '{username}' (id={user['id']})")
        except Exception as e:
            print(f"  Error creating user '{username}': {e}")

    return users


def generate_session(db: SQLiteRepository, user_id: int,
                     start_time: datetime, duration_minutes: int,
                     quality: str = "normal"):
    """
    Generate one session with realistic data.

    quality: 'good', 'normal', 'bad' - affects posture/fatigue patterns
    """
    conn = db.conn

    end_time = start_time + timedelta(minutes=duration_minutes)
    duration_seconds = duration_minutes * 60

    # Insert session
    with conn:
        cur = conn.execute(
            "INSERT INTO sessions (user_id, start_time, end_time, duration_seconds) VALUES (?, ?, ?, ?)",
            (user_id, start_time.isoformat(), end_time.isoformat(), duration_seconds)
        )
    session_id = cur.lastrowid

    # Quality parameters
    if quality == "good":
        base_severity = 0.2
        bad_posture_chance = 0.1
        base_blink_rate = 16.0
        fatigue_onset = 0.9   # fatigue starts at 90% of session
        distance_stability = 0.95
    elif quality == "bad":
        base_severity = 1.2
        bad_posture_chance = 0.5
        base_blink_rate = 10.0
        fatigue_onset = 0.4
        distance_stability = 0.7
    else:  # normal
        base_severity = 0.5
        bad_posture_chance = 0.25
        base_blink_rate = 14.0
        fatigue_onset = 0.65
        distance_stability = 0.85

    # Generate events every 5 seconds
    interval = 5.0
    num_events = int(duration_seconds / interval)
    blink_count = 0
    baseline_forward = random.uniform(-0.02, 0.02)
    baseline_lateral = random.uniform(-2.0, 2.0)
    baseline_distance = random.uniform(0.20, 0.26)

    posture_rows = []
    eye_rows = []
    distance_rows = []
    presence_rows = []

    # Simulate breaks (user leaves for a while)
    break_periods = []
    if duration_minutes > 30:
        num_breaks = random.randint(0, max(1, duration_minutes // 45))
        for _ in range(num_breaks):
            break_start_pct = random.uniform(0.2, 0.8)
            break_dur = random.randint(1, 15)  # 1-15 minutes
            break_periods.append((break_start_pct, break_dur / duration_minutes))

    good_events = 0
    total_events = 0

    for i in range(num_events):
        progress = i / max(num_events, 1)  # 0.0 -> 1.0
        ts = start_time + timedelta(seconds=i * interval)
        ts_iso = ts.isoformat()

        # Check if user is on break
        on_break = False
        for bp_start, bp_dur in break_periods:
            if bp_start <= progress <= bp_start + bp_dur:
                on_break = True
                break

        if on_break:
            presence_rows.append((session_id, ts_iso, 0))
            continue

        presence_rows.append((session_id, ts_iso, 1))

        # Fatigue factor: increases over time
        fatigue_factor = 0.0
        if progress > fatigue_onset:
            fatigue_factor = (progress - fatigue_onset) / (1.0 - fatigue_onset)

        # Posture: degrades with fatigue, with random noise
        noise_fwd = random.gauss(0, 0.02)
        noise_lat = random.gauss(0, 1.0)

        # Gradual slouch
        slouch = fatigue_factor * random.uniform(0.05, 0.15)

        forward_shift = baseline_forward - slouch + noise_fwd
        lateral_tilt = baseline_lateral + noise_lat + fatigue_factor * random.uniform(-3, 3)

        # Random bad posture bursts
        is_bad = random.random() < (bad_posture_chance + fatigue_factor * 0.3)

        if is_bad:
            forward_shift += random.choice([-1, 1]) * random.uniform(0.08, 0.2)
            lateral_tilt += random.choice([-1, 1]) * random.uniform(4, 12)

        severity = abs(forward_shift - baseline_forward) * 5 + abs(lateral_tilt - baseline_lateral) * 0.3
        severity = max(0, severity + random.gauss(0, 0.1))
        posture_status = "BAD" if severity > 1.0 else "OK"

        total_events += 1
        if posture_status == "OK":
            good_events += 1

        posture_rows.append((
            session_id, ts_iso, round(forward_shift, 4),
            round(lateral_tilt, 2), posture_status, round(severity, 3)
        ))

        # Blink: rate decreases with fatigue
        current_rate = base_blink_rate - fatigue_factor * 6 + random.gauss(0, 2)
        current_rate = max(3, min(35, current_rate))

        # Each 5-sec interval: expected blinks
        expected_blinks = current_rate / 12  # per 5 seconds
        new_blinks = max(0, int(expected_blinks + random.gauss(0, 0.5)))
        blink_count += new_blinks

        ear = random.uniform(0.22, 0.35) - fatigue_factor * 0.05
        ear = max(0.15, min(0.40, ear))

        fatigue_level = "NORMAL"
        if current_rate < 8:
            fatigue_level = "LOW_BLINK"
        elif current_rate > 28:
            fatigue_level = "HIGH_BLINK"

        eye_rows.append((
            session_id, ts_iso, blink_count, round(ear, 4),
            round(current_rate, 1), fatigue_level
        ))

        # Distance: fluctuates slightly, drifts closer with fatigue
        drift = fatigue_factor * 0.04
        distance_noise = random.gauss(0, 0.01) * (1.0 - distance_stability + 0.05)
        distance_ratio = baseline_distance + drift + distance_noise
        distance_ratio = max(0.10, min(0.40, distance_ratio))

        if distance_ratio > baseline_distance * 1.15:
            dist_status = "TOO_CLOSE"
        elif distance_ratio < baseline_distance * 0.85:
            dist_status = "TOO_FAR"
        else:
            dist_status = "OK"

        distance_rows.append((
            session_id, ts_iso, round(distance_ratio, 4), dist_status
        ))

    # Bulk insert
    with conn:
        conn.executemany(
            "INSERT INTO posture_events (session_id, timestamp, forward_shift, lateral_tilt, posture_status, severity) VALUES (?, ?, ?, ?, ?, ?)",
            posture_rows
        )
        conn.executemany(
            "INSERT INTO eye_events (session_id, timestamp, blink_count, ear, blink_rate_per_min, fatigue_level) VALUES (?, ?, ?, ?, ?, ?)",
            eye_rows
        )
        conn.executemany(
            "INSERT INTO distance_events (session_id, timestamp, distance_ratio, distance_status) VALUES (?, ?, ?, ?)",
            distance_rows
        )
        conn.executemany(
            "INSERT INTO presence_events (session_id, timestamp, is_present) VALUES (?, ?, ?)",
            presence_rows
        )

    # Update session summary
    good_pct = (good_events / total_events * 100) if total_events > 0 else 0
    score = max(0, min(100, good_pct * 0.7 + (100 - base_severity * 20) * 0.3))

    with conn:
        conn.execute(
            """UPDATE sessions SET posture_score = ?, good_posture_percent = ?,
               total_active_seconds = ?, avg_blink_rate = ?
               WHERE id = ?""",
            (round(score, 1), round(good_pct, 1),
             duration_seconds * 0.85, round(base_blink_rate, 1),
             session_id)
        )

    return session_id, len(posture_rows), len(eye_rows)


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic ErgoBoost data")
    parser.add_argument("--users", type=int, default=3, help="Number of demo users")
    parser.add_argument("--days", type=int, default=60, help="Days of history")
    parser.add_argument("--sessions-per-day", type=int, default=2,
                        help="Avg sessions per user per day")
    parser.add_argument("--db", type=str, default="data/ergoboost.db",
                        help="Database path")
    args = parser.parse_args()

    print(f"=== ErgoBoost Synthetic Data Generator ===")
    print(f"DB: {args.db}")
    print(f"Users: {args.users}, Days: {args.days}, Sessions/day: {args.sessions_per_day}")
    print()

    db = SQLiteRepository(Path(args.db))

    # Create users
    print("Creating users...")
    user_ids = generate_users(db, args.users)

    if not user_ids:
        print("No users created!")
        return

    print(f"\nGenerating sessions...")

    total_sessions = 0
    total_events = 0
    now = datetime.utcnow()

    for day_offset in range(args.days, 0, -1):
        day = now - timedelta(days=day_offset)

        for user_id in user_ids:
            # Random number of sessions this day (some days skip)
            if random.random() < 0.15:  # 15% chance no session
                continue

            num_sessions = max(1, int(random.gauss(args.sessions_per_day, 0.8)))

            for s in range(num_sessions):
                # Work hours: 8:00 - 20:00
                hour = random.randint(8, 18)
                minute = random.randint(0, 59)
                start = day.replace(hour=hour, minute=minute, second=0, microsecond=0)

                duration = random.randint(10, 120)  # 10-120 minutes

                # Quality varies: morning=good, afternoon=worse, random variation
                if hour < 12:
                    quality = random.choices(
                        ["good", "normal", "bad"], weights=[50, 40, 10])[0]
                elif hour < 16:
                    quality = random.choices(
                        ["good", "normal", "bad"], weights=[20, 50, 30])[0]
                else:
                    quality = random.choices(
                        ["good", "normal", "bad"], weights=[10, 40, 50])[0]

                sid, pe, ee = generate_session(db, user_id, start, duration, quality)
                total_sessions += 1
                total_events += pe + ee

                if total_sessions % 50 == 0:
                    print(f"  ... {total_sessions} sessions, {total_events:,} events")

    print(f"\n=== Done ===")
    print(f"Total sessions: {total_sessions}")
    print(f"Total events: {total_events:,}")

    # Count totals
    counts = db.conn.execute(
        "SELECT (SELECT COUNT(*) FROM posture_events) as pe, "
        "(SELECT COUNT(*) FROM eye_events) as ee, "
        "(SELECT COUNT(*) FROM distance_events) as de, "
        "(SELECT COUNT(*) FROM presence_events) as pre"
    ).fetchone()
    print(f"Posture events: {counts['pe']:,}")
    print(f"Eye events: {counts['ee']:,}")
    print(f"Distance events: {counts['de']:,}")
    print(f"Presence events: {counts['pre']:,}")
    print(f"Total records: {counts['pe'] + counts['ee'] + counts['de'] + counts['pre']:,}")

    db.close()


if __name__ == "__main__":
    main()
