# utils/export_utils.py
"""
Data export utilities
"""

import json
import csv
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from data.sqlite_repo import SQLiteRepository


def export_session_to_json(db: SQLiteRepository, session_id: int, output_path: Path):
    data = db.export_session_data(session_id)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=2)


def export_session_to_csv(db: SQLiteRepository, session_id: int, output_dir: Path):
    data = db.export_session_data(session_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    if data['posture_events']:
        with open(output_dir / f"session_{session_id}_posture.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data['posture_events'][0].keys())
            writer.writeheader()
            writer.writerows(data['posture_events'])

    if data['eye_events']:
        with open(output_dir / f"session_{session_id}_eye.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data['eye_events'][0].keys())
            writer.writeheader()
            writer.writerows(data['eye_events'])

    if data['distance_events']:
        with open(output_dir / f"session_{session_id}_distance.csv", 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=data['distance_events'][0].keys())
            writer.writeheader()
            writer.writerows(data['distance_events'])
