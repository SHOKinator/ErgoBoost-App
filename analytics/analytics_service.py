# analytics/analytics_service.py
"""
Analytics service - uses SQLite directly for basic analytics.
PySpark available for advanced batch processing if installed.
"""

from pathlib import Path
from typing import Dict
import json
from datetime import datetime
from data.sqlite_repo import SQLiteRepository
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AnalyticsService:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db = SQLiteRepository(db_path)

    def generate_summary(self, days: int = 7) -> Dict:
        sessions = self.db.get_historical_data(days=days)
        if not sessions:
            return {'sessions': 0}

        scores = [s['posture_score'] for s in sessions if s.get('posture_score')]
        durations = [s['duration_seconds'] / 60 for s in sessions if s.get('duration_seconds')]

        return {
            'generated_at': datetime.now().isoformat(),
            'period_days': days,
            'sessions': len(sessions),
            'avg_score': sum(scores) / len(scores) if scores else 0,
            'total_minutes': sum(durations),
            'avg_duration_minutes': sum(durations) / len(durations) if durations else 0,
        }

    def export_to_json(self, output_path: Path, days: int = 7):
        summary = self.generate_summary(days)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Report exported to {output_path}")

    def close(self):
        self.db.close()
